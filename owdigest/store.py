"""Состояние «что уже видели» и уборка старых файлов."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

from . import util
from .sources import Item

VERSION = 1


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"version": VERSION, "last_run": None, "seen": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"version": VERSION, "last_run": None, "seen": {}}
    data.setdefault("version", VERSION)
    data.setdefault("last_run", None)
    data.setdefault("seen", {})
    return data


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def mark_seen(state: dict, items: list[Item], reference: datetime) -> None:
    stamp = util.iso(reference)
    seen = state["seen"]
    for item in items:
        if item.uid in seen:
            continue
        seen[item.uid] = {"t": stamp, "title": item.title[:160], "src": item.source}


def prune_seen(state: dict, reference: datetime, days: int) -> None:
    cutoff = reference - timedelta(days=days)
    seen = state["seen"]
    for uid in list(seen):
        stamp = util.parse_date(seen[uid].get("t"))
        if stamp is None or stamp < cutoff:
            del seen[uid]


def is_new(state: dict, item: Item) -> bool:
    return item.uid not in state["seen"]


_DIGEST_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-\d{4}\.(?:md|html)$")


def prune_digests(directory: str, reference: datetime, days: int) -> None:
    if not os.path.isdir(directory):
        return
    cutoff = (reference - timedelta(days=days)).date()
    for name in os.listdir(directory):
        match = _DIGEST_NAME.match(name)
        if not match:
            continue  # latest.md / latest.html не трогаем
        try:
            stamp = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if stamp < cutoff:
            try:
                os.remove(os.path.join(directory, name))
            except OSError:
                pass
