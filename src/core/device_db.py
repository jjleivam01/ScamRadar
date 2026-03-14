"""
device_db.py — Gestor de base de datos SQLite para dispositivos ESP32 de Yarvis.
Guarda IP, nombre, tipo de sensor y última vez visto.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "yarvis_devices.db"

def _get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea las tablas si no existen."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ip        TEXT NOT NULL UNIQUE,
                name      TEXT NOT NULL,
                type      TEXT NOT NULL DEFAULT 'esp32_security',
                state     TEXT,
                added_at  TEXT NOT NULL,
                last_seen TEXT
            )
        """)
        conn.commit()

def add_device(ip: str, name: str, dtype: str = "esp32_security", state: dict = None) -> dict:
    """Registra un nuevo dispositivo (o actualiza si ya existe la IP)."""
    now = datetime.now().isoformat()
    state_json = json.dumps(state) if state else None
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO devices (ip, name, type, state, added_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                state=excluded.state,
                last_seen=excluded.last_seen
        """, (ip, name, dtype, state_json, now, now))
        conn.commit()
    return get_device(ip)

def get_device(ip: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM devices WHERE ip = ?", (ip,)).fetchone()
        return _row_to_dict(row) if row else None

def list_devices() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM devices ORDER BY added_at DESC").fetchall()
        return [_row_to_dict(r) for r in rows]

def update_state(ip: str, state: dict):
    """Actualiza el último estado conocido del dispositivo."""
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        conn.execute("""
            UPDATE devices SET state = ?, last_seen = ? WHERE ip = ?
        """, (json.dumps(state), now, ip))
        conn.commit()

def delete_device(ip: str):
    with _get_conn() as conn:
        conn.execute("DELETE FROM devices WHERE ip = ?", (ip,))
        conn.commit()

def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("state"):
        try:
            d["state"] = json.loads(d["state"])
        except Exception:
            pass
    return d
