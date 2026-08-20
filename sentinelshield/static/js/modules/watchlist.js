/**
 * Watchlist module — plate add, delete, and table rendering
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSWatchlist = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;

  function renderWatchlist() {
    const data = SSState.get("data") || {};
    const watch = data.watchlist || [];
    if ($("wl-rows")) {
      $("wl-rows").innerHTML = watch.map((w) => `<tr>
        <td><b>${escapeHtml(w.plate)}</b></td><td>${escapeHtml(w.kind)}</td><td>${escapeHtml(w.note || "")}</td>
        <td><button class="btn btn-r" onclick="SSWatchlist.delWl('${w.id}')">Remove</button></td></tr>`).join("");
    }
  }

  async function addWl() {
    const plate = $("wl-plate")?.value || "";
    const kind = $("wl-kind")?.value || "stolen";
    const note = $("wl-note")?.value || "";
    if (!plate) {
      alert("Enter a vehicle number.");
      return;
    }
    await SSApi.addWatchlist(plate, kind, note, "HIGH");
    if ($("wl-plate")) $("wl-plate").value = "";
    if ($("wl-note")) $("wl-note").value = "";
    SSApp.refresh();
  }

  async function delWl(id) {
    await SSApi.deleteWatchlist(id);
    SSApp.refresh();
  }

  return {
    renderWatchlist,
    addWl,
    delWl,
  };
});
