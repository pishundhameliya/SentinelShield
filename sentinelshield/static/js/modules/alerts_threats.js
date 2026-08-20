/**
 * Alerts and Threats module — incident table rendering, seen/done status updates, demo panic & abandoned object triggers
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSAlerts = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;

  function alertRow(a) {
    return `<tr>
      <td>${escapeHtml(a.created)}</td>
      <td><b>${escapeHtml(a.title)}</b><br/><span class="meta">${escapeHtml(a.detail || "")} · ${escapeHtml(a.kind)}</span></td>
      <td>${escapeHtml(a.camera_id)}</td>
      <td>${a.trust}</td>
      <td>
        <span class="badge ${a.severity === "CRITICAL" ? "b-bad" : "b-warn"}">${escapeHtml(a.severity)}</span>
        <div class="row">
          <button class="btn btn-d" onclick="SSAlerts.setAlert('${a.id}','seen')">Seen</button>
          <button class="btn btn-g" onclick="SSAlerts.setAlert('${a.id}','done')">Done</button>
        </div>
        <div class="meta">${escapeHtml(a.status)}</div>
      </td></tr>`;
  }

  function renderAlerts() {
    const data = SSState.get("data") || {};
    const allA = data.alerts || [];
    const threats = allA.filter((a) => a.kind === "threat" || a.kind === "watchlist");

    if ($("threat-rows")) $("threat-rows").innerHTML = threats.map(alertRow).join("") || "<tr><td colspan='5'>No threats yet.</td></tr>";
    if ($("alert-rows")) $("alert-rows").innerHTML = allA.map(alertRow).join("") || "<tr><td colspan='5'>No alerts.</td></tr>";
  }

  async function setAlert(id, status) {
    await SSApi.setAlertStatus(id, status);
    SSApp.refresh();
  }

  async function triggerPanic() {
    await fetch("/api/demo/panic", { method: "POST" });
    SSApp.refresh();
    SSApp.tab("alerts", document.querySelector('[data-tab="alerts"]'));
  }

  async function triggerAbandoned() {
    await fetch("/api/demo/abandoned", { method: "POST" });
    SSApp.refresh();
    SSApp.tab("alerts", document.querySelector('[data-tab="alerts"]'));
  }

  return {
    alertRow,
    renderAlerts,
    setAlert,
    triggerPanic,
    triggerAbandoned,
  };
});
