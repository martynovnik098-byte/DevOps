"""Веб-приложение «Заметки»: интерфейс, REST API, health check и метрики.

Маршруты:
    GET  /                    — кликабельный интерфейс
    GET/POST  /api/notes      — список / создание заметок
    GET/PUT/DELETE /api/notes/<id> — чтение / редактирование / удаление
    GET  /api/stats           — сводка для подвала интерфейса
    GET  /health              — health check (его же использует Docker HEALTHCHECK)
    GET  /metrics             — метрики в формате Prometheus
"""
import os
import sqlite3
import time

from flask import Flask, jsonify, request, send_from_directory
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from . import __version__, db

STARTED_AT = time.time()

# --- метрики Prometheus ------------------------------------------------------
HTTP_REQUESTS = Counter(
    "app_http_requests_total",
    "Общее число HTTP-запросов к приложению (метрика «посещения в час»)",
)
NOTES_COUNT = Gauge("app_notes_count", "Текущее число заметок в базе")

app = Flask(__name__)


def _sync_notes_gauge() -> None:
    try:
        NOTES_COUNT.set(db.count_notes())
    except sqlite3.Error:
        pass


db.init_db()
_sync_notes_gauge()


@app.before_request
def _count_visit():
    HTTP_REQUESTS.inc()


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/notes")
def api_notes():
    return jsonify(db.list_notes())


@app.post("/api/notes")
def api_create_note():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    if not title:
        return jsonify(error="Поле title обязательно"), 400
    note_id = db.create_note(title, str(data.get("text") or "").strip())
    _sync_notes_gauge()
    return jsonify(db.get_note(note_id)), 201


@app.get("/api/notes/<int:note_id>")
def api_get_note(note_id):
    note = db.get_note(note_id)
    if note is None:
        return jsonify(error="Заметка не найдена"), 404
    return jsonify(note)


@app.put("/api/notes/<int:note_id>")
def api_update_note(note_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is not None and not str(title).strip():
        return jsonify(error="Поле title не может быть пустым"), 400
    try:
        note = db.update_note(
            note_id,
            title=str(title).strip() if title is not None else None,
            text=str(data["text"]).strip() if "text" in data else None,
            done=data.get("done"),
        )
    except sqlite3.Error:
        return jsonify(error="База данных недоступна"), 503
    if note is None:
        return jsonify(error="Заметка не найдена"), 404
    _sync_notes_gauge()
    return jsonify(note)


@app.delete("/api/notes/<int:note_id>")
def api_delete_note(note_id):
    if not db.delete_note(note_id):
        return jsonify(error="Заметка не найдена"), 404
    _sync_notes_gauge()
    return "", 204


@app.get("/api/stats")
def api_stats():
    return jsonify(
        version=__version__,
        notes=db.count_notes(),
        uptime_seconds=round(time.time() - STARTED_AT),
    )


@app.get("/health")
def health():
    """Health check: приложение живо и база отвечает."""
    try:
        notes = db.count_notes()
    except sqlite3.Error:
        return jsonify(status="error", db="unavailable", version=__version__), 503
    return jsonify(
        status="ok",
        db="ok",
        version=__version__,
        notes=notes,
        uptime_seconds=round(time.time() - STARTED_AT, 1),
    )


@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    # Локальный запуск без Docker:  python -m notes_app.app
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
