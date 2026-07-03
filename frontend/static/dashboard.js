/* MosEs Dashboard — loads active plugins in saved layout. */

const dashboard = document.getElementById("dashboard");

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

function placeWidget(el, entry) {
  el.style.gridColumn = `${entry.x + 1} / span ${entry.w}`;
  el.style.gridRow = `${entry.y + 1} / span ${entry.h}`;
}

class WidgetHost {
  constructor(pluginId, manifest) {
    this.pluginId = pluginId;
    this.manifest = manifest;
    this.el = document.createElement("section");
    this.el.className = "widget widget-loading";
    this.el.dataset.plugin = pluginId;
    const title = document.createElement("div");
    title.className = "title";
    title.textContent = manifest.name;
    const body = document.createElement("div");
    body.className = "body";
    this.el.append(title, body);
    this.body = body;
  }

  setError(msg) {
    this.body.innerHTML = `<div class="widget-error">${msg}</div>`;
    this.el.classList.remove("widget-loading");
  }

  setReady() { this.el.classList.remove("widget-loading"); }

  async fetchPluginData(path = "") {
    return fetchJSON(`/api/plugins/${this.pluginId}${path}`);
  }
}

async function loadPlugin(host, refreshSeconds) {
  try {
    const mod = await import(`/api/plugins/${host.pluginId}/asset/frontend.js`);
    if (typeof mod.mount !== "function") {
      host.setError("frontend.js missing mount()");
      return;
    }
    const widget = await mod.mount({
      el: host.body,
      pluginId: host.pluginId,
      manifest: host.manifest,
      fetchData: (path) => host.fetchPluginData(path),
    });
    host.setReady();
    if (refreshSeconds && refreshSeconds > 0 && widget && typeof widget.refresh === "function") {
      setInterval(() => {
        try { widget.refresh(); } catch (e) { console.warn(e); }
      }, refreshSeconds * 1000);
    }
  } catch (err) {
    console.error("Plugin load failed:", host.pluginId, err);
    host.setError(`Plugin failed: ${err.message}`);
  }
}

async function bootstrap() {
  const [active, layout] = await Promise.all([
    fetchJSON("/api/plugins/active"),
    fetchJSON("/api/layout"),
  ]);
  const manifestById = Object.fromEntries(active.plugins.map((p) => [p.id, p.manifest]));
  const positionedIds = new Set();
  for (const entry of layout.entries) {
    const manifest = manifestById[entry.plugin_id];
    if (!manifest) continue;
    const host = new WidgetHost(entry.plugin_id, manifest);
    placeWidget(host.el, entry);
    dashboard.appendChild(host.el);
    loadPlugin(host, manifest.refresh_interval_seconds || 0);
    positionedIds.add(entry.plugin_id);
  }
  // Plugins active but missing from layout → drop into next free row.
  let nextY = layout.entries.reduce((m, e) => Math.max(m, e.y + e.h), 0);
  let nextX = 0;
  for (const p of active.plugins) {
    if (positionedIds.has(p.id)) continue;
    const w = p.manifest.widget?.default_width ?? 2;
    const h = p.manifest.widget?.default_height ?? 1;
    if (nextX + w > 12) { nextX = 0; nextY += h; }
    const host = new WidgetHost(p.id, p.manifest);
    placeWidget(host.el, { x: nextX, y: nextY, w, h });
    dashboard.appendChild(host.el);
    loadPlugin(host, p.manifest.refresh_interval_seconds || 0);
    nextX += w;
  }
}

bootstrap().catch((err) => {
  console.error("Dashboard bootstrap failed:", err);
  document.body.innerHTML = `<pre style="color:#f87171;padding:24px">${err.stack || err}</pre>`;
});
