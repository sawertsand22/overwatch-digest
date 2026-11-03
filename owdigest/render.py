"""Сборка сводки: Markdown для GitHub Issue и HTML-архив."""

from __future__ import annotations

import html as _html
from datetime import datetime

from . import classify
from .sources import Item

SOURCE_NAMES = {
    "blizzard_en": "Blizzard",
    "blizzard_ru": "Blizzard",
    "dexerto": "Dexerto",
    "eurogamer": "Eurogamer",
    "pcgamer": "PC Gamer",
    "googlenews": "Google News",
}


def _md(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("|", "\\|")
    )


def _date(dt: datetime | None) -> str:
    return dt.strftime("%d.%m.%Y") if dt else "—"


def _source_name(item: Item) -> str:
    return SOURCE_NAMES.get(item.source, item.source)


def _grouped(items: list[Item]) -> list[tuple[str, list[Item]]]:
    groups = []
    for category in classify.ORDER:
        chunk = [i for i in items if i.category == category]
        if chunk:
            groups.append((category, chunk))
    return groups


def render_markdown(
    items: list[Item],
    *,
    reference: datetime,
    images: dict[str, str],
    total_found: int,
    failures: list[str],
    baseline: bool,
    image_mode: str = "remote",
) -> str:
    """image_mode: "remote" — ссылки на оригинал (для Issue),
    "local" — пути внутри репозитория (для архива)."""

    lines: list[str] = []
    header = reference.strftime("%d.%m.%Y %H:%M UTC")
    label = "стартовый срез" if baseline else f"новых материалов: {len(items)}"
    lines.append(f"**Сформировано:** {header} · {label} · найдено всего: {total_found}")
    lines.append("")

    if items:
        lines.append("### Главное")
        for item in items[:3]:
            lines.append(f"- [{_md(item.title)}]({item.url})")
        lines.append("")

    for category, chunk in _grouped(items):
        lines.append(f"## {classify.LABELS[category]}")
        lines.append("")
        for item in chunk:
            lines.append(f"### [{_md(item.title)}]({item.url})")
            if item.summary:
                lines.append(_md(item.summary))
                lines.append("")
            if image_mode == "local":
                # Архив лежит в digests/, картинки — в ../images/
                image = images.get(item.uid)
                image = f"../{image}" if image else item.image
            else:
                image = item.image
            if image:
                lines.append(f'<img src="{_html.escape(image)}" width="520" alt="">')
                lines.append("")
            meta_bits = [f"`{_source_name(item)}`", _date(item.published)]
            lines.append("<sub>" + " · ".join(meta_bits) + "</sub>")
            lines.append("")

    if failures:
        lines.append("---")
        lines.append(f"<sub>⚠️ Не ответили источники: {', '.join(failures)}</sub>")
        lines.append("")

    if not items:
        lines.append("_Новых материалов за период не найдено. Следующая проверка — через 12 часов._")
        lines.append("")

    lines.append("<sub>🤖 Собирается автоматически · архив: `digests/`</sub>")
    return "\n".join(lines)


_HTML_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Overwatch — сводка {stamp}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 32px 16px 64px; background: #101015; color: #e8e8ef;
         font: 16px/1.55 -apple-system, "Segoe UI", Roboto, sans-serif; }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  h1 {{ font-size: 26px; margin: 0 0 6px; }}
  .sub {{ color: #8b8b9e; font-size: 14px; margin-bottom: 28px; }}
  h2 {{ font-size: 19px; margin: 36px 0 14px; padding-bottom: 8px;
        border-bottom: 1px solid #26262f; }}
  .card {{ display: grid; grid-template-columns: 220px 1fr; gap: 18px;
           padding: 16px; margin-bottom: 14px; border-radius: 12px;
           background: #17171f; border: 1px solid #24242e; }}
  .card img {{ width: 100%; height: 100%; max-height: 150px; object-fit: cover;
               border-radius: 8px; background: #0c0c10; }}
  .card.noimg {{ grid-template-columns: 1fr; }}
  .card h3 {{ margin: 0 0 8px; font-size: 17px; line-height: 1.35; }}
  .card h3 a {{ color: #f5f5fa; text-decoration: none; }}
  .card h3 a:hover {{ color: #ff8f3f; }}
  .card p {{ margin: 0 0 10px; color: #b9b9c8; font-size: 14px; }}
  .meta {{ color: #7a7a8c; font-size: 12.5px; }}
  .top {{ margin: 0 0 8px; padding-left: 20px; }}
  .top a {{ color: #ffb37a; }}
  .fail {{ color: #d98b6a; font-size: 13px; margin-top: 32px; }}
  @media (max-width: 640px) {{ .card {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body><div class="wrap">
<h1>🟠 Overwatch — сводка</h1>
<div class="sub">{stamp} · {label} · найдено всего: {total}</div>
{top}
{body}
{failures}
</div></body></html>
"""


def _card(item: Item, image: str) -> str:
    img = (
        f'<img src="{_html.escape(image)}" alt="" loading="lazy">' if image else ""
    )
    summary = f"<p>{_html.escape(item.summary)}</p>" if item.summary else ""
    return (
        f'<article class="card{" noimg" if not img else ""}">{img}<div>'
        f'<h3><a href="{_html.escape(item.url)}" target="_blank" rel="noopener">'
        f"{_html.escape(item.title)}</a></h3>"
        f"{summary}"
        f'<div class="meta">{_html.escape(_source_name(item))} · {_date(item.published)}</div>'
        f"</div></article>"
    )


def render_html(
    items: list[Item],
    *,
    reference: datetime,
    images: dict[str, str],
    total_found: int,
    failures: list[str],
    baseline: bool,
) -> str:
    stamp = reference.strftime("%d.%m.%Y %H:%M UTC")
    label = "стартовый срез" if baseline else f"новых материалов: {len(items)}"

    top = ""
    if items:
        links = "".join(
            f'<li><a href="{_html.escape(i.url)}" target="_blank" rel="noopener">'
            f"{_html.escape(i.title)}</a></li>"
            for i in items[:3]
        )
        top = f'<ol class="top">{links}</ol>'

    body: list[str] = []
    for category, chunk in _grouped(items):
        body.append(f"<h2>{classify.LABELS[category]}</h2>")
        for item in chunk:
            body.append(_card(item, images.get(item.uid, "")))

    failures_html = (
        f'<p class="fail">⚠️ Источники без ответа: {_html.escape(", ".join(failures))}</p>'
        if failures
        else ""
    )

    return _HTML_TEMPLATE.format(
        stamp=stamp,
        label=label,
        total=total_found,
        top=top,
        body="\n".join(body) or "<p><em>Новых материалов нет.</em></p>",
        failures=failures_html,
    )
