"""Мелкие утилиты: сеть, текст, даты, слаги."""

from __future__ import annotations

import gzip
import hashlib
import html as _html
import re
import time
import zlib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class FetchError(Exception):
    pass


def http_get(url: str, *, timeout: int = 30, retries: int = 2) -> tuple[bytes, str]:
    """GET с ретраями и распаковкой. Возвращает (тело, content-type)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if enc == "gzip":
                    raw = gzip.decompress(raw)
                elif enc == "deflate":
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                return raw, resp.headers.get("Content-Type", "")
        except Exception as exc:  # noqa: BLE001 — ретраим любые сетевые сбои
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"{url} → {last}")


def decode(raw: bytes, content_type: str = "") -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    candidates = []
    if m:
        candidates.append(m.group(1))
    candidates += ["utf-8", "cp1251", "windows-1252", "latin-1"]
    for enc in candidates:
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def clean_text(value: str | None, limit: int | None = None) -> str:
    if not value:
        return ""
    text = _html.unescape(_TAG_RE.sub(" ", value))
    text = _WS_RE.sub(" ", text).strip()
    if limit and len(text) > limit:
        cut = text[:limit]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut.rstrip(" ,.;:-—") + "…"
    return text


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    dt: datetime | None = None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        pass
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now() -> datetime:
    return datetime.now(timezone.utc)


def short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha1(value.encode("utf-8", "replace")).hexdigest()[:length]


def slugify(value: str, limit: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    if not slug:
        slug = short_hash(value or "item", 10)
    return slug[:limit].strip("-")
