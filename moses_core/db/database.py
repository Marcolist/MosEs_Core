"""SQLite access layer.

The database stores three things:
- Plugin enablement and per-plugin config (namespaced JSON blobs).
- Layout entries (one per plugin instance).
- OAuth tokens for providers like Google.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS plugins (
    id              TEXT PRIMARY KEY,
    version         TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 0,
    installed_at    TEXT NOT NULL,
    last_run_at     TEXT,
    last_status     TEXT,
    last_error      TEXT
);

CREATE TABLE IF NOT EXISTS plugin_config (
    plugin_id       TEXT NOT NULL,
    key             TEXT NOT NULL,
    value           TEXT NOT NULL,
    PRIMARY KEY (plugin_id, key),
    FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS layout (
    plugin_id       TEXT PRIMARY KEY,
    x               INTEGER NOT NULL,
    y               INTEGER NOT NULL,
    w               INTEGER NOT NULL,
    h               INTEGER NOT NULL,
    FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    provider        TEXT PRIMARY KEY,
    access_token    TEXT NOT NULL,
    refresh_token   TEXT,
    expires_at      TEXT,
    scope           TEXT,
    extra           TEXT
);

CREATE TABLE IF NOT EXISTS cache (
    namespace       TEXT NOT NULL,
    key             TEXT NOT NULL,
    value           TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.path, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
            finally:
                conn.close()

    # --- plugin metadata ----------------------------------------------------
    def upsert_plugin(self, plugin_id: str, version: str, enabled: bool, installed_at: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO plugins(id, version, enabled, installed_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET version=excluded.version""",
                (plugin_id, version, int(enabled), installed_at),
            )

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE plugins SET enabled = ? WHERE id = ?", (int(enabled), plugin_id))

    def delete_plugin(self, plugin_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))

    def list_plugins(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM plugins ORDER BY id")]

    def record_run(self, plugin_id: str, when: str, status: str, error: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE plugins SET last_run_at = ?, last_status = ?, last_error = ? WHERE id = ?",
                (when, status, error, plugin_id),
            )

    # --- per-plugin config --------------------------------------------------
    def config_get(self, plugin_id: str, key: str) -> Any:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM plugin_config WHERE plugin_id = ? AND key = ?",
                (plugin_id, key),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["value"])

    def config_all(self, plugin_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM plugin_config WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def config_set(self, plugin_id: str, key: str, value: Any) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO plugin_config(plugin_id, key, value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(plugin_id, key) DO UPDATE SET value=excluded.value""",
                (plugin_id, key, json.dumps(value)),
            )

    def config_replace(self, plugin_id: str, values: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM plugin_config WHERE plugin_id = ?", (plugin_id,))
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO plugin_config(plugin_id, key, value) VALUES (?, ?, ?)",
                    (plugin_id, key, json.dumps(value)),
                )

    # --- layout -------------------------------------------------------------
    def layout_get(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM layout")]

    def layout_set(self, entries: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM layout")
            for entry in entries:
                conn.execute(
                    "INSERT INTO layout(plugin_id, x, y, w, h) VALUES (?, ?, ?, ?, ?)",
                    (entry["plugin_id"], entry["x"], entry["y"], entry["w"], entry["h"]),
                )

    def layout_upsert(self, plugin_id: str, x: int, y: int, w: int, h: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO layout(plugin_id, x, y, w, h) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(plugin_id) DO UPDATE SET x=excluded.x, y=excluded.y,
                   w=excluded.w, h=excluded.h""",
                (plugin_id, x, y, w, h),
            )

    def layout_remove(self, plugin_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM layout WHERE plugin_id = ?", (plugin_id,))

    # --- oauth --------------------------------------------------------------
    def oauth_set(
        self,
        provider: str,
        access_token: str,
        refresh_token: str | None,
        expires_at: str | None,
        scope: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO oauth_tokens(provider, access_token, refresh_token, expires_at, scope, extra)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(provider) DO UPDATE SET
                     access_token=excluded.access_token,
                     refresh_token=excluded.refresh_token,
                     expires_at=excluded.expires_at,
                     scope=excluded.scope,
                     extra=excluded.extra""",
                (provider, access_token, refresh_token, expires_at, scope, json.dumps(extra or {})),
            )

    def oauth_get(self, provider: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM oauth_tokens WHERE provider = ?", (provider,)
            ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["extra"] = json.loads(out.get("extra") or "{}")
        return out

    def oauth_list(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT provider, expires_at, scope FROM oauth_tokens ORDER BY provider"
            ).fetchall()
        return [dict(r) for r in rows]

    def oauth_delete(self, provider: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM oauth_tokens WHERE provider = ?", (provider,))

    # --- cache --------------------------------------------------------------
    def cache_get(self, namespace: str, key: str, now_iso: str) -> Any:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
        if not row:
            return None
        if row["expires_at"] <= now_iso:
            return None
        return json.loads(row["value"])

    def cache_set(self, namespace: str, key: str, value: Any, expires_at_iso: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO cache(namespace, key, value, expires_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(namespace, key) DO UPDATE SET
                     value=excluded.value, expires_at=excluded.expires_at""",
                (namespace, key, json.dumps(value), expires_at_iso),
            )

    def cache_purge_expired(self, now_iso: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM cache WHERE expires_at <= ?", (now_iso,))

    # --- system settings ----------------------------------------------------
    def system_get(self, key: str, default: Any = None) -> Any:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM system_settings WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return default
        return json.loads(row["value"])

    def system_set(self, key: str, value: Any) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO system_settings(key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, json.dumps(value)),
            )


_DB: Database | None = None


def get_db() -> Database:
    global _DB
    if _DB is None:
        from ..config import settings

        _DB = Database(settings.db_path)
    return _DB
