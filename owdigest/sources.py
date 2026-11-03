"""Загрузка и разбор источников: страницы Blizzard и RSS/Atom."""

from __future__ import annotations

import html as _html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from . import util


@dataclass
class Item:
    uid: str
    source: str
    title: str
    url: str
    summary: str = ""
    image: str = ""
    published: datetime | None = None
    lang: str = "en"
    weight: int = 1
    order: int = 0
    category: str = "news"

    def sort_key(self) -> str:
        return util.iso(self.published) or ""


# ── Общее ───────────────────────────────────────────────────────────────────


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    return urlunparse((p.scheme, p.netloc.lower().replace("www.", ""), p.path.rstrip("/"), "", "", ""))


# ── Blizzard ────────────────────────────────────────────────────────────────

# Карточки отдаются сервером: ссылка, картинка и (иногда) alt-заголовок.
_BLIZZ_CARD = re.compile(
    r'class="news-card-link"\s+href="(/([a-z]{2}-[a-z]{2})/article/(\d+)/[^"]+)"'
)
_BLIZZ_IMAGE = re.compile(r"<blz-image\b[^>]*>", re.I)


def parse_blizzard(text: str, *, source_id: str, lang: str, weight: int,
                   base: str = "https://news.blizzard.com") -> list[Item]:
    cards = list(_BLIZZ_CARD.finditer(text))
    out: list[Item] = []
    for idx, match in enumerate(cards):
        path, _locale, article_id = match.group(1), match.group(2), match.group(3)
        end = cards[idx + 1].start() if idx + 1 < len(cards) else min(len(text), match.end() + 200_000)
        window = text[match.end():end]

        image, alt = "", ""
        tag = _BLIZZ_IMAGE.search(window)
        if tag:
            src = re.search(r'\bsrc="([^"]+)"', tag.group(0))
            alt_m = re.search(r'\balt="([^"]*)"', tag.group(0))
            image = src.group(1) if src else ""
            alt = util.clean_text(_html.unescape(alt_m.group(1))) if alt_m else ""

        title = alt or path.rsplit("/", 1)[-1].replace("-", " ").title()
        out.append(
            Item(
                uid=f"blizzard:{article_id}",
                source=source_id,
                title=title,
                url=base + path,
                image=image,
                lang=lang,
                weight=weight,
                order=idx,
            )
        )
    return out


def _meta(html_text: str, prop: str) -> str:
    pattern = re.compile(
        rf'<meta[^>]+property="{re.escape(prop)}"[^>]+content="([^"]*)"', re.I
    )
    m = pattern.search(html_text)
    if not m:
        pattern = re.compile(
            rf'<meta[^>]+content="([^"]*)"[^>]+property="{re.escape(prop)}"', re.I
        )
        m = pattern.search(html_text)
    return util.clean_text(_html.unescape(m.group(1))) if m else ""


_TITLE_SUFFIX = re.compile(
    r"(?:\s+[—|]\s+(?:Overwatch 2|Blizzard News|Новости Blizzard|Inside Blizzard|BlizzCon))+$",
    re.I,
)


def enrich_blizzard(item: Item) -> Item:
    """Дозагружает страницу статьи: точную дату, описание и картинку."""
    try:
        raw, content_type = util.http_get(item.url)
    except util.FetchError:
        return item

    page = util.decode(raw, content_type)

    title = _meta(page, "og:title")
    if title:
        cleaned = _TITLE_SUFFIX.sub("", title).strip()
        if cleaned:
            item.title = cleaned

    description = _meta(page, "og:description")
    if description and len(description) > len(item.summary):
        item.summary = description

    image = _meta(page, "og:image")
    if image:
        item.image = image

    for blob in re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S | re.I
    ):
        try:
            data = json.loads(blob)
        except (json.JSONDecodeError, ValueError):
            continue
        for obj in data if isinstance(data, list) else [data]:
            if not isinstance(obj, dict):
                continue
            kind = obj.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if any(k in ("NewsArticle", "Article", "BlogPosting") for k in kinds):
                published = util.parse_date(obj.get("datePublished"))
                if published:
                    item.published = published
        if item.published:
            break

    return item


