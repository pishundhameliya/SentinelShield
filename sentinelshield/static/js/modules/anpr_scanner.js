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
          <div style="background:#0f172a;border:1px solid var(--accent);border-radius:12px;padding:14px;min-width:280px;max-width:330px;flex:0 0 auto;box-shadow:0 4px 12px rgba(0,0,0,0.5)">
            <div style="font-size:11px;color:#38bdf8;font-weight:bold;margin-bottom:6px;background:#1e293b;padding:4px 8px;border-radius:4px">
              📹 FEED: ${j.camera_name}
            </div>
            <div style="font-size:18px;letter-spacing:1.5px;font-weight:900;color:#facc15;background:#000;padding:8px 12px;border:2px solid #facc15;border-radius:8px;text-align:center;margin-bottom:8px">
              🚘 ${p.plate_text}
            </div>
            <div style="font-size:12px;color:#e2e8f0;margin-bottom:6px">
              ⏱ Photo Clicked: <b style="color:#38bdf8">${p.captured_at}</b>
            </div>
            <div style="font-size:12px;color:#94a3b8;margin-bottom:8px">
              Vehicle: <b>${(p.vehicle && p.vehicle.cls ? p.vehicle.cls.toUpperCase() : 'VEHICLE')}</b> · Conf: <b>${((p.ocr_confidence || (p.vehicle ? p.vehicle.confidence : 0)) * 100).toFixed(0)}%</b>
            </div>
            ${p.deblurred_crop_b64 ? `
              <div style="margin:8px 0;text-align:center;background:#000;padding:6px;border-radius:6px">
                <img src="${p.deblurred_crop_b64}" alt="Deblurred License Plate" style="max-width:100%;height:80px;border-radius:4px;border:1px solid #38bdf8;object-fit:contain" />
              </div>
              <div style="font-size:11px;color:#94a3b8">Deblurring Quality: <b style="color:#38bdf8">${p.sharpness_score}</b></div>
              <div style="font-size:11px;color:#4ade80;margin-top:2px">✓ CLAHE + Unsharp Mask Applied</div>
            ` : `<div style="font-size:11px;color:#38bdf8;margin:6px 0">✓ Fast-ALPR Neural Read</div>`}
            <a href="${p.snapshot_url}" target="_blank" class="btn btn-p" style="display:block;text-decoration:none;text-align:center;margin-top:10px;font-weight:bold;font-size:13px;padding:8px">
              📷 Open Full Photo with Timestamp 🔗
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
