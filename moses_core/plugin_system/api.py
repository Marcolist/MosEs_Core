"""Per-plugin API surface.

Each plugin's backend.py receives a PluginAPI instance via `setup(api)`.
The API namespaces config storage and cache by plugin id, so plugins
cannot accidentally read each other's data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ..db import Database


class _ConfigProxy:
    def __init__(self, db: Database, plugin_id: str) -> None:
        self._db = db
        self._plugin_id = plugin_id

    def get(self, key: str, default: Any = None) -> Any:
        value = self._db.config_get(self._plugin_id, key)
        return default if value is None else value

    def set(self, key: str, value: Any) -> None:
        self._db.config_set(self._plugin_id, key, value)

    def all(self) -> dict[str, Any]:
        return self._db.config_all(self._plugin_id)


class _CacheProxy:
    def __init__(self, db: Database, plugin_id: str) -> None:
        self._db = db
        self._namespace = f"plugin:{plugin_id}"

    def get(self, key: str) -> Any:
        return self._db.cache_get(self._namespace, key, datetime.now(timezone.utc).isoformat())

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._db.cache_set(self._namespace, key, value, expires.isoformat())


class _OAuthProxy:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_token(self, provider: str) -> dict[str, Any] | None:
        from ..services.oauth import OAuthService

        return OAuthService(self._db).get_valid_token(provider)


class _SchedulerProxy:
    def __init__(self, plugin_id: str, scheduler: Any) -> None:
        self._plugin_id = plugin_id
        self._scheduler = scheduler

    def add(self, interval_seconds: int, func: Callable[[], None], job_id: str | None = None) -> str:
        return self._scheduler.add_plugin_job(self._plugin_id, interval_seconds, func, job_id)

    def add_cron(self, cron: dict[str, Any], func: Callable[[], None], job_id: str | None = None) -> str:
        return self._scheduler.add_plugin_cron(self._plugin_id, cron, func, job_id)

    def remove_all(self) -> None:
        self._scheduler.remove_plugin_jobs(self._plugin_id)


class PluginAPI:
    """Object passed to a plugin's `setup(api)` entrypoint."""

    def __init__(self, plugin_id: str, db: Database, scheduler: Any) -> None:
        self.plugin_id = plugin_id
        self.config = _ConfigProxy(db, plugin_id)
        self.cache = _CacheProxy(db, plugin_id)
        self.oauth = _OAuthProxy(db)
        self.scheduler = _SchedulerProxy(plugin_id, scheduler)
        self.log = logging.getLogger(f"moses.plugin.{plugin_id}")
        self._db = db

    def get_other_plugin_data(self, plugin_id: str, key: str) -> Any:
        """Cross-plugin read access (used e.g. by traffic to read calendar)."""
        return self._db.cache_get(f"plugin:{plugin_id}", key, datetime.now(timezone.utc).isoformat())

    def publish(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Publish data for other plugins to consume via cache."""
        self.cache.set(key, value, ttl_seconds)
