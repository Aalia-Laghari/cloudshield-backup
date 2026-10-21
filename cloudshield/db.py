import sqlite3
from pathlib import Path
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self):
        con = sqlite3.connect(self.path, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _init(self):
        with self.connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                note TEXT DEFAULT '',
                replica_a_key TEXT NOT NULL,
                replica_b_key TEXT NOT NULL,
                replica_a_ok INTEGER NOT NULL DEFAULT 0,
                replica_b_ok INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'degraded',
                UNIQUE(filename, version)
            );
            CREATE INDEX IF NOT EXISTS idx_backups_filename ON backups(filename, version DESC);
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                event TEXT NOT NULL,
                filename TEXT DEFAULT '',
                details TEXT DEFAULT ''
            );
            """)

    def create_backup(self, record):
        with self.connect() as con:
            con.execute("""INSERT INTO backups
            (filename,version,created_at,size_bytes,sha256,note,replica_a_key,replica_b_key,
             replica_a_ok,replica_b_ok,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                record["filename"], record["version"], record["created_at"], record["size_bytes"],
                record["sha256"], record["note"], record["replica_a_key"], record["replica_b_key"],
                int(record["replica_a_ok"]), int(record["replica_b_ok"]), record["status"]))
            row = con.execute("SELECT * FROM backups WHERE id=last_insert_rowid()").fetchone()
            return dict(row)

    def update_replica(self, backup_id, replica, ok):
        col = "replica_a_ok" if replica == "A" else "replica_b_ok"
        with self.connect() as con:
            con.execute(f"UPDATE backups SET {col}=? WHERE id=?", (int(ok), backup_id))
            row = con.execute("SELECT replica_a_ok,replica_b_ok FROM backups WHERE id=?", (backup_id,)).fetchone()
            status = "healthy" if row and row["replica_a_ok"] and row["replica_b_ok"] else ("degraded" if row and (row["replica_a_ok"] or row["replica_b_ok"]) else "unavailable")
            con.execute("UPDATE backups SET status=? WHERE id=?", (status, backup_id))

    def get_backup(self, backup_id):
        with self.connect() as con:
            row = con.execute("SELECT * FROM backups WHERE id=?", (backup_id,)).fetchone()
            return dict(row) if row else None

    def list_backups(self, limit=100):
        with self.connect() as con:
            rows = con.execute("SELECT * FROM backups ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
            return [dict(r) for r in rows]

    def list_files(self):
        with self.connect() as con:
            rows = con.execute("""SELECT filename, COUNT(*) AS versions, MAX(created_at) AS latest
            FROM backups GROUP BY filename ORDER BY filename COLLATE NOCASE""").fetchall()
            return [dict(r) for r in rows]

    def list_versions(self, filename):
        with self.connect() as con:
            rows = con.execute("SELECT * FROM backups WHERE filename=? ORDER BY version DESC", (filename,)).fetchall()
            return [dict(r) for r in rows]

    def next_version(self, filename):
        with self.connect() as con:
            row = con.execute("SELECT COALESCE(MAX(version),0)+1 AS v FROM backups WHERE filename=?", (filename,)).fetchone()
            return int(row["v"])

    def add_audit(self, event, filename="", details=""):
        with self.connect() as con:
            con.execute("INSERT INTO audit_log(created_at,event,filename,details) VALUES (?,?,?,?)",
                        (utcnow(), event, filename, details))

    def list_audit(self, limit=500):
        with self.connect() as con:
            rows = con.execute("SELECT created_at AS Time,event AS Event,filename AS File,details AS Details FROM audit_log ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
            return [dict(r) for r in rows]
