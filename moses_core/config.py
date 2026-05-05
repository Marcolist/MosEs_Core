"""Application-level configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(key: str, default: Path) -> Path:
    raw = os.getenv(key)
    return Path(raw).expanduser() if raw else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    plugins_dir: Path
    db_path: Path
    plugin_registry_repo: str
    plugin_registry_branch: str
    core_repo: str
    update_channel: str
    host: str
    port: int

    @classmethod
    def load(cls) -> "Settings":
        data_dir = _env_path("MOSES_DATA_DIR", Path.home() / ".moses")
        data_dir.mkdir(parents=True, exist_ok=True)
        plugins_dir = _env_path("MOSES_PLUGINS_DIR", data_dir / "plugins")
        plugins_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            data_dir=data_dir,
            plugins_dir=plugins_dir,
            db_path=_env_path("MOSES_DB_PATH", data_dir / "moses.db"),
            plugin_registry_repo=os.getenv(
                "MOSES_PLUGIN_REGISTRY_REPO", "Marcolist/MosEs_plugins"
            ),
            plugin_registry_branch=os.getenv("MOSES_PLUGIN_REGISTRY_BRANCH", "master"),
            core_repo=os.getenv("MOSES_CORE_REPO", "Marcolist/MosEs_Core"),
            update_channel=os.getenv("MOSES_UPDATE_CHANNEL", "stable"),
            host=os.getenv("MOSES_HOST", "0.0.0.0"),
            port=int(os.getenv("MOSES_PORT", "8000")),
        )


settings = Settings.load()
