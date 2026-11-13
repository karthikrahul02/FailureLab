import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from app.core.config import settings

_LOCK = RLock()

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _connect() -> sqlite3.Connection:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    if settings.aws_mode:
        return
    with _LOCK, _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, target TEXT NOT NULL,
            scenario TEXT NOT NULL, duration_seconds INTEGER NOT NULL, intensity INTEGER NOT NULL,
            hypothesis TEXT NOT NULL, status TEXT NOT NULL, mode TEXT NOT NULL,
            created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
            resilience_score REAL, anomaly_score REAL, summary TEXT,
            findings_json TEXT NOT NULL DEFAULT '[]', recommendations_json TEXT NOT NULL DEFAULT '[]',
            events_json TEXT NOT NULL DEFAULT '[]', metrics_json TEXT NOT NULL DEFAULT '[]', execution_arn TEXT, fis_experiment_id TEXT
        )""")
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(experiments)").fetchall()}
        if "fis_experiment_id" not in existing_columns:
            conn.execute("ALTER TABLE experiments ADD COLUMN fis_experiment_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at DESC)")

def _decode(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    for source, target in [("findings_json", "findings"), ("recommendations_json", "recommendations"), ("events_json", "events"), ("metrics_json", "metrics")]:
        item[target] = json.loads(item.pop(source, "[]") or "[]")
    return item

def create_experiment(item: dict[str, Any]) -> dict[str, Any]:
    if settings.aws_mode:
        from app.services.aws_adapters import aws_store
        return aws_store.create_experiment(item)
    values = dict(item)
    values.setdefault("created_at", utc_now()); values.setdefault("status", "QUEUED"); values.setdefault("mode", "SIMULATED")
    mapping = {"findings":"findings_json", "recommendations":"recommendations_json", "events":"events_json", "metrics":"metrics_json"}
    columns=[]; params=[]
    for field, value in values.items():
        columns.append(mapping.get(field, field))
        params.append(json.dumps(value, default=str) if field in mapping else value)
    with _LOCK, _connect() as conn:
        conn.execute(f"INSERT INTO experiments ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", params)
    return get_experiment(values["id"])

def update_experiment(experiment_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    if settings.aws_mode:
        from app.services.aws_adapters import aws_store
        return aws_store.update_experiment(experiment_id, patch)
    allowed = {"status", "started_at", "completed_at", "resilience_score", "anomaly_score", "summary", "findings", "recommendations", "events", "metrics", "execution_arn", "fis_experiment_id"}
    clean = {k:v for k,v in patch.items() if k in allowed}
    if not clean: return get_experiment(experiment_id)
    mapping = {"findings":"findings_json", "recommendations":"recommendations_json", "events":"events_json", "metrics":"metrics_json"}
    sets=[]; params=[]
    for key, value in clean.items():
        sets.append(f"{mapping.get(key,key)}=?")
        params.append(json.dumps(value, default=str) if key in mapping else value)
    params.append(experiment_id)
    with _LOCK, _connect() as conn:
        cursor = conn.execute(f"UPDATE experiments SET {','.join(sets)} WHERE id=?", params)
        if cursor.rowcount == 0: return None
    return get_experiment(experiment_id)

def get_experiment(experiment_id: str) -> dict[str, Any] | None:
    if settings.aws_mode:
        from app.services.aws_adapters import aws_store
        return aws_store.get_experiment(experiment_id)
    with _LOCK, _connect() as conn:
        row = conn.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
    return _decode(row) if row else None

def list_experiments(limit: int = 50) -> list[dict[str, Any]]:
    if settings.aws_mode:
        from app.services.aws_adapters import aws_store
        return aws_store.list_experiments(limit)
    with _LOCK, _connect() as conn:
        rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_decode(row) for row in rows]
