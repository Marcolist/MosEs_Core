"""Smoke tests — the app boots, no plugins installed."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def app_with_temp_data(monkeypatch):
    tmp = tempfile.TemporaryDirectory()
    monkeypatch.setenv("MOSES_DATA_DIR", tmp.name)
    monkeypatch.setenv("MOSES_PLUGINS_DIR", str(Path(tmp.name) / "plugins"))
    monkeypatch.setenv("MOSES_DB_PATH", str(Path(tmp.name) / "moses.db"))

    # Reload settings + db with the new paths.
    from moses_core import config as cfg_mod
    from moses_core.db import database as db_mod

    cfg_mod.settings = cfg_mod.Settings.load()
    db_mod._DB = None  # type: ignore[attr-defined]

    from moses_core.app import create_app

    app = create_app()
    yield app
    tmp.cleanup()


def test_app_boots(app_with_temp_data):
    from fastapi.testclient import TestClient

    with TestClient(app_with_temp_data) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_layout_empty(app_with_temp_data):
    from fastapi.testclient import TestClient

    with TestClient(app_with_temp_data) as client:
        r = client.get("/api/layout")
        assert r.status_code == 200
        body = r.json()
        assert body["columns"] == 12
        assert body["entries"] == []


def test_plugins_empty(app_with_temp_data):
    from fastapi.testclient import TestClient

    with TestClient(app_with_temp_data) as client:
        r = client.get("/api/plugins")
        assert r.status_code == 200
        assert r.json() == {"plugins": []}
