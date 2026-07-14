import traceback

import httpcore
import pytest

from app.supply_chain.source_policy import (
    PUBLIC_SUFFIX_EXTRACTOR,
    PinnedNetworkBackend,
    PinningHostResolver,
    SourcePolicyError,
    SourceUrlPolicy,
)


class Resolver:
    def __init__(self, addresses: dict[str, tuple[str, ...]]) -> None:
        self.addresses = addresses
        self.calls: list[str] = []

    async def resolve(self, hostname: str) -> tuple[str, ...]:
        self.calls.append(hostname)
        return self.addresses[hostname]


def issuer_policy() -> SourceUrlPolicy:
    return SourceUrlPolicy(issuer_hosts=("apple.com", "www.apple.com"))


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("http://127.0.0.1/private", "SOURCE_URL_SCHEME_UNSUPPORTED"),
        ("https://169.254.169.254/latest", "SOURCE_URL_HOST_FORBIDDEN"),
        ("https://user:secret@apple.com/report", "SOURCE_URL_INVALID"),
        ("https://apple.com:444/report", "SOURCE_URL_PORT_FORBIDDEN"),
        ("file:///etc/passwd", "SOURCE_URL_SCHEME_UNSUPPORTED"),
        ("https://[invalid/report", "SOURCE_URL_INVALID"),
        ("https://apple.com/line\nbreak", "SOURCE_URL_INVALID"),
        ("https://\ud800.com/report", "SOURCE_URL_INVALID"),
    ],
)
def test_rejects_unsafe_and_malformed_urls(url: str, code: str) -> None:
    with pytest.raises(SourcePolicyError) as error:
        issuer_policy().validate_url(url)

    assert error.value.code == code
    assert str(error.value) == code


def test_rejects_deeply_percent_encoded_control_characters() -> None:
    with pytest.raises(SourcePolicyError) as error:
        issuer_policy().validate_url("https://apple.com/report%250aheader")

    assert error.value.code == "SOURCE_URL_INVALID"


@pytest.mark.parametrize(
    "url",
    [
        "https://sec.gov/Archives/a",
        "https://www.sec.gov/Archives/a",
        "https://data.sec.gov/submissions/a.json",
        "https://archives.sec.gov/Archives/a",
    ],
)
def test_accepts_fixed_sec_hosts(url: str) -> None:
    validated = issuer_policy().validate_url(url)

    assert validated.hostname in {
        "sec.gov",
        "www.sec.gov",
        "data.sec.gov",
        "archives.sec.gov",
    }
    assert validated.port == 443
    assert validated.registrable_domain == "sec.gov"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://APPLE.com:443/news?q=supply#fragment",
            "https://apple.com/news?q=supply",
        ),
        ("https://investor.apple.com/earnings", None),
        ("https://ir.apple.com/results", None),
        ("https://newsroom.apple.com/update", None),
        ("https://news.apple.com/release", None),
    ],
)
def test_accepts_registered_issuer_and_explicit_ir_newsroom_hosts(
    url: str,
    expected: str | None,
) -> None:
    validated = issuer_policy().validate_url(url)

    assert validated.registrable_domain == "apple.com"
    assert validated.normalized_url == (expected or url)


@pytest.mark.parametrize(
    "url",
    [
        "https://store.apple.com/report",
        "https://apple.example/report",
        "https://apple.com.evil.example/report",
        "https://newsroom.apple.com.evil.example/report",
        "https://evilapple.com/report",
    ],
)
def test_rejects_sibling_unrelated_and_suffix_trick_hosts(url: str) -> None:
    with pytest.raises(SourcePolicyError) as error:
        issuer_policy().validate_url(url)

    assert error.value.code == "SOURCE_URL_HOST_FORBIDDEN"


def test_private_suffix_tenants_do_not_share_an_issuer_boundary() -> None:
    policy = SourceUrlPolicy(issuer_hosts=("acme.github.io",))

    assert (
        policy.validate_url("https://investor.acme.github.io/results").hostname
        == "investor.acme.github.io"
    )
    with pytest.raises(SourcePolicyError) as error:
        policy.validate_url("https://investor.attacker.github.io/results")

    assert error.value.code == "SOURCE_URL_HOST_FORBIDDEN"


def test_normalizes_idna_hostname_against_sec_registered_host() -> None:
    policy = SourceUrlPolicy(issuer_hosts=("m\u00fcnich.com",))

    validated = policy.validate_url("https://M\u00dcNICH.com/investors")

    assert validated.hostname == "xn--mnich-kva.com"
    assert validated.normalized_url == "https://xn--mnich-kva.com/investors"
    assert validated.registrable_domain == "xn--mnich-kva.com"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.8",
        "169.254.169.254",
        "224.0.0.1",
        "192.0.2.1",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "2001:db8::1",
        "::",
    ],
)
async def test_dns_gate_rejects_every_unsafe_address_class(address: str) -> None:
    resolver = Resolver({"apple.com": (address,)})

    with pytest.raises(SourcePolicyError) as error:
        await issuer_policy().authorize("https://apple.com/report", resolver)

    assert error.value.code == "SOURCE_DNS_UNSAFE"
    assert resolver.calls == ["apple.com"]


