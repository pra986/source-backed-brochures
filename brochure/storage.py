"""SQLite-backed source cache and immutable run snapshots."""
import json
import sqlite3
import time
import uuid
from pathlib import Path

class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'brochures.sqlite3'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created REAL, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, created REAL, data TEXT NOT NULL)')
    def connect(self):
        return sqlite3.connect(self.path, timeout=10)
    def cached(self, url):
        with self.connect() as db:
            row = db.execute('SELECT created, data FROM cache WHERE url=?', (url,)).fetchone()
        return json.loads(row[1]) if row and time.time()-row[0] < 3600 else None
    def cache(self, url, page):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO cache VALUES (?, ?, ?)', (url, time.time(), json.dumps(page)))
    def save(self, run):
        run = dict(run, id=uuid.uuid4().hex)
        with self.connect() as db:
            db.execute('INSERT INTO runs VALUES (?, ?, ?)', (run['id'], run['created_at'], json.dumps(run)))
        return run
    def get(self, run_id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM runs WHERE id=?', (run_id,)).fetchone()
        return json.loads(row[0]) if row else None
    def recent(self):
        with self.connect() as db:
            rows = db.execute('SELECT id, created, data FROM runs ORDER BY created DESC LIMIT 30').fetchall()
        return [{"id": r[0], "created_at": r[1], "company": json.loads(r[2])['company'], "demo": json.loads(r[2])['demo']} for r in rows]
