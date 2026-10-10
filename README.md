# DevOps: приложение в контейнере + CI/CD + мониторинг

Домашняя работа №1 по дисциплине «Системное программное обеспечение».

Веб-приложение «Заметки» (Flask + SQLite): кликабельный интерфейс, данные
редактируются и сохраняются. Всё развёртывается в Docker: сборка приложения
происходит в контейнере, артефакт сохраняется, упаковывается в образ и
деплоится вместе со стеком мониторинга (Prometheus + Grafana + cAdvisor).

## Работающее развёртывание (сервер)

Приложение задеплоено на сервер, ссылки доступны с любого устройства:

| Что | Ссылка |
|---|---|
| Приложение (интерфейс) | http://195.19.213.85:8080 |
| Дашборд мониторинга (Grafana) | http://195.19.213.85:3000 — просмотр без авторизации |
| Health check | http://195.19.213.85:8080/health |
| Метрики приложения (Prometheus-формат) | http://195.19.213.85:8080/metrics |
| Prometheus | http://195.19.213.85:9090 |
| Конвейер CI/CD (GitHub Actions) | https://github.com/martynovnik098-byte/DevOps/actions |

Локальный запуск тех же скриптов — в разделе «Быстрый старт» ниже.

## Соответствие требованиям

| Требование | Как выполнено |
|---|---|
| Приложение в контейнере | `Dockerfile` + `docker-compose.yml` |
| Мониторинг | Prometheus (сбор), Grafana (дашборд), cAdvisor (ресурсы контейнеров) |
| Исходники в git | репозиторий (структура ниже), пайплайн GitHub Actions в `.github/workflows/` |
| Сборка приложения, артефакт с сохранением | `ci/build.sh` — тесты + сборка wheel **в контейнере**, артефакт в `artifacts/` (+ artifact в GitHub Actions) |
| Артефакт упаковывается в контейнер и деплоится | `deploy/deploy.sh` — образ собирается **из wheel-артефакта**, `docker compose up -d` |
| Сборка и деплой в контейнере | оба этапа выполняются в docker-контейнерах, на хосте нужен только Docker |
| Скрипты сборки/деплоя | `ci/build.sh`, `ci/build.bat`, `deploy/deploy.sh`, `deploy/deploy.bat` |
| Файл описания контейнера | `Dockerfile` (в корне) |
| Ссылка на работающее приложение и метрику | см. «Ссылки» ниже (после запуска) |
| Приложение запускается **и редактируется** | CRUD заметок в UI, данные в docker volume переживают рестарт |
| Метрика: ресурсы (потребляемые и доступные) | cAdvisor: CPU/RAM контейнеров + лимиты + ресурсы хоста (панели Grafana) |
| Метрика: health check | `/health` + Docker HEALTHCHECK + панель `up` в Grafana |
| Метрика: посещения в час | `app_http_requests_total` → панель «Посещения за последний час» |

## Быстрый старт

Нужен только установленный Docker (Docker Desktop / Docker Engine).

**Linux / macOS / WSL / Git Bash:**

```bash
bash ci/build.sh        # CI:  тесты + сборка wheel-артефакта в контейнере
bash deploy/deploy.sh   # CD:  образ из артефакта + деплой всего стека
```

**Windows (cmd):**

```bat
ci\build.bat
deploy\deploy.bat
```

