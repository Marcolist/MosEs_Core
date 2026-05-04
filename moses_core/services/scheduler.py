"""Wraps APScheduler with per-plugin job tracking."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, db: Any | None = None) -> None:
        self._sched = AsyncIOScheduler(timezone="UTC")
        self._jobs_by_plugin: dict[str, list[str]] = {}
        self._db = db

    def start(self) -> None:
        if not self._sched.running:
            self._sched.start()

    def shutdown(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)

    def add_plugin_job(
        self,
        plugin_id: str,
        interval_seconds: int,
        func: Callable[[], None],
        job_id: str | None = None,
    ) -> str:
        job_id = job_id or f"{plugin_id}:default"
        wrapped = self._wrap(plugin_id, func)
        self._sched.add_job(
            wrapped,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=job_id,
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc),
        )
        self._jobs_by_plugin.setdefault(plugin_id, []).append(job_id)
        return job_id

    def add_plugin_cron(
        self,
        plugin_id: str,
        cron: dict[str, Any],
        func: Callable[[], None],
        job_id: str | None = None,
    ) -> str:
        job_id = job_id or f"{plugin_id}:cron:{len(self._jobs_by_plugin.get(plugin_id, []))}"
        wrapped = self._wrap(plugin_id, func)
        self._sched.add_job(
            wrapped,
            trigger=CronTrigger(**cron),
            id=job_id,
            replace_existing=True,
        )
        self._jobs_by_plugin.setdefault(plugin_id, []).append(job_id)
        return job_id

    def remove_plugin_jobs(self, plugin_id: str) -> None:
        for job_id in self._jobs_by_plugin.pop(plugin_id, []):
            try:
                self._sched.remove_job(job_id)
            except Exception:  # noqa: BLE001
                pass

    def _wrap(self, plugin_id: str, func: Callable[[], Any]) -> Callable[[], Any]:
        async def runner() -> None:
            now = datetime.now(timezone.utc).isoformat()
            try:
                result = func()
                if hasattr(result, "__await__"):
                    await result
                if self._db is not None:
                    self._db.record_run(plugin_id, now, "ok", None)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Plugin %s job failed: %s", plugin_id, exc)
                if self._db is not None:
                    self._db.record_run(plugin_id, now, "error", str(exc))

        return runner
