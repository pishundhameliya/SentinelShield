/**
 * Registry module — cities, areas, camera cards, and breadcrumbs
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSRegistry = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const fmt = SSState.fmt;

  function badge(cam) {
    if (cam.status === "tampered") return '<span class="badge b-bad">TAMPER</span>';
    if (cam.status === "checking") return '<span class="badge b-warn">CHECKING</span>';
    if (cam.status === "live") return '<span class="badge b-info">LIVE</span>';
    if (cam.status === "checked") return '<span class="badge b-good">OK ' + cam.trust + "</span>";
    if (cam.live_url) return '<span class="badge b-info">LINK SAVED</span>';
    if (cam.kind === "registry") return '<span class="badge b-info">GOVT</span>';
    return '<span class="badge b-info">' + (cam.status || "ready") + "</span>";
  }

  function camCard(c) {
    const hasVid = c.source && c.kind === "recorded";
    return `<article class="cam">
      <h3>${c.name} ${badge(c)}</h3>
      <div class="meta">${c.owner || "Government"}<br/>${c.spot || c.place || ""}<br/>${c.last_note || ""}</div>
      <div class="row">
        ${hasVid
          ? `<button class="btn btn-g" onclick="SSApp.analyze('${c.id}')">Check video + threats</button>`
          : `<span class="meta">Upload a clip or add a live link in Live tab.</span>`}
        <label class="btn btn-s">Upload<input type="file" accept="video/*" hidden onchange="SSApp.upload('${c.id}', this)"/></label>
      </div>
    </article>`;
  }

  function renderHome() {
    const data = SSState.get("data") || {};
    const city = SSState.get("city");
    const area = SSState.get("area");
    const areas = SSState.get("areas") || [];
    const cams = SSState.get("cams") || [];

    if ($("estate-n")) $("estate-n").textContent = fmt(data.estate_total) + "+";
    const threats = (data.alerts || []).filter((a) => a.kind === "threat" || a.kind === "watchlist" || a.kind === "tamper");
    if ($("stats")) {
      $("stats").innerHTML = `
        <div class="stat"><b>${fmt(data.estate_total)}</b> Gujarat gov cameras</div>
        <div class="stat"><b>${(data.cities || []).length}</b> cities / groups</div>
        <div class="stat"><b>${threats.filter((a) => a.status === "new").length}</b> open threats</div>`;
    }

    let crumb = `<button onclick="SSRegistry.backLevel(0)">Gujarat</button>`;
    if (city) {
      const c = (data.cities || []).find((x) => x.id === city);
      crumb += ` → <button onclick="SSRegistry.backLevel(1)">${c ? c.name : city}</button>`;
    }
    if (area) {
      const a = areas.find((x) => x.id.endsWith(":" + area) || x.id === area);
      crumb += ` → <span>${a ? a.name : area}</span>`;
    }
    if ($("crumb")) $("crumb").innerHTML = crumb;

    if (!city) {
      if ($("home-grid")) {
        $("home-grid").innerHTML = (data.cities || []).map((c) => `
          <article class="cam citypick" onclick="SSRegistry.pickCity('${c.id}')">
            <h3>${c.name}</h3>
            <div class="meta">Government cameras in this city</div>
            <b style="font-size:22px;color:var(--accent)">${fmt(c.cameras)}</b>
          </article>`).join("");
      }
      return;
    }

    if (!area) {
      if ($("home-grid")) {
        $("home-grid").innerHTML = areas.map((a) => {
          const aid = a.id.includes(":") ? a.id.split(":")[1] : a.id;
          return `<article class="cam citypick" onclick="SSRegistry.pickArea('${aid}')">
            <h3>${a.name}</h3>
            <div class="meta">Select this area</div>
            <b style="font-size:22px;color:var(--accent)">${fmt(a.cameras)}</b>
          </article>`;
        }).join("");
      }
      return;
    }

    if ($("home-grid")) {
      $("home-grid").innerHTML = cams.map(camCard).join("") || "<p class='meta'>No cameras in this area yet.</p>";
    }
  }

  async function loadAreas() {
    const city = SSState.get("city");
    if (!city) return;
    const j = await SSApi.getAreas(city);
    SSState.set("areas", j.areas || []);
  }

  async function loadCams(doRender = true) {
    const city = SSState.get("city");
    const area = SSState.get("area");
    if (!city || !area) return;
    const j = await SSApi.getCameras(city, area);
    SSState.set("cams", j.cameras || []);
    if (doRender) {
      renderHome();
      if ($("cam-list")) $("cam-list").innerHTML = (j.cameras || []).map(camCard).join("");
    }
  }

  async function pickCity(id) {
    SSState.set("city", id);
    SSState.set("area", "");
    SSState.set("cams", []);
    await loadAreas();
    renderHome();
  }

  async function pickArea(id, stay) {
    SSState.set("area", id);
    await loadCams(true);
    if (stay === "live") SSApp.tab("live", document.querySelector('[data-tab="live"]'));
    else SSApp.tab("cams", document.querySelector('[data-tab="cams"]'));
  }

  function backLevel(n) {
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
    renderHome();
    SSApp.tab("home", document.querySelector('[data-tab="home"]'));
  }

  async function addCam() {
    const city = SSState.get("city");
    const area = SSState.get("area");
    if (!city || !area) {
      alert("First open a city and an area.");
      return;
    }
    const name = $("nc-name")?.value || "New camera";
    const data = SSState.get("data");
    const place = (data.cities || []).find((c) => c.id === city)?.name || "Gujarat";
    await SSApi.addCamera({
      name,
      city_id: city,
      area_id: area,
      owner: "Gujarat Police",
      place,
    });
    if ($("nc-name")) $("nc-name").value = "";
    loadCams();
  }

  return {
    badge,
    camCard,
    renderHome,
    loadAreas,
    loadCams,
    pickCity,
    pickArea,
    backLevel,
    addCam,
  };
});
