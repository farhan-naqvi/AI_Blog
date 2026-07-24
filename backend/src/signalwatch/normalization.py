import hashlib
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dateutil import parser as date_parser

TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
}
TRACKING_PREFIXES = ("utm_",)


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("URL must be absolute HTTP(S)")
    host = parts.hostname.lower()
    port = parts.port
    netloc = host if port is None or (parts.scheme == "https" and port == 443) or (
        parts.scheme == "http" and port == 80
    ) else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_KEYS
            and not key.lower().startswith(TRACKING_PREFIXES)
        ),
        doseq=True,
    )
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def content_fingerprint(title: str, excerpt: str) -> str:
    normalized = f"{normalize_title(title).casefold()}\n{re.sub(r'\s+', ' ', excerpt).strip().casefold()}"
    return stable_hash(normalized)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = date_parser.parse(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
