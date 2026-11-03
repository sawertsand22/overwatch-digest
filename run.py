#!/usr/bin/env python3
"""Запуск сводки: python run.py [--no-publish] [--no-images] [--max N]"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from owdigest.main import cli  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(cli())
