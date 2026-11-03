"""Настройки сборщика.

Меняй здесь — код трогать не нужно.
"""

# ── Куда публиковать ────────────────────────────────────────────────────────
ISSUE_TITLE = "🟠 Overwatch — сводка"
ISSUE_LABEL = "digest"

# Сколько материалов показывать в одной сводке
MAX_ITEMS = 15
# Сколько статей догружать целиком (ради точной даты и описания)
ENRICH_CANDIDATES = 60
# Материалы старше этого срока в сводку не попадают
MAX_AGE_DAYS = 120

# Сколько дней хранить архивы и картинки
KEEP_DIGESTS_DAYS = 120
KEEP_IMAGES_DAYS = 60
# Сколько дней помнить «уже видели» (защита от роста state/seen.json)
KEEP_SEEN_DAYS = 365

# ── Источники ───────────────────────────────────────────────────────────────
# type: "blizzard" — карточки со страницы новостей Blizzard
#       "rss"      — обычная лента RSS/Atom
# filter: подстрока, которая обязана встретиться в заголовке/описании
SOURCES = [
    {
        "id": "blizzard_en",
        "type": "blizzard",
        "url": "https://news.blizzard.com/en-us/overwatch",
        "lang": "en",
        "weight": 3,
    },
    {
        "id": "blizzard_ru",
        "type": "blizzard",
        "url": "https://news.blizzard.com/ru-ru/overwatch",
        "lang": "ru",
        "weight": 3,
    },
    {
        "id": "dexerto",
        "type": "rss",
        "url": "https://www.dexerto.com/overwatch/feed/",
        "weight": 2,
    },
    {
        "id": "eurogamer",
        "type": "rss",
        "url": "https://www.eurogamer.net/feed",
        "filter": "overwatch",
        "weight": 1,
    },
    {
        "id": "pcgamer",
        "type": "rss",
        "url": "https://www.pcgamer.com/rss/",
        "filter": "overwatch",
        "weight": 1,
    },
    # Ленты ниже могут блокироваться с IP GitHub Actions — ошибка не критична.
    {
        "id": "googlenews",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=Overwatch+2&hl=en-US&gl=US&ceid=US:en",
        "weight": 1,
        "optional": True,
    },
]

# ── Пути (относительно корня проекта) ───────────────────────────────────────
STATE_FILE = "state/seen.json"
DIGESTS_DIR = "digests"
IMAGES_DIR = "images"
