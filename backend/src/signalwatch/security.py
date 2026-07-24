import ipaddress
import socket
from urllib import robotparser
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

MAX_SOURCE_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")


def validate_public_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("only absolute HTTP(S) source URLs are allowed")
    if parts.username or parts.password:
        raise ValueError("source URL credentials are not allowed")
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("source hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("source URL resolves to a private or reserved address")
    return url


@asynccontextmanager
async def safe_stream(
    client: httpx.AsyncClient, url: str, *, max_redirects: int = 3
) -> AsyncIterator[httpx.Response]:
    current = validate_public_url(url)
    response: httpx.Response | None = None
    for _ in range(max_redirects + 1):
        response = await client.send(
            client.build_request("GET", current, headers={"user-agent": "SignalWatch/0.1"}),
            stream=True,
        )
        if response.is_redirect:
            location = response.headers.get("location")
            await response.aclose()
            if not location:
                raise ValueError("redirect has no location")
            current = validate_public_url(urljoin(current, location))
            continue
        break
    else:
        raise ValueError("too many redirects")
    assert response is not None
    try:
        yield response
    finally:
        await response.aclose()


async def fetch_readable_text(client: httpx.AsyncClient, url: str) -> str:
    if not await robots_allows(client, url):
        raise ValueError("source robots policy does not allow automated retrieval")
    async with safe_stream(client, url) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"unsupported source content type: {content_type}")
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_SOURCE_BYTES:
                raise ValueError("source response exceeds maximum size")
            chunks.append(chunk)
    raw = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    extracted = trafilatura.extract(
        raw, include_comments=False, include_tables=False, favor_precision=True
    )
    text = (extracted or raw).strip()
    return text[:40_000]


async def robots_allows(client: httpx.AsyncClient, url: str) -> bool:
    parts = urlsplit(validate_public_url(url))
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    async with safe_stream(client, robots_url) as response:
        if response.status_code == 404:
            return True
        if response.status_code in {401, 403}:
            return False
        response.raise_for_status()
        body = (await response.aread())[:256_000].decode(response.encoding or "utf-8", errors="replace")
    policy = robotparser.RobotFileParser()
    policy.set_url(robots_url)
    policy.parse(body.splitlines())
    return policy.can_fetch("SignalWatch/0.1", url)
