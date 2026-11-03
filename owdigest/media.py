"""Скачивание превью-картинок и уборка старых папок."""

from __future__ import annotations

import os
import shutil
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from . import util
from .sources import Item

MAX_BYTES = 5 * 1024 * 1024
_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}


def _extension(url: str, content_type: str) -> str:
    ext = _EXT_BY_TYPE.get((content_type or "").split(";")[0].strip().lower())
    if ext:
        return ext
    path = urllib.parse.urlparse(url).path
    _, candidate = os.path.splitext(path)
    if candidate.lower() in _EXT_BY_TYPE.values():
        return candidate.lower()
    return ".jpg"


def download_items(items: list[Item], images_root: str, images_rel: str,
                   reference: datetime, limit: int) -> dict[str, str]:
    """Возвращает {uid: путь картинки относительно корня проекта}."""
    day = reference.strftime("%Y-%m-%d")
    folder = os.path.join(images_root, day)
    result: dict[str, str] = {}

    for item in items:
        if len(result) >= limit or not item.image:
            continue
        if not item.image.startswith(("http://", "https://")):
            continue

        os.makedirs(folder, exist_ok=True)
        stem = f"{util.slugify(item.title, 40)}-{util.short_hash(item.uid, 6)}"

        try:
            req = urllib.request.Request(item.image, headers={"User-Agent": util.USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if not content_type.lower().startswith("image"):
                    continue
                data = resp.read(MAX_BYTES)
        except Exception:  # noqa: BLE001 — картинка не критична
            continue

        if len(data) < 1024:
            continue

        filename = stem + _extension(item.image, content_type)
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(data)
        result[item.uid] = "/".join((images_rel, day, filename))

    return result


def prune_images(images_root: str, reference: datetime, days: int) -> None:
    if not os.path.isdir(images_root):
        return
    cutoff = reference - timedelta(days=days)
    for name in os.listdir(images_root):
        path = os.path.join(images_root, name)
        if not os.path.isdir(path):
            continue
        try:
            folder_date = datetime.strptime(name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if folder_date < cutoff:
            shutil.rmtree(path, ignore_errors=True)
