/**
 * Digital Twin map module — risk heatmaps, cyber attack pins, route drawing, and drone simulation
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSTwinMap = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  let twinMap = null;
  let twinLayer = [];

  async function drawTwin(mode) {
    if (!window.L || !$("twin-map")) return;
    const heat = await SSApi.getHeat();
    const twin = await SSApi.getTwin();

    if (!twinMap) {
      twinMap = L.map("twin-map").setView([22.5, 71.8], 7);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(twinMap);
    }

    twinLayer.forEach((m) => twinMap.removeLayer(m));
    twinLayer = [];

    const showHeat = !mode || mode === "heat" || mode === "route";
    const showCyber = !mode || mode === "cyber";

    if (showHeat) {
      (heat.spots || []).forEach((s) => {
        const r = s.level === "high" ? 28 : (s.level === "medium" ? 18 : 10);
        const col = s.level === "high" ? "#e11d48" : (s.level === "medium" ? "#f59e0b" : "#22c55e");
        const m = L.circleMarker([s.lat, s.lng], { radius: r, color: col, fillOpacity: 0.35 }).addTo(twinMap);
        m.bindPopup("<b>" + s.name + "</b><br/>Past incidents: " + s.past + "<br/>Predicted risk: " + s.predicted + " (" + s.level + ")");
        twinLayer.push(m);
      });
    }

    (twin.cameras || []).forEach((c) => {
      if (c.lat == null) return;
      const m = L.circleMarker([c.lat, c.lng], { radius: 6, color: "#38bdf8" }).addTo(twinMap);
      m.bindPopup(c.name + "<br/>" + (c.place || ""));
      twinLayer.push(m);
    });

    if (showCyber) {
      (twin.cyber || []).forEach((cy) => {
        const cam = (twin.cameras || []).find((c) => c.id === cy.camera_id) || { lat: 23.02, lng: 72.57 };
        if (cam.lat == null) return;
        const m = L.circleMarker([cam.lat, cam.lng], { radius: 10, color: "#fb923c" }).addTo(twinMap);
        m.bindPopup("CYBER · " + cy.kind + "<br/>" + cy.detail);
        twinLayer.push(m);
      });
    }

    if (mode === "route") {
      const rt = await SSApi.getRoute("GJ05SS2026");
      const latlngs = (rt.points || []).filter((p) => p.lat != null).map((p) => [p.lat, p.lng]);
      if (latlngs.length) {
        const line = L.polyline(latlngs, { color: "#e11d48" }).addTo(twinMap);
        twinLayer.push(line);
        twinMap.fitBounds(line.getBounds(), { padding: [30, 30] });
        if ($("twin-note")) $("twin-note").textContent = "Route hops " + rt.hops + " · direction " + rt.direction + " · est " + (rt.speed_kmh_est || "—") + " km/h";
      }
    } else if ($("twin-note")) {
      $("twin-note").textContent = "Red = predicted high risk · Orange = cyber · Blue = cameras. Heat is history + density, not a crystal ball.";
    }

    setTimeout(() => twinMap.invalidateSize(), 200);
  }

  async function launchDrone() {
    const city = SSState.get("city") || "surat";
    const j = await SSApi.launchDrone(city, "CCTV alert");
    alert(j.drone + " " + j.status + "\n" + j.feed);
    SSApp.tab("map", document.querySelector('[data-tab="map"]'));
  }

  return {
    drawTwin,
    launchDrone,
  };
});
