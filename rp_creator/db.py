import contextlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4


def uid():
    return uuid4().hex


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Database:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "world.sqlite3"
        with self.connect() as db:
            db.executescript(Path(__file__).with_name("schema.sql").read_text())

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def rows(self, query, params=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(query, params)]

    def one(self, query, params=()):
        rows = self.rows(query, params)
        return rows[0] if rows else None

    def setting(self, key, default=None):
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, dumps(value)))
