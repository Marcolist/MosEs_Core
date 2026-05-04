"""Installs plugins by downloading them from a GitHub plugin registry repo.

Strategy: download a tarball of the requested ref, extract only the
matching plugin subdirectory into the local plugins dir.
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class RegistryEntry:
    id: str
    name: str
    version: str
    description: str
    author: str
    requires_api_key: bool
    requires_oauth: bool
    dependencies: list[str]
    raw: dict[str, Any]


class PluginInstaller:
    def __init__(self, registry_repo: str, registry_branch: str, plugins_dir: Path) -> None:
        self.registry_repo = registry_repo
        self.registry_branch = registry_branch
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- registry ----------------
    def index_url(self) -> str:
        return (
            f"https://raw.githubusercontent.com/{self.registry_repo}/"
            f"{self.registry_branch}/registry.json"
        )

    def fetch_index(self) -> list[RegistryEntry]:
        req = Request(self.index_url(), headers={"User-Agent": "MosEs-Core"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        plugins = data.get("plugins", []) if isinstance(data, dict) else data
        out: list[RegistryEntry] = []
        for entry in plugins:
            out.append(
                RegistryEntry(
                    id=entry["id"],
                    name=entry.get("name", entry["id"]),
                    version=entry.get("version", "0.0.0"),
                    description=entry.get("description", ""),
                    author=entry.get("author", "unknown"),
                    requires_api_key=bool(entry.get("requires_api_key", False)),
                    requires_oauth=bool(entry.get("requires_oauth", False)),
                    dependencies=list(entry.get("dependencies", [])),
                    raw=entry,
                )
            )
        return out

    # ---------------- install / update ----------------
    def install(self, plugin_id: str) -> Path:
        target = self.plugins_dir / plugin_id
        if target.exists():
            shutil.rmtree(target)
        tarball_url = (
            f"https://codeload.github.com/{self.registry_repo}/tar.gz/refs/heads/"
            f"{self.registry_branch}"
        )
        req = Request(tarball_url, headers={"User-Agent": "MosEs-Core"})
        with urlopen(req, timeout=120) as resp:
            blob = resp.read()
        self._extract_plugin_from_tar(blob, plugin_id, target)
        return target

    def _extract_plugin_from_tar(self, blob: bytes, plugin_id: str, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            prefix = None
            for member in tar.getmembers():
                parts = member.name.split("/")
                if len(parts) >= 3 and parts[1] == "plugins" and parts[2] == plugin_id:
                    prefix = "/".join(parts[:3]) + "/"
                    break
            if prefix is None:
                raise FileNotFoundError(f"Plugin {plugin_id} not found in registry")
            for member in tar.getmembers():
                if not member.name.startswith(prefix):
                    continue
                rel = member.name[len(prefix):]
                if not rel:
                    continue
                dest = target / rel
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    dest.write_bytes(f.read())

    def remove(self, plugin_id: str) -> None:
        target = self.plugins_dir / plugin_id
        if target.exists():
            shutil.rmtree(target)
