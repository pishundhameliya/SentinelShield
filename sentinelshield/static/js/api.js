/**
 * SentinelShield Unified REST API Fetch Client
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSApi = factory();
})(typeof self !== "undefined" ? self : this, function () {
  async function postForm(url, data) {
    const fd = new FormData();
    Object.entries(data || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null) fd.append(k, v);
    });
    const r = await fetch(url, { method: "POST", body: fd });
    return await r.json();
  }

  async function getJson(url) {
    const r = await fetch(url);
    return await r.json();
  }

  return {
    login: (username, password) => postForm("/api/login", { username, password }),
    getMe: (token) => getJson(`/api/me?token=${encodeURIComponent(token || "")}`),
    getOverview: () => getJson("/api/overview"),
    getCities: () => getJson("/api/cities"),
    getAreas: (city) => getJson(`/api/areas?city=${encodeURIComponent(city || "")}`),
    getCameras: (city, area, owner = "government") =>
      getJson(`/api/cameras?owner=${encodeURIComponent(owner)}&city=${encodeURIComponent(city || "")}&area=${encodeURIComponent(area || "")}`),
    getHotCams: () => getJson("/api/hot-cams"),
    getLiveCams: () => getJson("/api/live-cameras"),
    addCamera: (payload) => postForm("/api/cameras", payload),
    connectCameraUrl: (id, live_url) => postForm(`/api/cameras/${id}/connect`, { live_url }),
    startLive: (camera_id, source = "auto") => postForm("/api/live/start", { camera_id, source }),
    stopLive: () => postForm("/api/live/stop", {}),
    scanLiveAnpr: (camera_id) => postForm(`/api/anpr/scan-live/${camera_id}`, {}),
    analyzeCamera: (camera_id) => postForm(`/api/analyze/${camera_id}`, {}),
    getJob: (job_id) => getJson(`/api/job/${job_id}`),
    findVehicle: (plate) => getJson(`/api/vehicle?plate=${encodeURIComponent(plate || "")}`),
    getVehicleDetections: (camera_id = "", q = "") =>
      getJson(`/api/vehicle-detections?camera_id=${encodeURIComponent(camera_id)}&q=${encodeURIComponent(q)}`),
    getRoute: (plate) => getJson(`/api/route?plate=${encodeURIComponent(plate || "")}`),
    addWatchlist: (plate, kind, note, priority) => postForm("/api/watchlist", { plate, kind, note, priority }),
    deleteWatchlist: (id) => fetch(`/api/watchlist/${id}`, { method: "DELETE" }).then((r) => r.json()),
    setAlertStatus: (id, status) => postForm(`/api/alerts/${id}/status`, { status }),
    getEvidence: () => getJson("/api/evidence"),
    sealEvidence: (camera_id) => postForm(`/api/evidence/${camera_id}`, {}),
    rankEvidence: () => getJson("/api/rank-evidence"),
    getHeat: () => getJson("/api/heat"),
    getTwin: () => getJson("/api/twin"),
    getEvents: (q = "") => getJson(`/api/events?q=${encodeURIComponent(q)}`),
    getCyber: () => getJson("/api/cyber"),
    triggerHoneypot: () => getJson("/honeypot"),
    ask: (q) => postForm("/api/ask", { q }),
    launchDrone: (city = "surat", reason = "CCTV alert") => postForm("/api/drones/launch", { city, reason }),
    getChat: (room = "team") => getJson(`/api/chat?room=${encodeURIComponent(room)}`),
    postChat: (text, token, room = "team") => postForm("/api/chat", { text, token, room }),
    toggleAi: (active) => postForm(active ? "/api/ai/on" : "/api/ai/off", {}),
  };
});
