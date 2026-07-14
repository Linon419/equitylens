import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import tldextract

PUBLIC_SUFFIX_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())

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
    async def resolve(self, hostname: str) -> tuple[str, ...]:
        loop = asyncio.get_running_loop()
        results = await loop.getaddrinfo(
            hostname,
            443,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
        return tuple(sorted({str(result[4][0]) for result in results}))


class SourceUrlPolicy:
    def __init__(self, *, issuer_hosts: tuple[str, ...]) -> None:
        try:
            normalized_hosts = tuple(_normalize_hostname(host) for host in issuer_hosts)
            issuer_domains = frozenset(
                _registrable_domain(host) for host in normalized_hosts
            )
        except (TypeError, ValueError, UnicodeError):
            raise SourcePolicyError("SOURCE_ISSUER_HOST_INVALID") from None
        if not normalized_hosts or "" in issuer_domains:
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
    if not value or len(value) > 8192 or "\\" in value:
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
