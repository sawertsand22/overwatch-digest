#!/usr/bin/env bash
# Запуск сводки на Debian/Linux: ./run.sh [--no-publish]
set -euo pipefail
cd "$(dirname "$0")"
exec python3 run.py "$@"
