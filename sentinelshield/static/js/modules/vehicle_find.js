/**
 * Vehicle Find module — search plate, sighting history, and Leaflet route trail
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSVehicleFind = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;
  let findMap = null;
  let findMarks = [];

  async function searchPlate() {
    try {
      const a = $("qplate") ? $("qplate").value : "";
      const b = $("qplate2") ? $("qplate2").value : "";
      const p = (a || b || "").trim();
      if (!p) {
        alert("Type a vehicle number, e.g. GJ05SS2026");
        return;
      }
      if ($("qplate")) $("qplate").value = p;
      if ($("qplate2")) $("qplate2").value = p;
      SSApp.tab("find", document.querySelector('[data-tab="find"]'));

      const j = await SSApi.findVehicle(p);
      window._lastFind = j;

      if ($("find-msg")) $("find-msg").textContent = j.message || j.error || "";
      if (j.last && $("find-last")) {
        $("find-last").innerHTML = '<div class="box" style="margin-top:10px"><h3>Last seen: ' +
          escapeHtml(j.plate) + "</h3><p><b>" + escapeHtml(j.last.camera_name || "") +
          "</b> · " + escapeHtml(j.last.place || "") + " · " + escapeHtml(j.last.created || "") +
          "</p>" + (j.watchlist ? '<span class="badge b-bad">' + escapeHtml(j.watchlist.kind) +
          " — " + escapeHtml(j.watchlist.note || "") + "</span>" : "") + "</div>";
      } else if ($("find-last")) {
        $("find-last").innerHTML = "";
      }

      if ($("find-rows")) {
        $("find-rows").innerHTML = (j.history || []).map(function (h) {
          return "<tr><td>" + escapeHtml(h.created) + "</td><td>" + escapeHtml(h.camera_name) +
            "</td><td>" + escapeHtml(h.place || "") + "</td><td>" + escapeHtml(h.city_id || "") + "</td></tr>";
        }).join("") || "<tr><td colspan='4'>No history yet.</td></tr>";
      }
      setTimeout(function () { drawFindMap(j); }, 100);
    } catch (err) {
      alert("Find failed: " + err);
    }
  }

  function drawFindMap(j) {
    if (!window.L || !$("find-map")) return;
    const last = j && j.last;
    const center = last && last.lat ? [last.lat, last.lng] : [21.17, 72.83];
    if (!findMap) {
      findMap = L.map("find-map").setView(center, 12);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(findMap);
    } else {
      findMap.setView(center, 13);
    }
    findMarks.forEach(function (m) { findMap.removeLayer(m); });
    findMarks = [];
    (j.history || []).forEach(function (h, i) {
      if (h.lat == null) return;
      const m = L.circleMarker([h.lat, h.lng], { radius: i === 0 ? 11 : 7, color: i === 0 ? "#e11d48" : "#38bdf8" }).addTo(findMap);
      m.bindPopup((i === 0 ? "LAST · " : "") + h.camera_name + "<br/>" + h.created);
      findMarks.push(m);
    });
    setTimeout(function () { findMap.invalidateSize(); }, 250);
  }

  return {
    searchPlate,
    drawFindMap,
  };
});
