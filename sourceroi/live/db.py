"""SQLite experiment history, entirely local to the workspace."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


def db_path(cfg: dict) -> Path:
    from .config import secure_path
    root = Path(cfg['_root']).resolve()
    dest = secure_path(root, '.sourceroi', must_exist=False)
    dest.mkdir(exist_ok=True)
    for name in ('runs.sqlite3', 'runs.sqlite3-wal', 'runs.sqlite3-shm'):
        if (dest / name).is_symlink():
            raise ValueError('Database symlinks are forbidden')
    return secure_path(root, '.sourceroi/runs.sqlite3', must_exist=False)


@contextmanager
def connect(cfg: dict):
    db = sqlite3.connect(db_path(cfg), timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('''CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            status TEXT NOT NULL, mode TEXT NOT NULL, exclusions TEXT NOT NULL,
            report TEXT, error TEXT)''')
        db.commit()
        yield db
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def begin(cfg: dict, mode: str, excluded: list[str]) -> str:
    rid = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    with connect(cfg) as conn:
        conn.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)',
                     (rid, now, now, 'running', mode, json.dumps(excluded), None, None))
        conn.commit()
    return rid


def finish(cfg: dict, run_id: str, report: dict | None, error: str | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with connect(cfg) as conn:
        conn.execute('UPDATE runs SET status=?, updated_at=?, report=?, error=? WHERE id=?',
                     ('failed' if error else 'completed', now,
                      json.dumps(report, ensure_ascii=False) if report else None, error, run_id))
        conn.commit()


def checkpoint(cfg: dict, run_id: str, report: dict):
    """Retain completed evidence during a running study without marking it finished."""
    now = datetime.now(timezone.utc).isoformat()
    with connect(cfg) as conn:
        conn.execute('UPDATE runs SET updated_at=?,report=? WHERE id=? AND status=?',
                     (now, json.dumps(report, ensure_ascii=False), run_id, 'running'))
        conn.commit()


def get(cfg: dict, run_id: str) -> dict | None:
    with connect(cfg) as conn:
        row = conn.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
        return _row(row) if row else None


def list_runs(cfg: dict, limit: int = 30, *, offset: int = 0) -> list[dict]:
    with connect(cfg) as conn:
        rows = conn.execute('SELECT * FROM runs ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?', (max(1, min(limit, 100)), max(0, min(offset, 100000)))).fetchall()
        out = []
        for row in rows:
            item = _row(row)
            if item['report']:
                item['metrics'] = item['report'].get('variants', [{}])[0].get('metrics', {})
                item.pop('report')
            out.append(item)
        return out


def _row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item['exclusions'] = json.loads(item['exclusions'])
    if item['report']:
        item['report'] = json.loads(item['report'])
    return item


def mark_interrupted(cfg: dict):
    """Mark orphaned runs after a previous process died during a run."""
    now = datetime.now(timezone.utc).isoformat()
    with connect(cfg) as conn:
        conn.execute("UPDATE runs SET status='failed',updated_at=?,error='Interrupted before completion' WHERE status='running'", (now,))
        conn.commit()


def save_decision(cfg, report):
    """Content-bound immutable offline result; duplicate submissions reuse history."""
    now=datetime.now(timezone.utc).isoformat()
    with connect(cfg) as conn:
        conn.execute('INSERT OR IGNORE INTO runs VALUES (?,?,?,?,?,?,?,?)',
            (report['id'],now,now,'completed','knowledge_decision','[]',json.dumps(report,ensure_ascii=False),None))
        row=conn.execute('SELECT report,mode,status FROM runs WHERE id=?',(report['id'],)).fetchone()
        if row['mode']!='knowledge_decision' or row['status']!='completed':raise ValueError('Conflicting immutable decision identity')
        conn.commit()
        return json.loads(row['report'])


def backup(cfg: dict, destination: str | Path) -> dict:
    """Consistent SQLite online backup; exclusive output, no restore over live state.

    Snapshots/documents/config must be backed up separately while writes are stopped.
    The digest detects later drift; it is not an authenticated audit signature.
    """
    import hashlib
    import os
    destination = Path(destination)
    if not destination.parent.is_dir():
        raise ValueError('Backup parent must exist')
    if destination.resolve().is_relative_to(Path(cfg['_root']).resolve()):
        raise ValueError('Backup must be outside the active workspace')
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with connect(cfg) as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed')
                count = target.execute('SELECT count(*) FROM runs').fetchone()[0]
            finally:
                target.close()
        return {'status': 'VERIFIED', 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                'runs': count, 'scope': 'SQLite only; source/config/snapshot files excluded'}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