@pytest.mark.anyio
async def test_dns_gate_rejects_mixed_public_and_unsafe_answers() -> None:
    resolver = Resolver({"apple.com": ("93.184.216.34", "127.0.0.1")})

    with pytest.raises(SourcePolicyError) as error:
        await issuer_policy().authorize("https://apple.com/report", resolver)

    assert error.value.code == "SOURCE_DNS_UNSAFE"


@pytest.mark.anyio
async def test_dns_failure_has_safe_stable_error() -> None:
    secret = "resolver-secret-token"

    class FailingResolver:
        async def resolve(self, hostname: str) -> tuple[str, ...]:
            raise OSError(secret)

    with pytest.raises(SourcePolicyError) as error:
        await issuer_policy().authorize(
            "https://apple.com/report",
            FailingResolver(),
        )

    assert error.value.code == "SOURCE_DNS_FAILURE"
    formatted = "".join(
        traceback.format_exception(
            type(error.value),
            error.value,
            error.value.__traceback__,
        )
    )
    assert secret not in formatted
    assert error.value.__cause__ is None


@pytest.mark.anyio
async def test_redirect_revalidates_target_before_request() -> None:
    resolver = Resolver({"apple.com": ("93.184.216.34",)})
    policy = issuer_policy()
    current = await policy.authorize("https://apple.com/report", resolver)

    with pytest.raises(SourcePolicyError) as error:
        await policy.authorize_redirect(
            current=current,
            location="http://127.0.0.1/admin",
            redirect_count=1,
            resolver=resolver,
        )

    assert error.value.code == "SOURCE_URL_SCHEME_UNSUPPORTED"
    assert resolver.calls == ["apple.com"]


@pytest.mark.anyio
async def test_redirect_resolves_relative_location_and_reruns_dns_gate() -> None:
    resolver = Resolver({"apple.com": ("93.184.216.34",)})
    policy = issuer_policy()
    current = await policy.authorize("https://apple.com/reports/2025", resolver)

    redirected = await policy.authorize_redirect(
        current=current,
        location="../2026#section",
        redirect_count=1,
        resolver=resolver,
    )

    assert redirected.normalized_url == "https://apple.com/2026"
    assert resolver.calls == ["apple.com", "apple.com"]


@pytest.mark.anyio
async def test_redirect_limit_is_three() -> None:
    resolver = Resolver({"apple.com": ("93.184.216.34",)})
    policy = issuer_policy()
    current = await policy.authorize("https://apple.com/report", resolver)

    with pytest.raises(SourcePolicyError) as error:
        await policy.authorize_redirect(
            current=current,
            location="/fourth",
            redirect_count=4,
            resolver=resolver,
        )

    assert error.value.code == "SOURCE_REDIRECT_LIMIT"
    assert resolver.calls == ["apple.com"]


@pytest.mark.anyio
async def test_pinned_network_backend_connects_to_the_validated_address() -> None:
    resolver = PinningHostResolver(Resolver({"apple.com": ("93.184.216.34",)}))
    await resolver.resolve("apple.com")

    class Backend:
        def __init__(self) -> None:
            self.hosts: list[str] = []
            self.stream = object()

        async def connect_tcp(self, host: str, port: int, **kwargs):
            self.hosts.append(host)
            return self.stream

        async def sleep(self, seconds: float) -> None:
            return None

    underlying = Backend()
    backend = PinnedNetworkBackend(resolver, backend=underlying)

    stream = await backend.connect_tcp("apple.com", 443)

    assert stream is underlying.stream
    assert underlying.hosts == ["93.184.216.34"]


@pytest.mark.anyio
async def test_pinned_network_backend_rejects_an_unvalidated_hostname() -> None:
    resolver = PinningHostResolver(Resolver({"apple.com": ("93.184.216.34",)}))

    class Backend:
        async def connect_tcp(self, host: str, port: int, **kwargs):
            raise AssertionError("connection should be blocked before the backend")

        async def sleep(self, seconds: float) -> None:
            return None

    backend = PinnedNetworkBackend(resolver, backend=Backend())

    with pytest.raises(httpcore.ConnectError, match="SOURCE_DNS_PIN_MISSING"):
        await backend.connect_tcp("apple.com", 443)


def test_public_suffix_extractor_is_offline_only() -> None:
    assert PUBLIC_SUFFIX_EXTRACTOR.suffix_list_urls == ()
    assert PUBLIC_SUFFIX_EXTRACTOR(
        "investor.apple.com"
    ).top_domain_under_public_suffix == ("apple.com")
