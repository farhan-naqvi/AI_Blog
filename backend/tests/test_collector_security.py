from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from signalwatch.collectors.arxiv import ArxivCollector
from signalwatch.collectors.base import (
    JSON_CONTENT_TYPES,
    CollectorContentTypeError,
    CollectorRateLimitError,
    CollectorRedirectError,
    CollectorResponseTooLarge,
    fetch_bounded_response,
    parse_retry_after,
)
from signalwatch.collectors.github import GitHubCollector
from signalwatch.collectors.huggingface import HuggingFaceCollector
from signalwatch.collectors.rss import RssCollector
from signalwatch.models import SourceRecord

RSS = b'<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title></channel></rss>'
ATOM = b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'


def source(key: str, base_url: str, config: dict | None = None) -> SourceRecord:
    return SourceRecord(
        id="1",
        name="Test",
        base_url=base_url,
        source_type="Test",
        retrieval_method="API" if key != "rss" else "RSS",
        connector_key=key,
        connector_config=config or {},
        is_primary_source=True,
        reliability_level="High",
        poll_interval_minutes=60,
        rate_limit_per_hour=20,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("collector", "configured_source"),
    [
        (GitHubCollector(), source("github", "https://github.com", {"repository": "acme/repo"})),
        (ArxivCollector(), source("arxiv", "https://arxiv.org", {"categories": ["cs.AI"]})),
        (HuggingFaceCollector(), source("huggingface", "https://huggingface.co", {"author": "acme"})),
        (RssCollector(), source("rss", "https://93.184.216.34/feed.xml")),
    ],
)
async def test_collectors_reject_invalid_content_types(collector, configured_source) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"not expected", headers={"content-type": "text/html"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CollectorContentTypeError):
            await collector.collect(configured_source, client)


@pytest.mark.asyncio
async def test_arxiv_accepts_atom_content_type() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=ATOM, headers={"content-type": "application/atom+xml"}
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await ArxivCollector(max_items=1).collect(
            source("arxiv", "https://arxiv.org", {"categories": ["cs.AI"]}), client
        )
    assert result.items == []


class ChunkedBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"["
        yield b" " * 8
        yield b"]"

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_declared_and_chunked_oversized_responses_are_rejected() -> None:
    declared = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"[]",
            headers={"content-type": "application/json", "content-length": "11"},
        )
    )
    async with httpx.AsyncClient(transport=declared) as client:
        with pytest.raises(CollectorResponseTooLarge):
            await fetch_bounded_response(
                client,
                "https://example.com/api",
                connector="github",
                allowed_content_types=JSON_CONTENT_TYPES,
                expected_kind="json",
                max_bytes=10,
            )

    chunked = httpx.MockTransport(
        lambda request: httpx.Response(
            200, stream=ChunkedBody(), headers={"content-type": "application/json"}
        )
    )
    async with httpx.AsyncClient(transport=chunked) as client:
        with pytest.raises(CollectorResponseTooLarge):
            await fetch_bounded_response(
                client,
                "https://example.com/api",
                connector="github",
                allowed_content_types=JSON_CONTENT_TYPES,
                expected_kind="json",
                max_bytes=5,
            )


def test_retry_after_seconds_http_date_and_malformed_values() -> None:
    now = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    assert parse_retry_after("3", now=now) == 3
    assert parse_retry_after(format_datetime(now + timedelta(seconds=9)), now=now) == 9
    assert parse_retry_after("later", now=now) is None
    assert parse_retry_after(None, now=now) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "headers", "expected_wait"),
    [
        (429, {"retry-after": "2"}, 2.0),
        (
            429,
            {"retry-after": format_datetime(datetime.now(UTC) + timedelta(minutes=1))},
            5.0,
        ),
        (429, {}, 1.0),
        (429, {"retry-after": "invalid"}, 1.0),
        (429, {"retry-after": "999"}, 5.0),
        (403, {"x-ratelimit-remaining": "0"}, 1.0),
    ],
)
async def test_rate_limits_retry_with_bounded_wait(
    monkeypatch, status, headers, expected_wait
) -> None:
    calls = 0
    waits = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status, headers=headers)
        return httpx.Response(200, json=[])

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("signalwatch.collectors.base.asyncio.sleep", fake_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_bounded_response(
            client,
            "https://api.github.com/repos/acme/repo/releases",
            connector="github",
            allowed_content_types=JSON_CONTENT_TYPES,
            expected_kind="json",
        )
    assert result.status_code == 200
    assert waits == [expected_wait]


@pytest.mark.asyncio
async def test_rate_limit_attempts_are_bounded(monkeypatch) -> None:
    waits = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("signalwatch.collectors.base.asyncio.sleep", fake_sleep)
    transport = httpx.MockTransport(lambda request: httpx.Response(429))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CollectorRateLimitError):
            await fetch_bounded_response(
                client,
                "https://api.github.com/repos/acme/repo/releases",
                connector="github",
                allowed_content_types=JSON_CONTENT_TYPES,
                expected_kind="json",
                max_attempts=3,
            )
    assert waits == [1.0, 2.0]


@pytest.mark.asyncio
async def test_rss_safe_cross_host_redirect_strips_authorization() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "https://1.1.1.1/feed.xml"})
        assert "authorization" not in request.headers
        return httpx.Response(200, content=RSS, headers={"content-type": "application/rss+xml"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await fetch_bounded_response(
            client,
            "https://93.184.216.34/feed.xml",
            connector="rss",
            headers={"authorization": "Bearer test-only"},
            allowed_content_types=("application/rss+xml",),
            expected_kind="xml",
            validate_redirects=True,
        )
    assert response.status_code == 200
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", ["http://127.0.0.1/feed", "http://10.0.0.1/feed"])
async def test_rss_rejects_local_and_private_redirects(destination: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": destination})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CollectorRedirectError, match="not public"):
            await RssCollector().collect(
                source("rss", "https://93.184.216.34/feed.xml"), client
            )


@pytest.mark.asyncio
async def test_rss_rejects_redirect_loop() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": str(request.url)})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CollectorRedirectError, match="loop"):
            await RssCollector().collect(
                source("rss", "https://93.184.216.34/feed.xml"), client
            )


@pytest.mark.asyncio
async def test_rss_enforces_redirect_limit() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": f"/feed-{calls}.xml"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CollectorRedirectError, match="limit"):
            await RssCollector().collect(
                source("rss", "https://93.184.216.34/feed.xml"), client
            )
    assert calls == 4
