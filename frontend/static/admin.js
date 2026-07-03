/* MosEs Admin UI — Alpine.js controller */

function adminApp() {
  return {
    tab: "store",
    storePlugins: [],
    installedPlugins: [],
    configValues: {},
    configStatus: {},
    layoutGrid: null,
    layoutStatus: "",
    google: { client_id: "", client_secret: "", client_secret_set: false },
    oauthProviders: [],
    system: { version: "", channel: "" },
    updateInfo: null,
    schedule: { enabled: false, on_time: "06:00", off_time: "23:00" },
    pluginAdminModules: {},

    async init() {
      await this.loadInstalled();
      await this.loadStore();
      await this.loadOAuth();
      await this.loadSystem();
      const persisted = sessionStorage.getItem("moses-tab");
      if (persisted) this.tab = persisted;
    },

    setTab(t) {
      this.tab = t;
      sessionStorage.setItem("moses-tab", t);
      if (t === "layout") this.$nextTick(() => this.initLayoutGrid());
      if (t.startsWith("plugin:")) {
        const id = t.slice("plugin:".length);
        this.$nextTick(() => this.mountPluginAdmin(id));
      }
    },

    async fetchJSON(url, opts = {}) {
      const res = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...opts,
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    },

    async loadInstalled() {
      const data = await this.fetchJSON("/api/plugins");
      this.installedPlugins = data.plugins;
      for (const p of this.installedPlugins) {
        if (!this.configValues[p.manifest.id]) {
          const cfg = await this.fetchJSON(`/api/plugins/${p.manifest.id}/config`);
          const values = { ...cfg.config };
          for (const f of p.manifest.settings_schema) {
            if (values[f.key] === undefined) values[f.key] = f.default ?? "";
          }
          this.configValues[p.manifest.id] = values;
        }
      }
    },

    async loadStore() {
      try {
        const data = await this.fetchJSON("/api/plugins/store");
        this.storePlugins = data.plugins;
      } catch (err) {
        console.warn("Plugin store unavailable:", err);
        this.storePlugins = [];
      }
    },

    async install(id) {
      await this.fetchJSON("/api/plugins/install", {
        method: "POST",
        body: JSON.stringify({ id }),
      });
      await this.loadInstalled();
      await this.loadStore();
    },

    async update(id) {
      await this.fetchJSON(`/api/plugins/${id}/update`, { method: "POST" });
      await this.loadInstalled();
      await this.loadStore();
    },

    async remove(id) {
      if (!confirm(`Remove plugin "${id}"?`)) return;
      await this.fetchJSON(`/api/plugins/${id}`, { method: "DELETE" });
      delete this.configValues[id];
      await this.loadInstalled();
      await this.loadStore();
    },

    async toggleEnabled(id, enabled) {
      const path = enabled ? "enable" : "disable";
      await this.fetchJSON(`/api/plugins/${id}/${path}`, { method: "POST" });
      await this.loadInstalled();
    },

    async saveConfig(id) {
      this.configStatus[id] = "Saving…";
      try {
        await this.fetchJSON(`/api/plugins/${id}/config`, {
          method: "PUT",
          body: JSON.stringify({ config: this.configValues[id] }),
        });
        this.configStatus[id] = "Saved";
        setTimeout(() => (this.configStatus[id] = ""), 2000);
      } catch (err) {
        this.configStatus[id] = "Error: " + err.message;
      }
    },

    async mountPluginAdmin(pluginId) {
      const host = document.getElementById(`plugin-extra-${pluginId}`);
      if (!host || host.dataset.mounted === "1") return;
      try {
        const mod = await import(`/api/plugins/${pluginId}/asset/admin.js`);
        if (mod && typeof mod.mountAdmin === "function") {
          mod.mountAdmin({
            host,
            pluginId,
            api: {
              getConfig: () => this.configValues[pluginId],
              setConfig: (cfg) => Object.assign(this.configValues[pluginId], cfg),
              save: () => this.saveConfig(pluginId),
              callPlugin: (path, opts) =>
                this.fetchJSON(`/api/plugins/${pluginId}${path}`, opts),
            },
          });
          host.dataset.mounted = "1";
        }
      } catch (err) {
        // No admin.js for this plugin — that's fine.
      }
    },

    // ---- layout ----
    async initLayoutGrid() {
      if (this.layoutGrid) {
        this.layoutGrid.destroy(false);
        this.layoutGrid = null;
      }
      const layout = await this.fetchJSON("/api/layout");
      const installedById = Object.fromEntries(
        this.installedPlugins.map((p) => [p.manifest.id, p])
      );
      const items = layout.entries.map((e) => {
        const m = installedById[e.plugin_id]?.manifest;
        return {
          x: e.x, y: e.y, w: e.w, h: e.h,
          id: e.plugin_id,
          minW: m?.widget?.min_width ?? 1,
          maxW: m?.widget?.max_width ?? 12,
          minH: m?.widget?.min_height ?? 1,
          maxH: m?.widget?.max_height ?? 12,
          noResize: !(m?.widget?.resizable ?? true),
          content: `<strong>${m?.name ?? e.plugin_id}</strong>`,
        };
      });
      this.layoutGrid = GridStack.init(
        { column: layout.columns, cellHeight: 80, float: true, animate: true },
        "#layout-grid"
      );
      this.layoutGrid.load(items);
    },

    async saveLayout() {
      if (!this.layoutGrid) return;
      const items = this.layoutGrid.save(false);
      const entries = items.map((i) => ({
        plugin_id: i.id,
        x: i.x, y: i.y, w: i.w, h: i.h,
      }));
      await this.fetchJSON("/api/layout", {
        method: "PUT",
        body: JSON.stringify({ entries }),
      });
      this.layoutStatus = "Saved";
      setTimeout(() => (this.layoutStatus = ""), 2000);
    },

    async resetLayout() {
      await this.fetchJSON("/api/layout/reset", { method: "POST" });
      await this.initLayoutGrid();
    },

    // ---- oauth ----
    async loadOAuth() {
      const creds = await this.fetchJSON("/api/oauth/google/credentials");
      this.google.client_id = creds.client_id || "";
      this.google.client_secret_set = creds.client_secret_set;
      const data = await this.fetchJSON("/api/oauth/providers");
      this.oauthProviders = data.providers;
    },

    async saveGoogleCreds() {
      await this.fetchJSON("/api/oauth/google/credentials", {
        method: "PUT",
        body: JSON.stringify({
          client_id: this.google.client_id,
          client_secret: this.google.client_secret,
        }),
      });
      await this.loadOAuth();
    },

    async disconnect(provider) {
      await this.fetchJSON(`/api/oauth/${provider}`, { method: "DELETE" });
      await this.loadOAuth();
    },

    // ---- system ----
    async loadSystem() {
      this.system = await this.fetchJSON("/api/system/info");
      this.schedule = await this.fetchJSON("/api/system/display-schedule");
    },

    async checkUpdate() {
      this.updateInfo = await this.fetchJSON("/api/system/update/check");
    },

    async installUpdate() {
      if (!confirm("Install update? Service will restart.")) return;
      await this.fetchJSON("/api/system/update/install", { method: "POST" });
    },

    async saveSchedule() {
      await this.fetchJSON("/api/system/display-schedule", {
        method: "PUT",
        body: JSON.stringify(this.schedule),
      });
    },

    async restart() {
      if (!confirm("Restart service?")) return;
      await this.fetchJSON("/api/system/restart", { method: "POST" });
    },
  };
}

window.adminApp = adminApp;
