/**
 * ANPR Scanner module — live frame AI plate detection & deblur gallery
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSAnpr = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;

  function onAnprCamChanged(val) {
    if (!val) return;
    SSState.set("currentLiveCamId", val);
    const liveCams = SSState.get("liveCams") || [];
    const cam = liveCams.find((c) => c.id === val);
    const name = cam ? cam.name : val;
    if ($("anpr-selected-label")) {
      $("anpr-selected-label").innerHTML = `Active Camera Feed: <b style="color:var(--accent)">${name}</b>`;
    }
    if ($("btn-anpr-scan")) {
      $("btn-anpr-scan").textContent = `Run AI Scan on Selected Feed`;
    }
    refreshLiveVehicles();
  }

  async function refreshLiveVehicles() {
    const cameraId = SSState.get("currentLiveCamId");
    if (!cameraId) return;
    try {
      const j = await SSApi.getVehicleDetections(cameraId);
      if ($("live-vehicle-count")) $("live-vehicle-count").textContent = j.count || 0;
      if ($("live-vehicle-rows")) {
        $("live-vehicle-rows").innerHTML = (j.detections || []).map((d) =>
          `<tr><td>${escapeHtml(d.vehicle_type)}</td><td>${escapeHtml(d.tracking_id)}</td><td>${escapeHtml(d.plate)}</td><td>${(Number(d.confidence || 0) * 100).toFixed(0)}%</td><td>${escapeHtml(d.created)}</td></tr>`
        ).join("") || "<tr><td colspan='5'>No vehicles detected from this camera yet.</td></tr>";
      }
    } catch (e) {}
  }

  function renderVehicleRowsFromScan(result) {
    const rows = $("live-vehicle-rows");
    const count = $("live-vehicle-count");
    if (count) {
      count.textContent = String((result && result.vehicles ? result.vehicles.length : 0));
    }
    if (!rows) return;

    const plateMap = (result && result.plates_enhanced ? result.plates_enhanced : []).map((item, idx) => ({
      idx,
      plate: item.plate_text || "Plate Not Clear",
      confidence: Number(item.ocr_confidence || item.vehicle?.confidence || 0),
      cls: item.vehicle?.cls || "vehicle",
    }));

    rows.innerHTML = (result && result.vehicles ? result.vehicles : []).map((vehicle, idx) => {
      const match = plateMap[idx] || plateMap[0] || { plate: "Plate Not Clear", confidence: 0, cls: vehicle.cls || "vehicle" };
      const plateText = match.plate || "Plate Not Clear";
      const confidencePct = Math.max(0, Math.min(100, Number(match.confidence || vehicle.confidence || 0) * 100));
      return `
        <tr>
          <td>${escapeHtml(vehicle.cls || match.cls || "vehicle")}</td>
          <td>live-${idx + 1}</td>
          <td>${escapeHtml(plateText)}</td>
          <td>${confidencePct.toFixed(0)}%</td>
          <td>${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
        </tr>
      `;
    }).join("") || "<tr><td colspan='5'>No vehicles detected from this camera yet.</td></tr>";
  }

  async function runLiveAnprScan(overrideCamId) {
    const status = $("anpr-status");
    const results = $("anpr-results");
    const sel = $("anpr-cam-select");
    const camId = overrideCamId || (sel && sel.value) || SSState.get("currentLiveCamId") || "cam-26";

    const liveCams = SSState.get("liveCams") || [];
    const cam = liveCams.find((c) => c.id === camId);
    const camName = cam ? cam.name : camId;

    if (status) status.textContent = `Scanning live frame from [${camName}]...`;
    try {
      const j = await SSApi.scanLiveAnpr(camId);
      if (!j.ok) {
        if (status) status.textContent = "Scan error: " + (j.error || "Failed");
        return;
      }
      if (status) status.textContent = `Scanned [${j.camera_name}]! Found ${j.vehicles.length} vehicles, read ${j.plates_enhanced.length} license plates. Photo saved at ${j.timestamp}`;
      renderVehicleRowsFromScan(j);
      if (results) {
        results.innerHTML = (j.plates_enhanced || []).map((p) => `
          <div class="plate-card">
            <div class="feed">FEED: ${j.camera_name}</div>
            <div class="plate-num"><span class="ind">IND</span><span class="txt">${p.plate_text}</span></div>
            <div class="line">Photo clicked: <b>${p.captured_at}</b></div>
            <div class="line sub">
              Vehicle: <b>${(p.vehicle && p.vehicle.cls ? p.vehicle.cls.toUpperCase() : 'VEHICLE')}</b> · Conf: <b>${((p.ocr_confidence || (p.vehicle ? p.vehicle.confidence : 0)) * 100).toFixed(0)}%</b>
            </div>
            ${p.deblurred_crop_b64 ? `
              <div class="crop">
                <img src="${p.deblurred_crop_b64}" alt="Deblurred License Plate" />
              </div>
              <div class="line sub">Deblurring quality: <b>${p.sharpness_score}</b></div>
              <div class="ok">✓ CLAHE + Unsharp Mask Applied</div>
            ` : `<div class="ok">✓ Fast-ALPR Neural Read</div>`}
            <a href="${p.snapshot_url}" target="_blank" class="btn btn-p">
              Open full photo with timestamp ↗
            </a>
          </div>
        `).join("") || `<p class='meta'>No vehicle plate crops found in feed: <b>${j.camera_name}</b>.</p>`;
      }
    } catch (e) {
      if (status) status.textContent = "Network error while scanning frame.";
    }
  }

  return {
    onAnprCamChanged,
    refreshLiveVehicles,
    runLiveAnprScan,
  };
});
