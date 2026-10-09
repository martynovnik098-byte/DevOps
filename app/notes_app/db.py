"""Хранилище заметок на SQLite.

Путь к файлу базы берётся из переменной окружения DB_PATH,
поэтому в контейнере данные выносятся в docker volume и
переживают пересоздание контейнера.
"""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "notes.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL,
    text       TEXT    NOT NULL DEFAULT '',
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
)
"""


def init_db() -> None:
    """Создаёт таблицу notes, если её ещё нет."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(_SCHEMA)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _query(sql: str, params=(), one: bool = False):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    records = [dict(row) for row in rows]
    if one:
        return records[0] if records else None
    return records


def _exec(sql: str, params=()) -> int:
    """Выполняет запрос на изменение, возвращает число затронутых строк."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount


def list_notes():
    return _query("SELECT * FROM notes ORDER BY done, id DESC")


def get_note(note_id: int):
    return _query("SELECT * FROM notes WHERE id = ?", (note_id,), one=True)


def count_notes() -> int:
    return _query("SELECT COUNT(*) AS n FROM notes", one=True)["n"]


def create_note(title: str, text: str = "") -> int:
    now = _utcnow()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute(
            "INSERT INTO notes (title, text, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, text, now, now),
        )
        conn.commit()
        return cursor.lastrowid


def update_note(note_id: int, title: str = None, text: str = None, done: bool = None):
    """Обновляет только переданные поля, остальные не трогает."""
    note = get_note(note_id)
    if note is None:
        return None
    new_title = note["title"] if title is None else title
    new_text = note["text"] if text is None else text
    new_done = note["done"] if done is None else int(bool(done))
    _exec(
        "UPDATE notes SET title = ?, text = ?, done = ?, updated_at = ? WHERE id = ?",
        (new_title, new_text, new_done, _utcnow(), note_id),
    )
    return get_note(note_id)


def delete_note(note_id: int) -> bool:
    return _exec("DELETE FROM notes WHERE id = ?", (note_id,)) > 0
