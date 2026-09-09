"""Journal SQLite local, montants en centimes, écritures atomiques."""
import csv
import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sales (
                session TEXT, source_id TEXT, at TEXT, product_id INTEGER,
                name TEXT, quantity INTEGER, revenue INTEGER, cost INTEGER,
                PRIMARY KEY(session, source_id));
            CREATE TABLE IF NOT EXISTS history (
                session TEXT, at TEXT, product_id INTEGER, name TEXT,
                price INTEGER, phase TEXT);
            CREATE TABLE IF NOT EXISTS events (at TEXT, message TEXT);
        ''')

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)',
                            (key, json.dumps(value, ensure_ascii=False)))

    def commit(self, state, sales=(), points=(), event=None, clear_pending=False):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)',
                            ('state', json.dumps(state, ensure_ascii=False)))
            self.db.executemany('INSERT INTO sales VALUES (?,?,?,?,?,?,?,?)', sales)
            self.db.executemany('INSERT INTO history VALUES (?,?,?,?,?,?)', points)
            if event:
                self.db.execute('INSERT INTO events VALUES (?,?)', event)
            if clear_pending:
                self.db.execute("DELETE FROM kv WHERE key='pending'")

    def sale_ids(self, session):
        return {r[0] for r in self.db.execute(
            'SELECT source_id FROM sales WHERE session=?', (session,))}

    def recent_history(self, session, limit=2400):
        rows = self.db.execute('SELECT * FROM history WHERE session=? ORDER BY rowid DESC LIMIT ?',
                               (session, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def events(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY rowid DESC LIMIT 60')]

    def export(self, folder, state):
        folder = Path(folder) / state['session']
        folder.mkdir(parents=True, exist_ok=True)
        for table, fields in [
            ('sales', ['session', 'source_id', 'at', 'product_id', 'name', 'quantity', 'revenue', 'cost']),
            ('history', ['session', 'at', 'product_id', 'name', 'price', 'phase'])
        ]:
            with (folder / f'{table}.csv').open('w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(fields)
                writer.writerows(self.db.execute(f'SELECT * FROM {table} WHERE session=?',
                                                 (state['session'],)))
        (folder / 'bilan.json').write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
        return str(folder)

    def close(self):
        self.db.close()