# ── RSS / Atom ──────────────────────────────────────────────────────────────


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(node: ET.Element, name: str) -> ET.Element | None:
    for child in node:
        if _local(child.tag) == name:
            return child
    return None


def _text(node: ET.Element, name: str) -> str:
    child = _find(node, name)
    return (child.text or "").strip() if child is not None and child.text else ""


def _link(node: ET.Element) -> str:
    for child in node:
        if _local(child.tag) != "link":
            continue
        href = child.get("href")
        if href:
            return href.strip()
        if child.text:
            return child.text.strip()
    return ""


_IMG_IN_TEXT = re.compile(r'<img[^>]+src="([^"]+)"', re.I)


def _first_image(node: ET.Element, raw_summary: str) -> str:
    for child in node:
        if _local(child.tag) not in ("enclosure", "content", "thumbnail"):
            continue
        url = child.get("url") or child.get("href")
        kind = (child.get("type") or "").lower()
        if not url:
            continue
        if kind and not kind.startswith("image"):
            continue
        if not kind and not re.search(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", url, re.I):
            continue
        return url
    m = _IMG_IN_TEXT.search(raw_summary or "")
    return _html.unescape(m.group(1)) if m else ""


def parse_feed(raw: bytes, *, source_id: str, weight: int) -> list[Item]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        root = ET.fromstring(util.decode(raw).encode("utf-8"))

    items: list[Item] = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue

        title = util.clean_text(_text(node, "title"))
        link = _link(node)
        if not title or not link:
            continue

        raw_summary = (
            _text(node, "description")
            or _text(node, "summary")
            or _text(node, "encoded")
            or _text(node, "content")
        )
        summary = util.clean_text(raw_summary, limit=320)
        published = util.parse_date(
            _text(node, "pubDate") or _text(node, "published") or _text(node, "updated")
        )
        guid = _text(node, "guid") or _text(node, "id") or link

        items.append(
            Item(
                uid=f"{source_id}:{util.short_hash(normalize_url(link) or guid, 12)}",
                source=source_id,
                title=title,
                url=link,
                summary=summary,
                image=_first_image(node, raw_summary),
                published=published,
                weight=weight,
                order=len(items),
            )
        )
    return items


# ── Сбор ────────────────────────────────────────────────────────────────────


def fetch_source(source: dict) -> list[Item]:
    raw, content_type = util.http_get(source["url"])
    if source["type"] == "blizzard":
        text = util.decode(raw, content_type)
        return parse_blizzard(
            text,
            source_id=source["id"],
            lang=source.get("lang", "en"),
            weight=source.get("weight", 1),
        )

    items = parse_feed(raw, source_id=source["id"], weight=source.get("weight", 1))
    needle = (source.get("filter") or "").lower()
    if needle:
        items = [i for i in items if needle in f"{i.title} {i.summary}".lower()]
    return items


def merge_duplicates(items: list[Item]) -> list[Item]:
    """Склеивает EN/RU версии статьи Blizzard (один uid) в одну запись."""
    merged: dict[str, Item] = {}
    for item in items:
        current = merged.get(item.uid)
        if current is None:
            merged[item.uid] = item
            continue
        # Английская версия приоритетнее, русская закрывает пробелы.
        if current.lang != "en" and item.lang == "en":
            item.summary = item.summary or current.summary
            item.image = item.image or current.image
            item.weight = max(item.weight, current.weight)
            merged[item.uid] = item
        else:
            current.summary = current.summary or item.summary
            current.image = current.image or item.image
            current.weight = max(current.weight, item.weight)
    return list(merged.values())


def dedupe_titles(items: list[Item]) -> list[Item]:
    """Убирает один и тот же материал, пришедший из разных изданий."""
    seen: dict[str, Item] = {}
    for item in items:
        key = re.sub(r"[^0-9a-zа-я]+", "", item.title.lower())[:70]
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            seen[key] = item
            continue
        # Оставляем версию с более полными данными и весом.
        if (item.weight, bool(item.image), len(item.summary)) > (
            existing.weight,
            bool(existing.image),
            len(existing.summary),
        ):
            seen[key] = item
    return list(seen.values())
