"""Точка входа: собрать → отфильтровать новое → сводка → публикация."""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

from . import classify, media, render, store, util
from . import publish as gh
from .sources import (
    Item,
    dedupe_titles,
    enrich_blizzard,
    fetch_source,
    merge_duplicates,
)


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def gather(sources: list[dict]) -> tuple[list[Item], list[str]]:
    items: list[Item] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_source, src): src for src in sources}
        for future in as_completed(futures):
            src = futures[future]
            try:
                got = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append(src["id"])
                print(f"  ✗ {src['id']:<13} {str(exc)[:110]}")
                continue
            items.extend(got)
            print(f"  ✓ {src['id']:<13} {len(got):>3} шт.")
    return items, failures


def enrich(items: list[Item], limit: int) -> list[Item]:
    """Догружает страницы статей Blizzard: точную дату, описание, обложку."""
    todo = [i for i in items if i.uid.startswith("blizzard:") and not i.published][:limit]
    if not todo:
        return items
    print(f"  … догружаю страницы статей Blizzard: {len(todo)}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(enrich_blizzard, todo))
    return items


def recent(items: list[Item], reference, days: int) -> list[Item]:
    kept = [
        i for i in items
        if i.published is None or (reference - i.published).days <= days
    ]
    if len(kept) != len(items):
        print(f"  отсеяно по возрасту (>{days} дн.): {len(items) - len(kept)}")
    return kept


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content.rstrip() + "\n")


def run(args: argparse.Namespace) -> int:
    root = project_root()
    reference = util.now()
    state_path = os.path.join(root, config.STATE_FILE)
    state = store.load_state(state_path)
    baseline = not state["seen"]

    print(f"\n🟠 Overwatch digest · {reference:%Y-%m-%d %H:%M UTC}")
    print("Источники:")
    raw_items, failures = gather(config.SOURCES)

    items = dedupe_titles(merge_duplicates(raw_items))
    total_found = len(items)
    print(f"Всего материалов: {total_found}")

    max_items = args.max or config.MAX_ITEMS
    if baseline:
        pool = items
        print("  первый запуск → собираю стартовый срез")
    else:
        pool = [i for i in items if store.is_new(state, i)]
        print(f"  новых с прошлого раза: {len(pool)}")

    # Обогащение обязано идти ДО ранжирования: без дат старые статьи
    # выглядят как свежие.
    pool = enrich(pool, config.ENRICH_CANDIDATES)
    pool = recent(pool, reference, config.MAX_AGE_DAYS)
    selected = classify.rank(pool, reference)[:max_items]

    images: dict[str, str] = {}
    if selected and not args.no_images:
        images = media.download_items(
            selected,
            os.path.join(root, config.IMAGES_DIR),
            config.IMAGES_DIR,
            reference,
            max_items,
        )
        print(f"  картинок скачано: {len(images)}")

    digest_name = reference.strftime("%Y-%m-%d-%H%M")
    digests_dir = os.path.join(root, config.DIGESTS_DIR)

    body_remote = render.render_markdown(
        selected,
        reference=reference,
        images=images,
        total_found=total_found,
        failures=failures,
        baseline=baseline,
        image_mode="remote",
    )
    body_local = render.render_markdown(
        selected,
        reference=reference,
        images=images,
        total_found=total_found,
        failures=failures,
        baseline=baseline,
        image_mode="local",
    )
    page = render.render_html(
        selected,
        reference=reference,
        images=images,
        total_found=total_found,
        failures=failures,
        baseline=baseline,
    )

    write_file(os.path.join(digests_dir, f"{digest_name}.md"), body_local)
    write_file(os.path.join(digests_dir, "latest.md"), body_local)
    write_file(os.path.join(digests_dir, "latest.html"), page)
    print(f"  сводка: {config.DIGESTS_DIR}/{digest_name}.md")

    exit_code = 0
    if args.no_publish:
        print("  публикация отключена (--no-publish)")
    else:
        try:
            status, url = gh.publish(
                body_remote, title=config.ISSUE_TITLE, label=config.ISSUE_LABEL
            )
            print(f"  Issue ({status}): {url}")
        except gh.GitHubError as exc:
            print(f"  ⚠️ публикация не удалась: {exc}")
            print("    сводка сохранена локально в digests/")
            exit_code = 0  # архив остаётся рабочим fallback

    store.mark_seen(state, items, reference)
    state["last_run"] = util.iso(reference)
    store.prune_seen(state, reference, config.KEEP_SEEN_DAYS)
    store.save_state(state_path, state)

    store.prune_digests(digests_dir, reference, config.KEEP_DIGESTS_DAYS)
    media.prune_images(os.path.join(root, config.IMAGES_DIR), reference, config.KEEP_IMAGES_DAYS)

    print(f"\nГотово: {len(selected)} материалов в сводке.\n")
    return exit_code


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="overwatch-digest")
    parser.add_argument("--no-publish", action="store_true", help="не трогать GitHub Issue")
    parser.add_argument("--no-images", action="store_true", help="не качать картинки")
    parser.add_argument("--max", type=int, default=0, help="сколько материалов показать")
    args = parser.parse_args(argv)
    return run(args)
