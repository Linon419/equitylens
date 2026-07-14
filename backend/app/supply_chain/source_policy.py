import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import httpcore
import httpx
import tldextract

PUBLIC_SUFFIX_EXTRACTOR = tldextract.TLDExtract(
    suffix_list_urls=(),
    include_psl_private_domains=True,
)

SEC_HOSTS = frozenset(
    {
        "sec.gov",
        "www.sec.gov",
        "data.sec.gov",
        "archives.sec.gov",
    }
)
ISSUER_SUBDOMAIN_LABELS = frozenset({"investor", "investors", "ir", "news", "newsroom"})
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class SourcePolicyError(RuntimeError):
    """A source-policy failure with a stable, disclosure-safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidatedSourceUrl:
    normalized_url: str
    hostname: str
    port: int
    registrable_domain: str


class HostResolver(Protocol):
    async def resolve(self, hostname: str) -> tuple[str, ...]: ...


class SystemHostResolver:
    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def resolve(self, hostname: str) -> tuple[str, ...]:
        loop = asyncio.get_running_loop()
        async with asyncio.timeout(self._timeout_seconds):
            results = await loop.getaddrinfo(
                hostname,
                443,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        return tuple(sorted({str(result[4][0]) for result in results}))


class PinningHostResolver:
    def __init__(self, resolver: HostResolver | None = None) -> None:
        self._resolver = resolver or SystemHostResolver()
        self._pins: dict[str, tuple[str, ...]] = {}

    async def resolve(self, hostname: str) -> tuple[str, ...]:
        addresses = await self._resolver.resolve(hostname)
        self._pins[hostname] = addresses
        return addresses

    def pinned_addresses(self, hostname: str) -> tuple[str, ...]:
        return self._pins.get(hostname, ())


class PinnedNetworkBackend:
    def __init__(
        self,
        resolver: PinningHostResolver,
        *,
        backend: Any | None = None,
    ) -> None:
        self._resolver = resolver
        self._backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any | None = None,
    ) -> httpcore.AsyncNetworkStream:
        hostname = host.decode("ascii") if isinstance(host, bytes) else host
        addresses = self._resolver.pinned_addresses(hostname)
        if not addresses:
            raise httpcore.ConnectError("SOURCE_DNS_PIN_MISSING")
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception:
                continue
        raise httpcore.ConnectError("SOURCE_PINNED_CONNECT_FAILED") from None

    async def connect_unix_socket(self, *args: Any, **kwargs: Any) -> Any:
        raise httpcore.ConnectError("SOURCE_UNIX_SOCKET_FORBIDDEN")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class PinnedDnsTransport(httpx.AsyncHTTPTransport):
    def __init__(self, resolver: PinningHostResolver) -> None:
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=True, trust_env=False),
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=5.0,
            retries=0,
            network_backend=PinnedNetworkBackend(resolver),
        )


class SourceUrlPolicy:
    def __init__(self, *, issuer_hosts: tuple[str, ...]) -> None:
        try:
            normalized_hosts = tuple(_normalize_hostname(host) for host in issuer_hosts)
            issuer_domains = frozenset(
                _registrable_domain(host) for host in normalized_hosts
            )
        except (TypeError, ValueError, UnicodeError):
            raise SourcePolicyError("SOURCE_ISSUER_HOST_INVALID") from None
        if "" in issuer_domains:
            raise SourcePolicyError("SOURCE_ISSUER_HOST_INVALID")
        self._issuer_hosts = frozenset(normalized_hosts)
        self._issuer_domains = issuer_domains

    def validate_url(self, url: str) -> ValidatedSourceUrl:
        if not isinstance(url, str) or _contains_unsafe_characters(url):
            raise SourcePolicyError("SOURCE_URL_INVALID")
        try:
            parsed = urlsplit(url)
            hostname_value = parsed.hostname
            port = parsed.port
        except (UnicodeError, ValueError):
            raise SourcePolicyError("SOURCE_URL_INVALID") from None
        if parsed.scheme.casefold() != "https":
            raise SourcePolicyError("SOURCE_URL_SCHEME_UNSUPPORTED")
        if (
            hostname_value is None
            or parsed.username is not None
            or parsed.password is not None
            or "\\" in parsed.netloc
        ):
            raise SourcePolicyError("SOURCE_URL_INVALID")
        if port not in {None, 443}:
            raise SourcePolicyError("SOURCE_URL_PORT_FORBIDDEN")
        try:
            hostname = _normalize_hostname(hostname_value)
        except (TypeError, ValueError, UnicodeError):
            raise SourcePolicyError("SOURCE_URL_INVALID") from None
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise SourcePolicyError("SOURCE_URL_HOST_FORBIDDEN")
        try:
            registrable_domain = _registrable_domain(hostname)
        except ValueError:
            raise SourcePolicyError("SOURCE_URL_HOST_FORBIDDEN") from None
        if not self._host_is_allowed(hostname, registrable_domain):
            raise SourcePolicyError("SOURCE_URL_HOST_FORBIDDEN")
        normalized = urlunsplit(("https", hostname, parsed.path, parsed.query, ""))
        return ValidatedSourceUrl(
            normalized_url=normalized,
            hostname=hostname,
            port=443,
            registrable_domain=registrable_domain,
        )

    async def authorize(
        self,
        url: str,
        resolver: HostResolver,
    ) -> ValidatedSourceUrl:
        validated = self.validate_url(url)
        await self.validate_dns(validated, resolver)
        return validated

    async def validate_dns(
        self,
        validated: ValidatedSourceUrl,
        resolver: HostResolver,
    ) -> None:
        try:
            addresses = await resolver.resolve(validated.hostname)
        except Exception:
            raise SourcePolicyError("SOURCE_DNS_FAILURE") from None
        if not addresses:
            raise SourcePolicyError("SOURCE_DNS_FAILURE")
        try:
            parsed_addresses = tuple(
                ipaddress.ip_address(address) for address in addresses
            )
        except ValueError:
            raise SourcePolicyError("SOURCE_DNS_FAILURE") from None
        if any(not _address_is_safe(address) for address in parsed_addresses):
            raise SourcePolicyError("SOURCE_DNS_UNSAFE")

    async def authorize_redirect(
        self,
        *,
        current: ValidatedSourceUrl,
        location: str,
        redirect_count: int,
        resolver: HostResolver,
    ) -> ValidatedSourceUrl:
        if redirect_count < 1 or redirect_count > 3:
            raise SourcePolicyError("SOURCE_REDIRECT_LIMIT")
        if not isinstance(location, str) or not location:
            raise SourcePolicyError("SOURCE_REDIRECT_INVALID")
        target = urljoin(current.normalized_url, location)
        return await self.authorize(target, resolver)

    def _host_is_allowed(self, hostname: str, registrable_domain: str) -> bool:
        if hostname in SEC_HOSTS or hostname in self._issuer_hosts:
            return True
        first_label = hostname.split(".", 1)[0]
        return (
            first_label in ISSUER_SUBDOMAIN_LABELS
            and registrable_domain in self._issuer_domains
        )


def _contains_unsafe_characters(value: str) -> bool:
    if not value or len(value) > 2000 or "\\" in value:
        return True
    decoded = value
    for _ in range(8):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    else:
        return True
    return any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in decoded
    )


def _normalize_hostname(hostname: str) -> str:
    if not isinstance(hostname, str) or not hostname:
        raise ValueError("hostname is required")
    value = hostname.rstrip(".")
    if not value or "%" in value:
        raise ValueError("hostname is invalid")
    ascii_hostname = value.encode("idna").decode("ascii").casefold()
    if len(ascii_hostname) > 253:
        raise ValueError("hostname is too long")
    if any(_HOST_LABEL.fullmatch(label) is None for label in ascii_hostname.split(".")):
        raise ValueError("hostname is invalid")
    return ascii_hostname


def _registrable_domain(hostname: str) -> str:
    extracted = PUBLIC_SUFFIX_EXTRACTOR(hostname)
    domain = extracted.top_domain_under_public_suffix
    if not domain:
        raise ValueError("registrable domain is required")
    return domain.casefold()


def _address_is_safe(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_global
        and not address.is_loopback
        and not address.is_private
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )
