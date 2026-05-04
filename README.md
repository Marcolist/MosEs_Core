# MosEs — Modular Everyday Screen

> Your modular everyday screen. Self-hosted family command center: calendar,
> weather, traffic, PV production, crypto prices, news, and more — composed
> from independent plugins, arranged by drag & drop, no cloud, no
> subscriptions.

## What is this

MosEs runs on a Raspberry Pi (or any Linux box), drives a wall-mounted
screen, and shows widgets for whatever you care about. Each widget is a
**plugin**: independent code, independent versioning, installable from the
[plugin registry](https://github.com/marcolist/moses_plugins) at runtime.

This repo contains the **Core**: the FastAPI backend that loads plugins,
the SQLite-backed config store, the Admin UI, and the Dashboard shell.
Plugins live in their own repo.

## Quick start (Pi or any Debian-derived Linux)

```bash
curl -sSL https://raw.githubusercontent.com/marcolist/moses_core/main/deploy/install.sh | sudo bash
```

Then open `http://<pi-ip>:8000/admin` and:

1. **Plugin Store** — install the plugins you want.
2. **Plugin tabs** — configure each (locations, API keys, OAuth).
3. **Layout** — arrange the widgets on the dashboard grid.

The dashboard renders at `http://<pi-ip>:8000/dashboard`.

## Local development

```bash
git clone https://github.com/marcolist/moses_core.git
cd moses_core
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m moses_core
```

Then visit `http://localhost:8000/admin`.

Configuration via env vars:
- `MOSES_DATA_DIR` — where SQLite + plugins live (default `~/.moses`)
- `MOSES_PLUGIN_REGISTRY_REPO` — `owner/repo` pair (default `marcolist/moses_plugins`)
- `MOSES_PLUGIN_REGISTRY_BRANCH` — registry branch to install from (default `main`)
- `MOSES_PORT` (default `8000`) and `MOSES_HOST` (default `0.0.0.0`)

## Architecture

```
┌─────────────────────────────────────────────┐
│  Dashboard (Chromium kiosk → /dashboard)    │
└─────────▲───────────────────────────────────┘
          │ widgets (frontend.js per plugin)
┌─────────┴───────────────────────────────────┐
│  FastAPI Core                               │
│  ├── Plugin Registry / Loader / Installer   │
│  ├── Per-plugin config + cache (SQLite)     │
│  ├── Scheduler (APScheduler)                │
│  ├── OAuth (Google)                         │
│  ├── Layout API                             │
│  └── Update Manager (Core + Plugins)        │
└─────────▲───────────────────────────────────┘
          │
┌─────────┴───────────────────────────────────┐
│  Admin UI (browser → /admin)                │
│  Plugin Store · Layout Editor · Plugin Tabs │
│  · OAuth · System                           │
└─────────────────────────────────────────────┘
```

Plugins ship a manifest (`plugin.json`) plus optional `backend.py`,
`frontend.js`, and `admin.js` modules. Backends register themselves
under `/api/plugins/<id>/...` and receive a per-plugin API surface
(config, cache, OAuth, scheduler).

See [moses_plugins/README.md](https://github.com/marcolist/moses_plugins#readme)
for the plugin authoring guide.

## Tech stack

| Layer            | Tech                                  |
|------------------|---------------------------------------|
| Backend          | FastAPI · Uvicorn · APScheduler · SQLite |
| Plugin loading   | Dynamic Python import + APIRouter     |
| Admin frontend   | HTML + Alpine.js + GridStack          |
| Dashboard frontend | Vanilla JS modules + CSS Grid       |
| Deployment       | systemd · Chromium `--kiosk`          |

## Roadmap

See the project description for the full plan. The first wave ships the
plugin system, all eight officially-supported plugins (clock, weather,
calendar, traffic, pv_fusionsolar, pv_anker, crypto, news), the Admin UI,
and the Dashboard shell.
