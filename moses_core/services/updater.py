"""Core + plugin update manager.

Core updates use git pull from the configured repo; plugin updates use
the PluginInstaller to re-download from the registry.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class ReleaseInfo:
    tag: str
    name: str
    body: str
    published_at: str


class UpdateManager:
    def __init__(self, core_repo: str, channel: str, project_root: Path) -> None:
        self.core_repo = core_repo
        self.channel = channel
        self.project_root = Path(project_root)

    def latest_release(self) -> ReleaseInfo | None:
        url = f"https://api.github.com/repos/{self.core_repo}/releases/latest"
        try:
            req = Request(url, headers={"User-Agent": "MosEs-Core", "Accept": "application/vnd.github+json"})
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("No release info available: %s", exc)
            return None
        return ReleaseInfo(
            tag=data.get("tag_name", ""),
            name=data.get("name", ""),
            body=data.get("body", ""),
            published_at=data.get("published_at", ""),
        )

    def current_version(self) -> str:
        from .. import __version__
        return __version__

    def update_core(self) -> dict[str, Any]:
        """Run git pull + pip install. Caller is responsible for restarting."""
        results: dict[str, Any] = {"started_at": datetime.now(timezone.utc).isoformat()}
        for cmd in (
            ["git", "fetch", "--all", "--tags"],
            ["git", "pull", "--ff-only"],
            ["pip", "install", "-r", "requirements.txt"],
        ):
            r = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            results.setdefault("steps", []).append(
                {"cmd": " ".join(cmd), "code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
            )
            if r.returncode != 0:
                results["status"] = "error"
                return results
        results["status"] = "ok"
        return results
