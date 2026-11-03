# 🟠 Overwatch Digest

Автоматическая сводка новостей Overwatch: новые герои, скины, сезоны, патчи.
Каждые 12 часов собирает материалы, скачивает превью, складывает их в архив
и обновляет **один** GitHub Issue — его удобно смотреть с телефона.

Работает на бесплатном GitHub Actions, поэтому **не нужен VPS и включённый ПК**.

```
GitHub Actions (cron, каждые 12 ч)
        │
        ├─ Blizzard News (EN + RU)   ─┐
        ├─ Dexerto Overwatch          ├─► дедупликация → классификация → рейтинг
        ├─ Eurogamer / PC Gamer       │
        └─ Google News (опционально) ─┘
        │
        ├─► GitHub Issue  «🟠 Overwatch — сводка»   ← читаешь с телефона
        ├─► digests/latest.html                      ← красивый архив
        └─► digests/*.md + images/*                  ← история в репозитории
```

---

## Быстрый старт (15 минут, один раз)

### 1. Создать репозиторий

```bash
cd "C:/projects/ai/claude/news overwatch"
git init
git add -A
git commit -m "init: overwatch digest"
```

Дальше либо через `gh`:

```bash
gh repo create overwatch-digest --public --source=. --push
```

…либо руками: создай пустой репозиторий на github.com и выполни

```bash
git remote add origin https://github.com/<твой-логин>/overwatch-digest.git
git branch -M main
git push -u origin main
```

### 2. Разрешить Actions писать в репозиторий

Это самый важный шаг, без него не заработает:

**Settings → Actions → General → Workflow permissions →
«Read and write permissions» → Save.**

Заодно проверь, что **Issues включены** (Settings → General → Features → Issues,
по умолчанию включено).

### 3. Запустить первый раз вручную

**Actions → Overwatch digest → Run workflow → Run workflow.**

Первый запуск называется «стартовый срез»: он покажет самое актуальное за
последние 120 дней, чтобы Issue не был пустым.

### 4. Открыть Issue

Вкладка **Issues** → «🟠 Overwatch — сводка». Добавь его в закладки телефона.

Дальше всё само: каждые 12 часов Issue перезаписывается только новыми
материалами, а старые остаются в `digests/`.

---

## Расписание

Сейчас в `.github/workflows/overwatch-digest.yml`:

```yaml
- cron: "0 6,18 * * *"   # 09:00 и 21:00 МСК
```

Время указывается в **UTC**, поэтому МСК = UTC+3. Примеры:

| Хочу (МСК) | cron (UTC)        |
|------------|-------------------|
| 09:00, 21:00 | `0 6,18 * * *`  |
| каждые 6 часов | `0 */6 * * *` |
| раз в сутки в 12:00 | `0 9 * * *` |

⚠️ GitHub запускает cron с задержкой 5–30 минут — это нормально.
Ещё GitHub **отключает** scheduled-воркфлоу после 60 дней без активности в
репозитории; наши коммиты каждые 12 часов как раз создают эту активность.

---

## Запуск на своём ПК

Скрипт тот же, что в Actions — зависимостей нет, только Python 3.11+.

**Windows** — двойной клик по `run.bat` (или `python run.py`).

**Debian** — `./run.sh` (или `python3 run.py`).

По умолчанию локальный запуск тоже публикует в Issue, если есть авторизация:
переменная `GITHUB_TOKEN`/`GH_TOKEN` либо `gh auth login`. Чтобы только
собрать файлы — `python run.py --no-publish`.

Полезные флаги:

| Флаг | Что делает |
|------|------------|
| `--no-publish` | только файлы, Issue не трогать |
| `--no-images` | не качать картинки (быстрее) |
| `--max 30` | показать больше материалов |

### Автозапуск, если ПК включён

**Windows** (две задачи — утром и вечером):

```bat
schtasks /Create /SC DAILY /TN "OverwatchDigestAM" /TR "\"C:\projects\ai\claude\news overwatch\run.bat\"" /ST 10:00 /F
schtasks /Create /SC DAILY /TN "OverwatchDigestPM" /TR "\"C:\projects\ai\claude\news overwatch\run.bat\"" /ST 22:00 /F
```

**Debian** (crontab -e):

```cron
0 10,22 * * * cd /home/ВЛАДС/news-overwatch && ./run.sh >> /tmp/overwatch-digest.log 2>&1
```

Оговорка очевидна: если ПК был выключен — этот запуск пропускается.
Но GitHub Actions работает независимо, так что в Issue всё равно всё придёт.
Локальный запуск идёт по тем же `state/seen.json`, поэтому ничего не задвоится.

---

## Настройка

Всё в `config.py`:

- **`SOURCES`** — список источников. Чтобы добавить сайт с RSS:

  ```python
  {
      "id": "my_site",
      "type": "rss",
      "url": "https://example.com/feed/",
      "filter": "overwatch",   # необязательно
      "weight": 2,             # 3 = официально, 2 = профильное, 1 = пресса
  },
  ```

- **`MAX_ITEMS`** — сколько материалов в сводке (по умолчанию 15).
- **`MAX_AGE_DAYS`** — старше этого срока не показываем (120).
- **`ISSUE_TITLE`** — название Issue.
- **`KEEP_IMAGES_DAYS`** — через сколько дней удалять старые картинки (60),
  чтобы репозиторий не разрастался.

Категории и ключевые слова («новый герой», «скин», «mythic», «season»…)
описаны в `owdigest/classify.py`.

---

## Что внутри

```
config.py                      настройки
run.py / run.bat / run.sh      точка входа
owdigest/
  sources.py                   загрузка Blizzard и RSS, дедупликация
  classify.py                  герой / скин / событие / киберспорт
  media.py                     скачивание картинок, чистка старых
  render.py                    Markdown для Issue + HTML-архив
  store.py                     state/seen.json и ретеншн
  publish.py                   GitHub API: создать/обновить Issue
state/seen.json                что уже видели (чтобы не повторяться)
digests/latest.md|html         текущая сводка
digests/YYYY-MM-DD-HHMM.md     история
images/YYYY-MM-DD/*.jpg        скачанные превью
```

## Подводные камни

- **Google News** из GitHub Actions часто отдаёт ошибку — источник помечен
  опциональным, сводка строится без него.
- **Reddit** отдаёт 403/429 с серверных IP — поэтому его нет в списке.
- Issue обновляется **на месте**, а не создаётся новый — иначе за год набежит
  700 штук. История лежит в `digests/`.
- Если Actions упал на шаге публикации, сводка всё равно закоммитится в
  `digests/` — ничего не теряется.
