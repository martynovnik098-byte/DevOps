#!/usr/bin/env bash
# =============================================================================
# ЭТАП CI: тесты + сборка артефакта (wheel) ВНУТРИ КОНТЕЙНЕРА Python.
#
# Сам скрипт на хосте не требует ничего, кроме Docker: ни Python, ни pip.
# Результат сохраняется в artifacts/ — оттуда его забирает этап CD
# (deploy/deploy.sh), упаковывает в docker-образ и деплоит.
#
# Запуск:  bash ci/build.sh
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

APP_DIR="app"                # исходный код приложения
ART_DIR="artifacts"          # сюда сохраняется артефакт (с сохранением)
BUILDER_IMAGE="python:3.12-slim"

mkdir -p "$ART_DIR"

echo "==> Шаг 1/3. Тесты приложения (в контейнере $BUILDER_IMAGE)"
docker run --rm \
  --volume "$(pwd)/$APP_DIR":/app --workdir /app \
  "$BUILDER_IMAGE" bash -c \
  'pip install --quiet flask prometheus-client && python -m unittest discover -s tests -v'

echo "==> Шаг 2/3. Сборка wheel-артефакта (в контейнере)"
docker run --rm \
  --volume "$(pwd)/$APP_DIR":/app --workdir /app \
  --volume "$(pwd)/$ART_DIR":/out \
  "$BUILDER_IMAGE" bash -c \
  'pip install --quiet build && python -m build --wheel --outdir /out'

WHEEL="$(cd "$ART_DIR" && ls -t -- *.whl | head -n 1)"
echo -n "$WHEEL" > "$ART_DIR/LATEST"

GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'no-git')"
VERSION="$(printf '%s' "$WHEEL" | cut -d- -f2)"
printf 'artifact=%s\nversion=%s\ngit=%s\ndate=%s\n' \
  "$WHEEL" "$VERSION" "$GIT_SHA" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$ART_DIR/build.info"

echo "==> Шаг 3/3. Готово. Артефакт сохранён: artifacts/$WHEEL"
echo "    Дальше: bash deploy/deploy.sh"