Открыть [http://localhost:8080](http://localhost:8080) — работает приложение.

Остановить и удалить стек: `docker compose down` (данные в volumes сохранятся;
полная очистка — `docker compose down -v`).

## Ссылки (после запуска)

| Что | Адрес | Примечание |
|---|---|---|
| Приложение (интерфейс) | http://localhost:8080 | кликабельный UI заметок |
| Health check | http://localhost:8080/health | JSON: статус + версия |
| Метрики приложения (текст) | http://localhost:8080/metrics | формат Prometheus |
| Prometheus | http://localhost:9090 | raw-метрики, targets |
| **Grafana (дашборд)** | http://localhost:3000 | логин `admin`, пароль `admin`, дашборд «DevOps: приложение «Заметки» — мониторинг» создаётся сам |
| cAdvisor | http://localhost:8081 | ресурсы контейнеров напрямую |

При развёртывании на сервере те же ссылки, но `localhost` заменяется на адрес
сервера (см. раздел «Деплой на сервер»).

## Схема процесса CI/CD

```
 git push / локальный запуск
        │
        ▼
┌───────────────────────┐   артефакт сохраняется
│  CI  (ci/build.sh)    │   в artifacts/*.whl
│  всё внутри контейнеров│──────────────┐
│  1. unittest в python:3.12-slim      │
│  2. python -m build → wheel          │
└───────────────────────┘              │
                                       ▼
                        ┌──────────────────────────┐
                        │  артефакт artifacts/     │
                        │  notes_app-1.0.0-...whl  │
                        │  (+ build.info, LATEST)  │
                        └────────────┬─────────────┘
                                     ▼
┌────────────────────────────────────────────────────┐
│  CD  (deploy/deploy.sh)                            │
│  1. docker build --build-arg WHEEL=artifacts/…whl  │
│         Dockerfile ставит ТОЛЬКО артефакт          │
│  2. docker compose up -d:                           │
│     app + prometheus + grafana + cadvisor           │
└────────────────────────────────────────────────────┘
        │
        ▼
 http://localhost:8080 — приложение;  :3000 — Grafana
 healthcheck зелёный, метрики собираются каждые 5 секунд
```

Тот же процесс в GitHub Actions (`.github/workflows/ci-cd.yml`):
джоб `build` выполняет `ci/build.sh` и сохраняет артефакт
(`actions/upload-artifact`), джоб `deploy` скачивает его, собирает образ,
публикует в GHCR и деплоит на сервер по SSH (настраивается секретами).

## Что именно делает каждый этап

### CI — `ci/build.sh` (или `ci/build.bat`)

1. **Тесты в контейнере.** `docker run python:3.12-slim` ставит зависимости
   и запускает `python -m unittest discover -s tests`. Если тесты падают —
   сборка прерывается, артефакт не создаётся.
2. **Сборка артефакта в контейнере.** `python -m build --wheel` собирает
   wheel-пакет `notes_app-<версия>-py3-none-any.whl` — это и есть сборочный
   артефакт: в него упакован код приложения, интерфейс и зависимости.
3. **Сохранение артефакта.** Wheel остаётся в `artifacts/` (плюс файлы
   `LATEST` — имя свежего артефакта, и `build.info` — версия, git-коммит,
   дата). В GitHub Actions артефакт дополнительно сохраняется как artifact.

### CD — `deploy/deploy.sh` (или `deploy/deploy.bat`)

1. **Упаковка артефакта в контейнер.** `docker build --build-arg WHEEL=…`
   по `Dockerfile`: базовый образ `python:3.12-slim`, в него ставится
   только wheel (исходники образу не нужны — `.dockerignore` пропускает
   в контекст сборки одну папку `artifacts/`). Настраивается `HEALTHCHECK`
   на `/health`.
2. **Деплой.** `docker compose up -d` поднимает 4 контейнера:
   - `notes-app` — само приложение (порт 8080), SQLite в volume `app-data`,
     лимиты `mem_limit: 256m`, `cpus: 0.50` — чтобы были метрики «доступных»
     ресурсов;
   - `notes-prometheus` — опрашивает `/metrics` приложения и cAdvisor
     каждые 5 с, история в volume;
   - `notes-grafana` — дашборд и источник данных подгружаются автоматически
     из `monitoring/grafana/` (provisioning);
   - `notes-cadvisor` — метрики ресурсов всех контейнеров.

## Метрики (где что смотреть)

| Метрика | Запрос Prometheus | Панель Grafana |
|---|---|---|
| Посещения за час | `sum(increase(app_http_requests_total[1h]))` | «Посещения за последний час» |
| Health check | `up{job="app"}` (плюс Docker `HEALTHCHECK` → `docker compose ps` показывает healthy) | «Health check» (UP/DOWN) |
| Ресурсы: потребляемые | `container_memory_usage_bytes`, `rate(container_cpu_usage_seconds_total[5m])`, `process_resident_memory_bytes` | «Память контейнеров», «CPU контейнеров», «Память процесса» |
| Ресурсы: доступные | `container_spec_memory_limit_bytes`, `container_spec_cpu_quota/container_spec_cpu_period`, `machine_memory_bytes`, `machine_cpu_cores` | «Лимит RAM приложения» (пунктиром на графиках), «RAM/CPU хоста» |

## Проверка «приложение не только запускается, но и редактируется»

1. Открыть http://localhost:8080.
2. Добавить заметку (заголовок + текст → «Добавить»).
3. Нажать «Изменить» — отредактировать, сохранить.
4. Отметить выполненной (галочка), удалить лишнюю.
5. Проверить сохранность данных при пересоздании контейнера:
   ```bash
   docker compose restart app     # или даже down + deploy заново
   ```
   Заметки на месте: база лежит в volume `app-data`, а не в контейнере.

## Структура репозитория

```
DevOps/
├── README.md                  # этот файл: описание процесса
├── Dockerfile                 # описание контейнера приложения (из артефакта)
├── docker-compose.yml         # весь стек: app + мониторинг
├── .dockerignore
├── .gitignore
├── app/                       # ИСХОДНЫЙ КОД приложения
│   ├── pyproject.toml         #   метаданные пакета (для сборки wheel)
│   ├── notes_app/             #   Flask-приложение
│   │   ├── app.py             #   маршруты, метрики, health
│   │   ├── db.py              #   SQLite (CRUD)
│   │   └── static/            #   интерфейс: html + css + js
│   └── tests/                 #   unittest-тесты API
├── ci/
│   ├── build.sh               # скрипт сборки (тесты + wheel в контейнере)
│   └── build.bat              # то же для Windows cmd
├── deploy/
│   ├── deploy.sh              # скрипт деплоя (образ + compose up)
│   └── deploy.bat             # то же для Windows cmd
├── monitoring/
│   ├── prometheus.yml         # что и как часто опрашивать
│   └── grafana/               # автозагрузка datasource + дашборда
├── artifacts/                 # сюда CI складывает артефакты (в git не коммитится)
└── .github/workflows/ci-cd.yml  # конвейер CI/CD для GitHub
```

## Деплой на сервер

Скрипты одинаковы для ноутбука и сервера: на сервере нужен только Docker.

```bash
git clone <этот-репозиторий> && cd DevOps
bash ci/build.sh && bash deploy/deploy.sh
```

Для деплоя с GitHub Actions (без ручного входа на сервер) задайте секреты
репозитория: `REGISTRY_TOKEN`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`,
`DEPLOY_PATH` — тогда пуш в `main` сам соберёт артефакт, образ, опубликует его
в GHCR и выполнит `docker compose up -d` на сервере. На сервере нужно открыть
порты 8080 (приложение), 3000 (Grafana), при желании 9090/8081.

Ссылки для отчёта: `http://<сервер>:8080` — приложение,
`http://<сервер>:3000` — Grafana с метриками.

Минимальные требования к серверу: Linux (Ubuntu 22.04/24.04), 1–2 vCPU,
2 ГБ RAM, 10 ГБ диска, установленный Docker (одна команда:
`curl -fsSL https://get.docker.com | sh`). Весь стек занимает ~700 МБ RAM.

## Как изменить приложение и пересобрать

1. Поменять код в `app/` (например, версию в `app/notes_app/__init__.py`
   и `app/pyproject.toml`).
2. Снова выполнить `bash ci/build.sh && bash deploy/deploy.sh` —
   поднимется новая версия артефакта и образа; данные в volume сохранятся.

## Технические заметки

- Gunicorn запускается с одним воркером и 4 потоками: счётчик посещений
  живёт в памяти процесса, при нескольких воркерах каждый считал бы только
  свои запросы.
- Сборка и деплой выполняются в контейнерах (`python:3.12-slim` для сборки),
  поэтому на машине, где запускаются скрипты, не нужны ни Python, ни pip.
- `.sh`-скрипты запускайте из Git Bash/WSL/Linux; на чистом Windows —
  используйте `.bat`-версии (делают то же самое).
- Если порты 3000/8080/8081/9090 заняты — поменяйте левую часть в
  `docker-compose.yml` (например, `"3001:3000"`).
- **Важно для свежих Docker Desktop (4.34+):** если в настройках включён
  «Use containerd for pulling and storing images» (по умолчанию он включён
  в новых установках), cAdvisor не сможет собрать метрики отдельных
  контейнеров (не умеет читать хранилище containerd). Отключите эту опцию:
  Settings → General → снять галочку «Use containerd for pulling and storing
  images» → Apply & Restart, затем выполните `deploy\deploy.bat` ещё раз.
  Проверено: с классическим хранилищем (overlay2) все метрики контейнеров
  собираются корректно.
