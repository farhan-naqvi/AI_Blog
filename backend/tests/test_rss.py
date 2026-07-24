import httpx
import pytest

from signalwatch.collectors.rss import RssCollector
from signalwatch.models import SourceRecord

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title><item><guid>abc</guid><title>Important model release</title><link>https://example.com/post?utm_source=rss</link><description>Official release details.</description><pubDate>Tue, 20 Jan 2026 10:00:00 GMT</pubDate></item></channel></rss>"""


@pytest.mark.asyncio
async def test_rss_parsing_and_normalization() -> None:
    source = SourceRecord(id="1", name="Test", base_url="https://example.com/feed.xml", source_type="Official", retrieval_method="RSS", connector_key="rss", is_primary_source=True, reliability_level="High", poll_interval_minutes=60, rate_limit_per_hour=20)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=RSS, headers={"etag": "abc"}))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await RssCollector().collect(source, client)
    assert len(result.items) == 1
    assert str(result.items[0].canonical_url) == "https://example.com/post"
    assert result.items[0].source_identifier == "abc"
    assert result.etag == "abc"


@pytest.mark.asyncio
async def test_rss_conditional_not_modified() -> None:
    source = SourceRecord(id="1", name="Test", base_url="https://example.com/feed.xml", source_type="Official", retrieval_method="RSS", connector_key="rss", is_primary_source=True, reliability_level="High", poll_interval_minutes=60, rate_limit_per_hour=20, etag="old")
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["if-none-match"] == "old"
        return httpx.Response(304)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RssCollector().collect(source, client)
    assert result.not_modified
