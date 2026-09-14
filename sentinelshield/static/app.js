/**
 * SentinelShield Command Desk — Entrypoint & Modular Coordinator
 * 
 * All feature modules are cleanly decoupled under /static/js/modules/
 * and state is managed reactively via /static/js/state.js.
 */
(function () {
  const scripts = [
    "/static/js/state.js",
    "/static/js/api.js",
    "/static/js/modules/auth.js",
    "/static/js/modules/registry.js",
    "/static/js/modules/live_player.js",
    "/static/js/modules/anpr_scanner.js",
    "/static/js/modules/vehicle_find.js",
    "/static/js/modules/map_twin.js",
    "/static/js/modules/alerts_threats.js",
    "/static/js/modules/watchlist.js",
    "/static/js/modules/evidence_vault.js",
    "/static/js/modules/cyber_tools.js",
    "/static/js/modules/assistant.js",
    "/static/js/modules/chat_drawer.js",
    "/static/js/main.js",
  ];

  // If running directly without script tags, load modules dynamically
  if (!window.SSApp && !window._ss_modules_loading) {
    window._ss_modules_loading = true;
    let idx = 0;
    function loadNext() {
      if (idx >= scripts.length) return;
      const src = scripts[idx++];
      const existing = document.querySelector(`script[src^="${src}"]`);
      if (existing) {
        loadNext();
        return;
      }
      const s = document.createElement("script");
      s.src = src + "?v=" + Date.now();
      s.onload = loadNext;
      document.head.appendChild(s);
    }
    loadNext();
  }
})();
