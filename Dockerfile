# =============================================================================
# Докерфайл приложения «Заметки».
#
# ВАЖНО: образ собирается ИЗ СБОРОЧНОГО АРТЕФАКТА (wheel-пакета), который
# заранее создаёт CI-скрипт ci/build.sh, а не из исходного кода. Так выполнено
# требование «артефакт берётся процессами, упаковывается в контейнер».
#
# Сборка (её делает deploy/deploy.sh, вручную так):
#   docker build --build-arg WHEEL=artifacts/notes_app-1.0.0-py3-none-any.whl \
#                --tag notes-app:1.0.0 .
# =============================================================================

FROM python:3.12-slim

# Путь к артефакту внутри контекста сборки (папка artifacts/).
ARG WHEEL
RUN test -n "$WHEEL" || { \
      echo "ОШИБКА: укажите артефакт: --build-arg WHEEL=artifacts/<имя>.whl"; \
      echo "Сначала выполните сборку: bash ci/build.sh"; \
      exit 1; \
    }

LABEL org.opencontainers.image.title="notes-app" \
      org.opencontainers.image.description="Заметки: домашняя работа по DevOps (собран из артефакта ${WHEEL})"

WORKDIR /srv

# Ставим только собранный артефакт: он уже содержит весь код и зависимости.
# Имя wheel-файла сохраняем — pip требует валидное имя вида name-version-*.whl.
COPY ${WHEEL} /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# База SQLite хранится в /data — монтируется docker volume (сохранность данных).
ENV DB_PATH=/data/notes.db \
    PYTHONUNBUFFERED=1

VOLUME /data
EXPOSE 8080

# Health check: /health должен вернуть HTTP 200 (его же опрашивает Prometheus).
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/health', timeout=2)"

# Один процесс с потоками: счётчик посещений живёт в памяти процесса,
# при нескольких воркерах gunicorn каждый считал бы только свои запросы.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", \
     "--access-logfile", "-", "notes_app.app:app"]
