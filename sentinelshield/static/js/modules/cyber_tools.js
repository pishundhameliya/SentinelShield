/**
 * Cyber Tools module — honeypot testing and incident audit table
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSCyber = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;

  async function loadCyber() {
    const j = await SSApi.getCyber();
    const html = (j.cyber || []).map((e) =>
      "<tr><td>" + escapeHtml(e.created || "") + "</td><td>" + escapeHtml(e.kind) +
      "</td><td>" + escapeHtml(e.detail || "") + "</td></tr>"
    ).join("") || "<tr><td colspan='3'>No cyber hits yet. Press the red button to test.</td></tr>";
    if ($("tools-cyber-rows")) $("tools-cyber-rows").innerHTML = html;
  }

  async function loadEvents() {
    const j = await SSApi.getEvents();
    const rows = (j.events || []).slice(0, 20);
    const html = rows.map((e) => {
      let what = e.title || e.kind;
      if (e.kind === "vehicle") what = "Vehicle number seen: " + (e.extra || e.title);
      if (e.kind === "tamper") what = "Camera picture frozen / black";
      if (e.kind === "crowd" || e.kind === "panic") what = "Crowd / people running";
      return "<tr><td>" + escapeHtml(e.created || "") + "</td><td><b>" + escapeHtml(what) +
        "</b></td><td>" + escapeHtml(e.place || e.camera_id || "") + "</td></tr>";
    }).join("") || "<tr><td colspan='3'>Waiting for AI… keep this page open 15 seconds.</td></tr>";

    if ($("tools-ev-rows")) $("tools-ev-rows").innerHTML = html;
    if ($("ev-rows")) $("ev-rows").innerHTML = html;

    const data = SSState.get("data") || {};
    if ($("tools-stats")) {
      $("tools-stats").innerHTML =
        '<div class="stat"><b>' + rows.length + "</b> latest finds</div>" +
        '<div class="stat"><b>' + ((data.ai && data.ai.cycles) || 0) + "</b> AI checks done</div>" +
        '<div class="stat"><b>' + ((data.alerts || []).filter((a) => a.status === "new").length) + "</b> new alerts</div>";
    }
  }

  async function fillTools() {
    await loadEvents();
    await loadCyber();
    if (window.SSEvidence) await SSEvidence.loadVault();
  }

  async function triggerHoneypotTest() {
    await SSApi.triggerHoneypot();
    await fillTools();
    SSApp.refresh();
  }

  return {
    loadCyber,
    loadEvents,
    fillTools,
    triggerHoneypotTest,
  };
});
