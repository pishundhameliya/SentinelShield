/**
 * SentinelShield Application Bootstrap and Event Coordinator
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSApp = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);

  async function refresh() {
    try {
      const data = await SSApi.getOverview();
      SSState.set("data", data);
      const city = SSState.get("city");
      const area = SSState.get("area");
      if (city && area) {
        await SSRegistry.loadCams(false);
      } else if (city) {
        await SSRegistry.loadAreas();
      }
      render();
    } catch (e) {}
  }

  function render() {
    SSRegistry.renderHome();
    SSAlerts.renderAlerts();
    SSWatchlist.renderWatchlist();
    SSLivePlayer.renderLive();
    SSChat.renderChatMessages();

    const data = SSState.get("data") || {};
    if ($("ai-status") && data.ai) {
      $("ai-status").textContent = data.ai.on
        ? ("AI ON · last " + (data.ai.last_cam || "—") + " · cycle " + (data.ai.cycles || 0))
        : "AI paused";
    }

    if ($("person-rows")) {
      $("person-rows").innerHTML = (data.persons || []).map((p) =>
        `<tr><td>${SSState.escapeHtml(p.name)}</td><td>${SSState.escapeHtml(p.kind)}</td><td>${SSState.escapeHtml(p.note || "")}</td></tr>`
      ).join("");
    }
  }

  function tab(name, btn) {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("on"));
    if (btn) btn.classList.add("on");
    document.querySelectorAll(".page > section").forEach((el) => {
      el.classList.toggle("hidden", el.id !== "p-" + name);
    });

    const city = SSState.get("city");
    const area = SSState.get("area");

    if (name === "map" || name === "twin") setTimeout(() => SSTwinMap.drawTwin(), 50);
    if (name === "find") setTimeout(() => { if (window._lastFind) SSVehicleFind.drawFindMap(window._lastFind); }, 50);
    if (name === "cams" && city && area) SSRegistry.loadCams();
    if (name === "home" && city && area) SSRegistry.loadCams();
    if (name === "live") SSLivePlayer.renderLive();
    if (name === "tools") SSCyber.fillTools();
    if (name === "webcam" && window.WebcamTest) window.WebcamTest.onShow();
  }

  function showApp() {
    $("login")?.classList.add("hidden");
    $("app")?.classList.remove("hidden");
    const user = SSState.get("user");
    if ($("who")) $("who").textContent = user ? (user.name + " · " + user.role) : "";
    refresh();
    SSChat.openWs();
    setInterval(refresh, 5000);
  }

  async function analyze(id) {
    await SSApi.analyzeCamera(id);
    refresh();
  }

  async function analyzeAll() {
    const cams = SSState.get("cams") || [];
    for (const c of cams.filter((x) => x.kind === "recorded")) {
      await SSApi.analyzeCamera(c.id);
    }
  }

  async function upload(id, input) {
    if (!input.files || !input.files[0]) return;
    const fd = new FormData();
    fd.append("camera_id", id);
    fd.append("file", input.files[0]);
    await fetch("/api/upload", { method: "POST", body: fd });
    input.value = "";
    SSRegistry.loadCams();
  }

  async function toggleAi() {
    const data = SSState.get("data") || {};
    const on = data.ai && data.ai.on;
    await SSApi.toggleAi(!on);
    refresh();
  }

  function setupEventDelegation() {
    document.addEventListener("click", function (e) {
      const t = e.target;
      const id = t && t.id;
      if (t && t.getAttribute && t.getAttribute("data-ask")) {
        if ($("askq")) $("askq").value = t.getAttribute("data-ask");
        SSAssistant.askBot();
        return;
      }
      if (id === "btn-find" || id === "btn-find2") SSVehicleFind.searchPlate();
      if (id === "btn-ai") toggleAi();
      if (id === "btn-evq") SSCyber.loadEvents();
      if (id === "btn-evd") SSEvidence.sealEvidence();
      if (id === "btn-heat") { tab("map", document.querySelector('[data-tab="map"]')); setTimeout(() => SSTwinMap.drawTwin("heat"), 80); }
      if (id === "btn-cybermap") { tab("map", document.querySelector('[data-tab="map"]')); setTimeout(() => SSTwinMap.drawTwin("cyber"), 80); }
      if (id === "btn-route") { if ($("qplate")) $("qplate").value = "GJ05SS2026"; SSVehicleFind.searchPlate(); }
      if (id === "btn-drone") SSTwinMap.launchDrone();
      if (id === "btn-panic") SSAlerts.triggerPanic();
      if (id === "btn-bag") SSAlerts.triggerAbandoned();
      if (id === "btn-hp") SSCyber.triggerHoneypotTest();
      if (id === "btn-ask") SSAssistant.askBot();
      if (id === "btn-voice") SSAssistant.startVoice();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.target.id === "qplate" || e.target.id === "qplate2")) {
        e.preventDefault();
        SSVehicleFind.searchPlate();
      }
    });
  }

  function boot() {
    setupEventDelegation();
    const token = SSState.get("token");
    if (!SSState.get("token")) {
      // Auto-bypass login screen for final submission
      $("login")?.classList.add("hidden");
      if ($("user")) $("user").value = "operator";
      if ($("pass")) $("pass").value = "operator";
      SSAuth.doLogin(() => showApp());
      return;
    }
    SSAuth.checkSession(() => showApp());
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  // Expose backwards-compatible window methods for inline handlers in index.html
  window.doLogin = () => SSAuth.doLogin(() => showApp());
  window.logout = SSAuth.logout;
  window.tab = tab;
  window.toggleChat = SSChat.toggleChat;
  window.sendChat = SSChat.sendChat;
  window.pickCity = SSRegistry.pickCity;
  window.pickArea = SSRegistry.pickArea;
  window.backLevel = SSRegistry.backLevel;
  window.addCam = SSRegistry.addCam;
  window.analyze = analyze;
  window.analyzeAll = analyzeAll;
  window.upload = upload;
  window.addWl = SSWatchlist.addWl;
  window.delWl = SSWatchlist.delWl;
  window.setAlert = SSAlerts.setAlert;
  window.renderLive = SSLivePlayer.renderLive;
  window.startLive = SSLivePlayer.startLive;
  window.stopLive = SSLivePlayer.stopLive;
  window.pauseLiveStream = SSLivePlayer.pauseLiveStream;
  window.playLiveStream = SSLivePlayer.playLiveStream;
  window.addShopCam = SSLivePlayer.addShopCam;
  window.liveBack = SSLivePlayer.liveBack;
  window.onAnprCamChanged = SSAnpr.onAnprCamChanged;
  window.runLiveAnprScan = SSAnpr.runLiveAnprScan;
  window.searchPlate = SSVehicleFind.searchPlate;
  window.sealEvidence = SSEvidence.sealEvidence;
  window.fillTools = SSCyber.fillTools;
  window.drawTwin = SSTwinMap.drawTwin;
  window.launchDrone = SSTwinMap.launchDrone;
  window.askBot = SSAssistant.askBot;
  window.startVoice = SSAssistant.startVoice;

  return {
    refresh,
    render,
    tab,
    showApp,
    analyze,
    analyzeAll,
    upload,
    toggleAi,
  };
});
