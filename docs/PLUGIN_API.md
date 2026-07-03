# Plugin API

A plugin is a directory containing at minimum a `plugin.json` manifest
and a `frontend.js` ES module. Backend logic and an admin extension
are optional.

## Files

```
my_plugin/
├── plugin.json      ← manifest, settings_schema (required)
├── backend.py       ← FastAPI integration (optional)
├── frontend.js      ← dashboard widget (required for dashboard rendering)
├── admin.js         ← optional admin tab extension
└── README.md
```

## plugin.json

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "...",
  "author": "Your Name",
  "requires_api_key": false,
  "requires_oauth": false,
  "default_enabled": false,
  "refresh_interval_seconds": 600,
  "dependencies": [],
  "has_backend": true,
  "has_admin": false,
  "widget": {
    "default_width": 4, "default_height": 2,
    "min_width": 2, "max_width": 12,
    "min_height": 1, "max_height": 6,
    "resizable": true
  },
  "settings_schema": [
    { "key": "location", "type": "string", "label": "Location", "required": true }
  ]
}
```

Field types: `string`, `password`, `number`, `boolean`, `select`, `multiselect`, `textarea`.

## Backend (`backend.py`)

```python
from fastapi import APIRouter

def setup(api):
    router = APIRouter()

    @router.get("/data")
    def data():
        return api.cache.get("data") or _refresh(api)

    api.scheduler.add(api.config.get("refresh_interval_seconds", 600), lambda: _refresh(api))
    return router
```

`api` provides:

| Member            | Purpose |
|-------------------|---------|
| `api.config.get/set/all` | per-plugin namespaced config |
| `api.cache.get/set`      | TTL cache (SQLite-backed) |
| `api.oauth.get_token(p)` | get a refreshed token for provider `p` |
| `api.scheduler.add(s, f)`| add interval job (seconds) |
| `api.scheduler.add_cron(d, f)` | add APScheduler cron job |
| `api.publish(k, v, ttl)` | publish data for other plugins |
| `api.get_other_plugin_data(p, k)` | read data published by plugin `p` |
| `api.log`                | logger named `moses.plugin.<id>` |

Routes registered on the returned `APIRouter` are mounted under `/api/plugins/<id>`.

## Frontend (`frontend.js`)

```js
export async function mount({ el, fetchData, manifest, pluginId }) {
  const data = await fetchData("/data");          // calls /api/plugins/<id>/data
  el.innerHTML = `<strong>${data.value}</strong>`;
  return {
    refresh: async () => { /* re-fetch + redraw */ },
    destroy: () => { /* cleanup */ },
  };
}
```

The dashboard auto-calls `refresh()` every `refresh_interval_seconds`.

## Admin extension (`admin.js`)

```js
export function mountAdmin({ host, pluginId, api }) {
  // Render extra UI under host. Use api.callPlugin(path, opts) and api.save().
}
```

## Cross-plugin data

Use `api.publish("key", value, ttl)` and `api.get_other_plugin_data("other_id", "key")`
for one-way data flow. Example: `calendar` publishes events with locations,
`traffic` consumes them.
