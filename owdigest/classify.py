"""Классификация материала: герой / скин / событие / киберспорт / прочее."""

from __future__ import annotations

import re
from datetime import datetime

from .sources import Item

# Порядок важен: первая подошедшая категория побеждает.
RULES: list[tuple[str, int, list[str]]] = [
    (
        "hero",
        40,
        [
            r"\bnew\s+hero(?:es)?\b",
            r"\bhero(?:es)?\s+reveal\b",
            r"\breveal(?:s|ed)?\s+(?:a|the)\s+new\s+hero\b",
            r"\bjoins?\s+(?:the\s+)?(?:hero\s+)?roster\b",
            r"\bnew\s+(?:tank|support|damage|dps)\s+hero\b",
            r"\bnewest\s+(?:\w+\s+){0,3}hero\b",
            r"\bhero\s+(?:enters?|arrives?|debuts?|joins?)\b",
            r"\bplayable\s+(?:hero|character)\b",
            r"\bhero\s+rework\b",
            r"\bнов(?:ый|ого|ые|ая)\s+геро",
            r"\bгеро[йя]\s+(?:вступает|появится|дебютирует)",
        ],
    ),
    (
        "skin",
        25,
        [
            r"\bskins?\b",
            r"\bmythic\b",
            r"\bbattle\s*pass\b",
            r"\bcosmetics?\b",
            r"\blegendary\s+(?:skin|outfit)\b",
            r"\bскин",
            r"\bмифич",
            r"\bбоевой\s+пропуск\b",
            r"\bкосметик",
        ],
    ),
    (
        "event",
        12,
        [
            r"\bseason\s*\d+\b",
            r"\bblizzcon\b",
            r"\bcollab(?:oration|s)?\b|\bcrossover\b",
            r"\bpatch\s+notes?\b",
            r"\bspecial\s+event\b",
            r"\bсезон\b",
            r"\bсобытие\b",
            r"\bобновлени",
        ],
    ),
    (
        "esports",
        6,
        [
            r"\bowcs\b|\boverwatch\s+league\b|\besports?\b",
            r"\btournament\b|\bchampionship\b|\broster\b",
        ],
    ),
]

_COMPILED = [
    (name, bonus, [re.compile(p, re.I) for p in patterns])
    for name, bonus, patterns in RULES
]

DEFAULT_WEIGHT = {"hero": 0, "skin": 0, "event": 0, "esports": 0, "news": 0}
CATEGORY_BONUS = {name: bonus for name, bonus, _ in RULES}
CATEGORY_BONUS["news"] = 0

ORDER = ["hero", "skin", "event", "esports", "news"]

LABELS = {
    "hero": "🆕 Герои",
    "skin": "🎨 Скины и косметика",
    "event": "📅 Сезоны, события, патчи",
    "esports": "🏆 Киберспорт",
    "news": "📰 Прочие новости",
}


def classify(item: Item) -> Item:
    haystack = f"{item.title} {item.summary}"
    for name, _bonus, patterns in _COMPILED:
        if any(p.search(haystack) for p in patterns):
            item.category = name
            return item
    item.category = "news"
    return item


def score(item: Item, reference: datetime) -> float:
    value = item.weight * 10 + CATEGORY_BONUS[item.category]
    if item.published:
        age_hours = max(0.0, (reference - item.published).total_seconds() / 3600)
        value -= min(age_hours / 6.0, 60.0)
    elif item.order:
        # Нет даты — доверяем порядку в ленте (сверху = свежее).
        value -= min(item.order * 0.4, 30.0)
    return value


def rank(items: list[Item], reference: datetime) -> list[Item]:
    for item in items:
        classify(item)
    return sorted(items, key=lambda i: score(i, reference), reverse=True)
