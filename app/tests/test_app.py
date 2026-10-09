"""Тесты REST API: создание, чтение, редактирование, удаление, health, метрики.

Локальный запуск (без Docker):
    cd app
    python -m unittest discover -s tests -v

В контейнере эти же тесты запускает ci/build.sh.
"""
import os
import pathlib
import re
import sqlite3
import sys
import tempfile
import unittest
import warnings
from contextlib import closing

warnings.simplefilter("ignore", ResourceWarning)

# База для тестов — во временной папке; задаётся ДО импорта приложения,
# потому что notes_app.db читает DB_PATH в момент импорта.
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="notes-tests-"))
os.environ["DB_PATH"] = str(_TMP / "test.db")

from notes_app.app import app  # noqa: E402


def _counter_value(metrics_text: str) -> int:
    """Достаёт значение счётчика app_http_requests_total из /metrics."""
    match = re.search(
        r"^app_http_requests_total\s+([\d.]+)", metrics_text, re.MULTILINE
    )
    return int(float(match.group(1)))


class NotesApiTests(unittest.TestCase):
    def setUp(self):
        with closing(sqlite3.connect(os.environ["DB_PATH"])) as conn:
            conn.execute("DELETE FROM notes")
        self.client = app.test_client()

    def test_index_served(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Заметки", resp.get_data(as_text=True))

    def test_create_and_list(self):
        resp = self.client.post(
            "/api/notes", json={"title": "Купить кофе", "text": "зёрна, не молотый"}
        )
        self.assertEqual(resp.status_code, 201)
        created = resp.get_json()
        self.assertEqual(created["title"], "Купить кофе")
        self.assertEqual(created["done"], 0)

        notes = self.client.get("/api/notes").get_json()
        self.assertTrue(any(n["id"] == created["id"] for n in notes))

    def test_create_requires_title(self):
        resp = self.client.post("/api/notes", json={"title": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_get_single_note(self):
        created = self.client.post(
            "/api/notes", json={"title": "прочитать"}
        ).get_json()
        resp = self.client.get(f"/api/notes/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["title"], "прочитать")

    def test_edit_note(self):
        note = self.client.post(
            "/api/notes", json={"title": "старый заголовок"}
        ).get_json()
        resp = self.client.put(
            f"/api/notes/{note['id']}",
            json={"title": "новый заголовок", "text": "и текст", "done": True},
        )
        self.assertEqual(resp.status_code, 200)
        edited = resp.get_json()
        self.assertEqual(edited["title"], "новый заголовок")
        self.assertEqual(edited["text"], "и текст")
        self.assertEqual(edited["done"], 1)

    def test_edit_missing_returns_404(self):
        resp = self.client.put("/api/notes/999999", json={"title": "x"})
        self.assertEqual(resp.status_code, 404)

    def test_delete_note(self):
        note = self.client.post(
            "/api/notes", json={"title": "на удаление"}
        ).get_json()
        self.assertEqual(
            self.client.delete(f"/api/notes/{note['id']}").status_code, 204
        )
        self.assertEqual(
            self.client.get(f"/api/notes/{note['id']}").status_code, 404
        )

    def test_health_ok(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["db"], "ok")
        self.assertIn("version", body)

    def test_stats(self):
        body = self.client.get("/api/stats").get_json()
        self.assertIn("notes", body)
        self.assertIn("uptime_seconds", body)

    def test_metrics_counter_grows(self):
        before = _counter_value(self.client.get("/metrics").get_data(as_text=True))
        self.client.get("/api/notes")
        after = _counter_value(self.client.get("/metrics").get_data(as_text=True))
        self.assertGreaterEqual(after, before + 2)  # сам /metrics тоже считается

    def test_metrics_has_app_metrics(self):
        text = self.client.get("/metrics").get_data(as_text=True)
        self.assertIn("app_notes_count", text)
        self.assertIn("python_info", text)

    @unittest.skipIf(
        sys.platform == "win32",
        "process_*-метрики prometheus_client на Windows требуют psutil; "
        "в Linux-контейнере они есть",
    )
    def test_metrics_has_process_metrics(self):
        text = self.client.get("/metrics").get_data(as_text=True)
        self.assertIn("process_resident_memory_bytes", text)


if __name__ == "__main__":
    unittest.main()
