#!/usr/bin/env bash
# =============================================================================
# ЭТАП CD: упаковка артефакта из artifacts/ в docker-образ и деплой стека
# (приложение + Prometheus + Grafana + cAdvisor) через docker compose.
#
# Запуск:  bash deploy/deploy.sh   (сначала выполните bash ci/build.sh)
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

ART_DIR="artifacts"

# Берём самый свежий артефакт: сначала по ссылке LATEST, иначе — по дате.
WHEEL=""
if [ -f "$ART_DIR/LATEST" ] && [ -f "$ART_DIR/$(cat "$ART_DIR/LATEST")" ]; then
  WHEEL="$(cat "$ART_DIR/LATEST")"
elif compgen -G "$ART_DIR/*.whl" > /dev/null; then
  WHEEL="$(cd "$ART_DIR" && ls -t -- *.whl | head -n 1)"
fi
if [ -z "$WHEEL" ]; then
  echo "ОШИБКА: в $ART_DIR нет wheel-артефакта." >&2
  echo "Сначала запустите сборку: bash ci/build.sh" >&2
  exit 1
fi

VERSION="$(printf '%s' "$WHEEL" | cut -d- -f2)"
IMAGE="notes-app:$VERSION"

echo "==> Шаг 1/2. Сборка образа $IMAGE из артефакта $ART_DIR/$WHEEL"
docker build --build-arg "WHEEL=$ART_DIR/$WHEEL" --tag "$IMAGE" .

echo "==> Шаг 2/2. Деплой стека: docker compose up -d"
export APP_IMAGE="$IMAGE"
docker compose up -d --remove-orphans

docker compose ps
cat <<EOF

Готово! Ссылки:
  Приложение        http://localhost:8080
  Health check      http://localhost:8080/health
  Метрики (текст)   http://localhost:8080/metrics
  Prometheus        http://localhost:9090
  Grafana           http://localhost:3000   (admin / admin)
  cAdvisor          http://localhost:8081
EOF
