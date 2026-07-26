import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

from ..models import CollectedItem, SourceRecord
from ..security import validate_public_url

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_RATE_LIMIT_WAIT_SECONDS = 5.0
MAX_RATE_LIMIT_ATTEMPTS = 3

JSON_CONTENT_TYPES = (
    "application/json",
    "application/vnd.github+json",
)
XML_CONTENT_TYPES = (
    "application/atom+xml",
    "application/rss+xml",
    "application/xml",
    "text/xml",
)


class CollectorError(RuntimeError):
    pass


class CollectorResponseError(CollectorError, httpx.HTTPError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CollectorParseError(CollectorError):
    pass


class CollectorContentTypeError(CollectorError):
    pass


class CollectorResponseTooLarge(CollectorError):
    pass


class CollectorRateLimitError(CollectorError):
    pass


class CollectorRedirectError(CollectorError):
    pass


@dataclass
class CollectionResult:
    items: list[CollectedItem] = field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    discovered_count: int | None = None
    filtered_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class BoundedResponse:
    status_code: int
    content: bytes
    headers: httpx.Headers

    def json(self):
        try:
            return json.loads(self.content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorParseError("collector returned invalid JSON") from exc


class Collector(Protocol):
    key: str

    async def collect(self, source: SourceRecord, client: httpx.AsyncClient) -> CollectionResult:
        ...


def conditional_headers(source: SourceRecord) -> dict[str, str]:
    headers = {"user-agent": "SignalWatch/0.1 (+owner-operated AI monitoring)"}
    if source.etag:
        headers["if-none-match"] = source.etag
    if source.last_modified:
        headers["if-modified-since"] = source.last_modified
    return headers


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.isdigit():
        return float(cleaned)
    try:
        parsed = parsedate_to_datetime(cleaned)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    reference = now or datetime.now(UTC)
    return max(0.0, (parsed.astimezone(UTC) - reference).total_seconds())


def _content_type_allowed(content_type: str, allowed: tuple[str, ...]) -> bool:
    if content_type in allowed:
        return True
    if content_type.endswith("+json") and any(item.endswith("json") for item in allowed):
        return True
    return content_type.endswith("+xml") and any(item.endswith("xml") for item in allowed)


def _sniffed_type_allowed(content: bytes, expected_kind: str) -> bool:
    prefix = content.lstrip()[:32]
    if expected_kind == "json":
        return prefix.startswith((b"{", b"["))
    return prefix.startswith(b"<?xml") or prefix.startswith((b"<rss", b"<feed"))


async def _open_response(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict | None,
    validate_redirects: bool,
    max_redirects: int,
) -> httpx.Response:
    current = validate_public_url(url) if validate_redirects else url
    current_headers = dict(headers)
    current_params = params
    visited = {current}
    for redirect_count in range(max_redirects + 1):
        request = client.build_request("GET", current, headers=current_headers, params=current_params)
        response = await client.send(request, stream=True)
        current_params = None
        if response.status_code == 304 or not response.is_redirect:
            return response
        location = response.headers.get("location")
        await response.aclose()
        if not location:
            raise CollectorRedirectError("redirect has no location")
        if redirect_count >= max_redirects:
            raise CollectorRedirectError("redirect limit exceeded")
        destination = urljoin(str(request.url), location)
        if validate_redirects:
            try:
                destination = validate_public_url(destination)
            except ValueError as exc:
                raise CollectorRedirectError("redirect destination is not public") from exc
        if destination in visited:
            raise CollectorRedirectError("redirect loop detected")
        visited.add(destination)
        if urlsplit(destination).hostname != urlsplit(str(request.url)).hostname:
            current_headers.pop("authorization", None)
        current = destination
    raise CollectorRedirectError("redirect limit exceeded")


async def fetch_bounded_response(
    client: httpx.AsyncClient,
    url: str,
    *,
    connector: str,
    headers: dict[str, str] | None = None,
    params: dict | None = None,
    allowed_content_types: tuple[str, ...],
    expected_kind: str,
    max_bytes: int = MAX_RESPONSE_BYTES,
    max_attempts: int = MAX_RATE_LIMIT_ATTEMPTS,
    max_rate_wait: float = MAX_RATE_LIMIT_WAIT_SECONDS,
    validate_redirects: bool = False,
    max_redirects: int = 3,
) -> BoundedResponse:
    request_headers = headers or {}
    for attempt in range(max(1, max_attempts)):
        response = await _open_response(
            client,
            url,
            headers=request_headers,
            params=params,
            validate_redirects=validate_redirects,
            max_redirects=max_redirects,
        )
        try:
            rate_limited = response.status_code == 429 or (
                connector == "github"
                and response.status_code == 403
                and response.headers.get("x-ratelimit-remaining") == "0"
            )
            if rate_limited:
                wait = parse_retry_after(response.headers.get("retry-after"))
                reset = response.headers.get("x-ratelimit-reset")
                if wait is None and reset and reset.isdigit():
                    wait = max(0.0, float(reset) - datetime.now(UTC).timestamp())
                wait = min(wait if wait is not None else float(2**attempt), max_rate_wait)
                if attempt + 1 >= max(1, max_attempts):
                    raise CollectorRateLimitError(f"{connector} rate limit exhausted")
                logger.warning(
                    "collector_rate_limited",
                    extra={
                        "subsystem": f"collector:{connector}",
                        "category": "rate_limit",
                        "wait_seconds": round(wait, 2),
                    },
                )
                await asyncio.sleep(wait)
                continue
            if response.status_code == 304:
                return BoundedResponse(response.status_code, b"", response.headers)
            if response.is_error or response.is_redirect:
                raise CollectorResponseError(
                    f"{connector} returned HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            declared_length = response.headers.get("content-length")
            if declared_length and declared_length.isdigit() and int(declared_length) > max_bytes:
                raise CollectorResponseTooLarge(f"{connector} response exceeds maximum size")
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type and not _content_type_allowed(content_type, allowed_content_types):
                raise CollectorContentTypeError(
                    f"{connector} returned unsupported content type"
                )
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise CollectorResponseTooLarge(f"{connector} response exceeds maximum size")
                chunks.append(chunk)
            content = b"".join(chunks)
            if not content_type and not _sniffed_type_allowed(content, expected_kind):
                raise CollectorContentTypeError(
                    f"{connector} response has no trustworthy content type"
                )
            return BoundedResponse(response.status_code, content, response.headers)
        finally:
            await response.aclose()
    raise CollectorRateLimitError(f"{connector} rate limit exhausted")
