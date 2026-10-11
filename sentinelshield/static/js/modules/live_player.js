/**
 * Live Player module — streaming controls, MJPEG playback, pause/play freeze frame
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSLivePlayer = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);

  async function renderLive() {
    const crumb = $("live-crumb");
    const grid = $("live-grid");
    const bind = $("live-bind");
    if (!crumb || !grid) return;

    const j = await SSApi.getLiveCams();
    const liveCams = j.cameras || [];
    SSState.set("liveCams", liveCams);

    const city = SSState.get("city");
    const area = SSState.get("area");
    const areas = SSState.get("areas") || [];
    const data = SSState.get("data") || {};

    let html = `<button type="button" onclick="SSLivePlayer.liveBack(0)">All Cameras / Gujarat</button>`;
    if (city) {
      const c = (data.cities || []).find((x) => x.id === city);
      html += ` → <button type="button" onclick="SSLivePlayer.liveBack(1)">${c ? c.name : city}</button>`;
    }
    if (area) {
      const a = areas.find((x) => x.id.endsWith(":" + area) || x.id === area);
      html += ` → <span>${a ? a.name : area}</span>`;
    }
    crumb.innerHTML = html;

    if (liveCams.length) {
      grid.innerHTML = liveCams.map(liveCard).join("");
      applyLiveFilter();
    } else {
      grid.innerHTML = "<p class='meta' style='padding:16px'>No Sentinel Gujarat live cameras found.</p>";
    }
    if ($("live-cam-count")) $("live-cam-count").textContent = liveCams.length;
    if (bind) bind.innerHTML = liveCams.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");

    const anprSel = $("anpr-cam-select");
    const currentId = SSState.get("currentLiveCamId");
    if (anprSel && liveCams.length) {
      anprSel.innerHTML = liveCams.map((c) => `<option value="${c.id}" ${c.id === currentId ? "selected" : ""}>${c.name}</option>`).join("");
    }
  }

  let osdTimer = null;

  // Monitor chrome: "off" | "live" | "paused"
  function setViewer(mode, name) {
    const v = $("live-viewer");
    if (!v) return;
    v.classList.toggle("is-live", mode !== "off");
    v.classList.toggle("is-paused", mode === "paused");
    if (name !== undefined && $("live-osd-name")) $("live-osd-name").textContent = name;
    clearInterval(osdTimer);
    if (mode === "live") {
      const tick = () => {
        if ($("live-osd-clock")) $("live-osd-clock").textContent = new Date().toLocaleString("en-IN", { hour12: false });
      };
      tick();
      osdTimer = setInterval(tick, 1000);
    }
  }

  function highlightPlaying() {
    const id = SSState.get("playingCamId") || "";
    document.querySelectorAll("#live-grid .cam").forEach((el) => {
      el.classList.toggle("is-playing", el.getAttribute("data-cam") === id);
    });
  }

  function liveCard(c) {
    const urlArg = (c.live_url || "").replace(/'/g, "\\'");
    const playing = c.id === SSState.get("playingCamId") ? " is-playing" : "";
    const num = c.custom ? "URL" : (String(c.name || "").match(/(\d+)\s*$/) || [, "•"])[1];
    const tag = c.custom ? '<span class="badge b-warn">CUSTOM FEED</span>' : SSRegistry.badge(c);
    return `<article class="cam live-item${playing}" data-cam="${c.id}" tabindex="0" role="button"
      title="Open live: ${c.name}"
      onclick="SSLivePlayer.startLive('${c.id}', '${urlArg}')"
      onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}">
      <span class="live-thumb"><small>CAM</small>${num}</span>
      <span class="live-info">
        <b>${c.name}</b>
        <span class="meta">${c.owner || ""}</span>
        <span>${tag}</span>
      </span>
      <span class="live-go"><span class="go-open">Open live</span><span class="go-on">● On air</span></span>
    </article>`;
  }

  function applyLiveFilter() {
    const q = (($("live-filter") && $("live-filter").value) || "").trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll("#live-grid .cam").forEach((el) => {
      el.hidden = !!q && !el.textContent.toLowerCase().includes(q);
      if (!el.hidden) shown++;
    });
    const grid = $("live-grid");
    let empty = $("live-filter-empty");
    if (grid && !empty) {
      empty = document.createElement("p");
      empty.id = "live-filter-empty";
      empty.className = "meta";
      empty.style.padding = "12px 4px";
      grid.appendChild(empty);
    }
    if (empty) {
      empty.hidden = shown > 0 || !q;
      empty.textContent = "No camera matches “" + q + "”.";
    }
  }

  function liveBack(n) {
    if (n === 0) {
      SSState.set("city", "");
      SSState.set("area", "");
      SSState.set("areas", []);
      SSState.set("cams", []);
    }
    if (n === 1) {
      SSState.set("area", "");
      SSState.set("cams", []);
    }
    renderLive();
  }

  async function startLive(id, passedUrl) {
    const camId = id || ($("live-bind") && $("live-bind").value);
    if (!camId) {
      alert("First pick city then area, then a camera.");
      return;
    }

    SSState.set("currentLiveCamId", camId);
    const sel = $("anpr-cam-select");
    if (sel) sel.value = camId;
    if (window.SSAnpr) SSAnpr.onAnprCamChanged(camId);

    const liveCams = SSState.get("liveCams") || [];
    const cam = liveCams.find((c) => c.id === camId);
    let liveUrl = passedUrl || (cam && (cam.live_url || cam.source)) || "";

    const img = $("live-img");
    const iframe = $("live-frame");
    const video = $("live-video");
    const link = $("live-link");

    if (img) { img.removeAttribute("src"); img.style.display = "none"; }
    if (iframe) { iframe.removeAttribute("src"); iframe.style.display = "none"; }
    if (video) { video.removeAttribute("src"); video.style.display = "none"; }
    if (link) { link.style.display = "none"; }
    if (window._liveCanvas) { window._liveCanvas.style.display = "none"; }

    const camName = cam ? cam.name : camId;
    SSState.set("playingCamId", camId);
    highlightPlaying();
    if ($("live-now")) $("live-now").textContent = "Connecting to " + camName + "…";
    const viewer = $("live-viewer");
    if (viewer) viewer.scrollIntoView({ behavior: "smooth", block: "nearest" });

    if (liveUrl.startsWith("http://") || liveUrl.startsWith("https://")) {
      setViewer("live", camName);
      if ($("live-now")) $("live-now").textContent = "Playing " + (cam ? cam.name : camId);
      if (link) {
        link.href = liveUrl;
        link.style.display = "inline-block";
      }
      if (iframe) {
        iframe.src = liveUrl;
        iframe.style.display = "block";
      }
      return;
    }

    const j = await SSApi.startLive(camId, "auto");
    if (j.error) {
      SSState.set("playingCamId", "");
      highlightPlaying();
      setViewer("off");
      if ($("live-now")) $("live-now").textContent = "Could not open " + camName + ".";
      alert(j.error || "Cannot start live");
      return;
    }

    const data = SSState.get("data");
    if (data && data.ai && !data.ai.on) {
      await SSApi.toggleAi(true);
      data.ai.on = true;
    }

    setViewer("live", camName);
    if ($("live-now")) $("live-now").textContent = "Playing " + (cam ? cam.name : camId);
    if (img) {
      img.style.display = "block";
      img.src = "/api/live/stream?t=" + Date.now();
    }
    if (window.SSAnpr) SSAnpr.refreshLiveVehicles();
  }

  async function stopLive() {
    await SSApi.stopLive();
    if ($("live-img")) { $("live-img").removeAttribute("src"); $("live-img").style.display = "none"; }
    if ($("live-frame")) { $("live-frame").removeAttribute("src"); $("live-frame").style.display = "none"; }
    if ($("live-video")) { $("live-video").removeAttribute("src"); $("live-video").style.display = "none"; }
    if ($("live-link")) { $("live-link").style.display = "none"; }
    if (window._liveCanvas) { window._liveCanvas.style.display = "none"; }
    if ($("live-now")) $("live-now").textContent = "Live stopped.";
    SSState.set("playingCamId", "");
    highlightPlaying();
    setViewer("off");
  }

  function pauseLiveStream() {
    const img = $("live-img");
    const video = $("live-video");
    if (img && img.style.display !== "none") {
      if (!window._liveCanvas) {
        window._liveCanvas = document.createElement("canvas");
        window._liveCanvas.style.marginTop = "10px";
        window._liveCanvas.style.width = "100%";
        window._liveCanvas.style.maxWidth = "720px";
        window._liveCanvas.style.borderRadius = "10px";
        window._liveCanvas.style.border = "1px solid var(--line)";
        img.parentNode.insertBefore(window._liveCanvas, img.nextSibling);
      }
      const canvas = window._liveCanvas;
      canvas.width = img.naturalWidth || 640;
      canvas.height = img.naturalHeight || 360;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      img.style.display = "none";
      canvas.style.display = "block";
      window._pausedLiveUrl = img.src;
      img.removeAttribute("src");
      if ($("live-now")) $("live-now").textContent = "Live paused.";
      setViewer("paused");
    } else if (video && video.style.display !== "none") {
      video.pause();
      if ($("live-now")) $("live-now").textContent = "Live paused.";
      setViewer("paused");
    }
  }

  function playLiveStream() {
    const img = $("live-img");
    const video = $("live-video");
    if (window._liveCanvas && window._liveCanvas.style.display !== "none") {
      window._liveCanvas.style.display = "none";
      img.style.display = "block";
      if (window._pausedLiveUrl) {
        img.src = "/api/live/stream?t=" + Date.now();
      }
      if ($("live-now")) $("live-now").textContent = "Playing stream...";
      setViewer("live");
    } else if (video && video.style.display !== "none") {
      video.play();
      if ($("live-now")) $("live-now").textContent = "Playing stream...";
      setViewer("live");
    }
  }

  async function addShopCam() {
    const name = ($("shop-name") && $("shop-name").value.trim()) || "Live Camera Feed";
    const url = ($("shop-url") && $("shop-url").value.trim()) || "";
    if (!url) {
      alert("Paste your live camera link (e.g. https://live.sentinelgujarat.in/camera/26).");
      return;
    }
    // Operator-connected feeds live under Gujarat → New cameras, next to the built-in Sentinel feeds
    const j = await SSApi.addCamera({
      name,
      live_url: url,
      city_id: "gujarat",
      area_id: "new-cameras",
      owner: "Live Sentinel Gujarat Feed",
      place: "Gujarat",
    });
    if (!j || !j.ok) {
      alert((j && j.error) || "Could not save the camera.");
      return;
    }

    if ($("shop-name")) $("shop-name").value = "";
    if ($("shop-url")) $("shop-url").value = "";
    if ($("live-filter")) $("live-filter").value = "";
    await renderLive();
    alert("Camera added. It is now at the top of the Live cameras list — click it to open the feed.");
  }

  return {
    renderLive,
    liveCard,
    applyLiveFilter,
    liveBack,
    startLive,
    stopLive,
    pauseLiveStream,
    playLiveStream,
    addShopCam,
  };
});
