"""Plugin manifest parsing and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SettingField:
    key: str
    type: str  # string | password | number | boolean | select | multiselect | textarea
    label: str
    required: bool = False
    default: Any = None
    options: list[dict[str, Any]] = field(default_factory=list)
    placeholder: str | None = None
    help: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SettingField":
        return cls(
            key=data["key"],
            type=data.get("type", "string"),
            label=data.get("label", data["key"]),
            required=bool(data.get("required", False)),
            default=data.get("default"),
            options=data.get("options", []),
            placeholder=data.get("placeholder"),
            help=data.get("help"),
        )


@dataclass
class WidgetSpec:
    default_width: int = 2
    default_height: int = 1
    min_width: int = 1
    max_width: int = 12
    min_height: int = 1
    max_height: int = 12
    resizable: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WidgetSpec":
        return cls(
            default_width=int(data.get("default_width", 2)),
            default_height=int(data.get("default_height", 1)),
            min_width=int(data.get("min_width", 1)),
            max_width=int(data.get("max_width", 12)),
            min_height=int(data.get("min_height", 1)),
            max_height=int(data.get("max_height", 12)),
            resizable=bool(data.get("resizable", True)),
        )


@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    description: str
    author: str
    requires_api_key: bool
    requires_oauth: bool
    oauth_provider: str | None
    default_enabled: bool
    refresh_interval_seconds: int
    dependencies: list[str]
    widget: WidgetSpec
    settings_schema: list[SettingField]
    has_backend: bool
    has_frontend: bool
    has_admin: bool
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        required = ["id", "name", "version"]
        for key in required:
            if key not in data:
                raise ValueError(f"plugin.json missing required key: {key}")
        return cls(
            id=data["id"],
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            requires_api_key=bool(data.get("requires_api_key", False)),
            requires_oauth=bool(data.get("requires_oauth", False)),
            oauth_provider=data.get("oauth_provider"),
            default_enabled=bool(data.get("default_enabled", False)),
            refresh_interval_seconds=int(data.get("refresh_interval_seconds", 0)),
            dependencies=list(data.get("dependencies", [])),
            widget=WidgetSpec.from_dict(data.get("widget", {})),
            settings_schema=[SettingField.from_dict(f) for f in data.get("settings_schema", [])],
            has_backend=bool(data.get("has_backend", True)),
            has_frontend=bool(data.get("has_frontend", True)),
            has_admin=bool(data.get("has_admin", False)),
            raw=data,
        )

    @classmethod
    def load(cls, path: Path) -> "PluginManifest":
        with path.open("r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "requires_api_key": self.requires_api_key,
            "requires_oauth": self.requires_oauth,
            "oauth_provider": self.oauth_provider,
            "default_enabled": self.default_enabled,
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "dependencies": self.dependencies,
            "widget": self.widget.__dict__,
            "settings_schema": [f.__dict__ for f in self.settings_schema],
            "has_backend": self.has_backend,
            "has_frontend": self.has_frontend,
            "has_admin": self.has_admin,
        }
