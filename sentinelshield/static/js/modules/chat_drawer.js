/**
 * Chat Drawer module — static desk assistant (rule-based, runs fully in the browser).
 * Answers come from pre-written replies plus counts already loaded in SSState;
 * nothing typed here is sent to the server.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSChat = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;
  const STORE = "ss_bot_log";

  const SUGGESTIONS = [
    "What can you do?",
    "Show open alerts",
    "How do I track a vehicle?",
    "How to open a live camera?",
    "How is evidence sealed?",
  ];

  let log = loadLog();
  let unread = log.length ? 0 : 1;
  let typing = false;

  function loadLog() {
    try { return JSON.parse(sessionStorage.getItem(STORE) || "[]"); } catch (e) { return []; }
  }

  function saveLog() {
    try { sessionStorage.setItem(STORE, JSON.stringify(log.slice(-60))); } catch (e) {}
  }

  function clock() {
    return new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  }

  function data() { return SSState.get("data") || {}; }

  function firstName() {
    const u = SSState.get("user");
    return u && u.name ? escapeHtml(String(u.name).split(" ")[0]) : "Officer";
  }

  const act = (label, action) => ({ label, action });

  // ---------------------------------------------------------------- replies
  const PLATE_RE = /\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4})\b/i;

  const INTENTS = [
    {
      test: /\b(hi|hello|hey|namaste|namaskar|good (morning|afternoon|evening))\b/,
      reply: () => ({
        html: `Namaste ${firstName()}. I am the SentinelShield desk assistant. Ask me how to use any part of the command desk.`,
        actions: [act("What can you do?", "ask:what can you do")],
      }),
    },
    {
      test: /(what can you do|^help\W*$|features|guide|how to use|menu)/,
      reply: () => ({
        html: `I can help you with:<ul>
          <li><b>Alerts &amp; threats</b> — open counts and latest incidents</li>
          <li><b>Vehicle tracking</b> — type a number like GJ05SS2026</li>
          <li><b>Live CCTV</b> and ANPR plate scanning</li>
          <li><b>Watchlist</b> — stolen / blacklisted vehicles</li>
          <li><b>Evidence</b> — Section 65B / BSA 2023 sealing</li>
          <li><b>Map</b>, cyber honeypot and camera registry</li></ul>`,
        actions: [act("Open alerts", "tab:alerts"), act("Track a vehicle", "tab:find"), act("Live cameras", "tab:live")],
      }),
    },
    {
      test: /(alert|threat|incident|panic|abandon|weapon|crowd)/,
      reply: () => {
        const all = data().alerts || [];
        const open = all.filter((a) => a.status === "new");
        const critical = open.filter((a) => a.severity === "CRITICAL");
        const latest = open.slice(0, 3).map((a) =>
          `<li>${escapeHtml(a.title)} <span class="meta">· ${escapeHtml(a.camera_id || "")}</span></li>`).join("");
        return {
          html: `There are <b>${open.length}</b> open alerts (${critical.length} critical) out of ${all.length} total.` +
            (latest ? `<ul>${latest}</ul>` : "") +
            `Open an alert and press <b>Seen</b> or <b>Done</b> after checking it.`,
          actions: [act("Open alerts", "tab:alerts"), act("Open threats", "tab:threats")],
        };
      },
    },
    {
      test: /(watchlist|stolen|blacklist|suspect)/,
      reply: () => {
        const wl = data().watchlist || [];
        const items = wl.slice(0, 5).map((w) =>
          `<li><b>${escapeHtml(w.plate)}</b> — ${escapeHtml(w.kind)}${w.note ? " · " + escapeHtml(w.note) : ""}</li>`).join("");
        return {
          html: `The watchlist has <b>${wl.length}</b> vehicle numbers.` + (items ? `<ul>${items}</ul>` : "") +
            `Every plate read by ANPR is matched against this list automatically.`,
          actions: [act("Open watchlist", "tab:watch")],
        };
      },
    },
    {
      test: /\b(track|find|vehicle|route|number plate|car|bike)\b/,
      reply: () => ({
        html: `To track a vehicle, type its number in the <b>Find vehicle</b> box at the top (e.g. GJ05SS2026) and press Find. You will see the last camera, the full route and the direction of travel.`,
        actions: [act("Track GJ05SS2026", "plate:GJ05SS2026"), act("Open Find vehicle", "tab:find")],
      }),
    },
    {
      test: /(anpr|scan|ocr|deblur|plate read)/,
      reply: () => ({
        html: `Open <b>Live</b>, click a camera in the list, then press <b>Run AI Scan on Selected Feed</b> under the video. Detected vehicles and enhanced plate crops appear below.`,
        actions: [act("Open Live", "tab:live")],
      }),
    },
    {
      test: /(live|cctv|camera|feed|video|stream)/,
      reply: () => ({
        html: `Open the <b>Live</b> tab and click any camera in the list on the right — it plays in the monitor on the left. Use <b>Pause</b>, <b>Play</b> or <b>Stop live</b> above the video.`,
        actions: [act("Open Live", "tab:live"), act("Browse cities", "tab:home")],
      }),
    },
    {
      test: /(evidence|65b|bsa|seal|sha|hash|court|forensic)/,
      reply: () => ({
        html: `Evidence packs are sealed with a <b>SHA-256 fingerprint</b> and frame watermark for Section 65B / Bharatiya Sakshya Adhiniyam, 2023. Go to <b>Tools → Save important video</b>, choose the camera and press <b>Save evidence now</b>.`,
        actions: [act("Open Tools", "tab:tools")],
      }),
    },
    {
      test: /(map|heat|twin|drone|gis|risk)/,
      reply: () => ({
        html: `The <b>Map</b> tab shows the digital twin: predicted risk heat (red), cyber hits (orange) and cameras (blue). You can also draw a suspect route or launch a simulated drone.`,
        actions: [act("Open Map", "tab:map")],
      }),
    },
    {
      test: /(cyber|honeypot|hack|tamper|attack|freeze|black screen)/,
      reply: () => ({
        html: `Tamper (frozen / black / replaced video) and network attacks are logged automatically. The fake-camera <b>honeypot</b> and full cyber log are in <b>Tools</b>.`,
        actions: [act("Open Tools", "tab:tools")],
      }),
    },
    {
      test: /(city|cities|area|registry|how many)/,
      reply: () => {
        const d = data();
        return {
          html: `The state registry holds <b>${SSState.fmt(d.estate_total)}</b> government cameras across <b>${(d.cities || []).length}</b> cities / groups. Open a city, then an area, to see its cameras.`,
          actions: [act("Open Cities", "tab:home")],
        };
      },
    },
    {
      test: /\b(ai|pause|resume|guardian)\b/,
      reply: () => {
        const ai = data().ai || {};
        return {
          html: `Continuous AI is <b>${ai.on ? "ON" : "paused"}</b>` + (ai.on ? ` · ${ai.cycles || 0} checks done.` : ".") +
            ` You can pause or resume it from the <b>Find vehicle</b> page.`,
          actions: [act("Open Find vehicle", "tab:find")],
        };
      },
    },
    {
      test: /(password|login|log in|sign out|logout|account)/,
      reply: () => ({
        html: `Use <b>Sign out</b> at the top right when leaving the desk. Password changes are handled by your system administrator — never share credentials in chat.`,
        actions: [],
      }),
    },
    {
      test: /(emergency|112|\b100\b|ambulance|fire)/,
      reply: () => ({
        html: `For any emergency, call <b>112</b> (Emergency Response Support System). This assistant is not an emergency line.`,
        actions: [],
      }),
    },
    {
      test: /(who are you|are you (a )?bot|your name)/,
      reply: () => ({
        html: `I am a built-in help assistant with pre-set answers. I run inside this page and do not send your messages anywhere.`,
        actions: [act("What can you do?", "ask:what can you do")],
      }),
    },
    {
      test: /\b(thank|thanks|dhanyavad|ok|okay|great)\b/,
      reply: () => ({ html: `You're welcome. Ask me anything else about the desk.`, actions: [] }),
    },
  ];

  function answer(question) {
    const plate = question.match(PLATE_RE);
    if (plate) {
      const p = plate[1].replace(/\s+/g, "").toUpperCase();
      return {
        html: `Vehicle number <b>${escapeHtml(p)}</b> detected. I can open Find vehicle and show its last camera and route.`,
        actions: [act("Track " + p, "plate:" + p), act("Open watchlist", "tab:watch")],
      };
    }
    const q = question.toLowerCase();
    for (const intent of INTENTS) {
      if (intent.test.test(q)) return intent.reply();
    }
    return {
      html: `Sorry, I don't have an answer for that. Try one of the suggestions below or ask about alerts, vehicles, live cameras, evidence or the map.`,
      actions: [act("What can you do?", "ask:what can you do")],
    };
  }

  // -------------------------------------------------------------- rendering
  function welcome() {
    log.push({
      from: "bot",
      time: clock(),
      html: `Namaste ${firstName()}. I am the SentinelShield desk assistant. Ask me about alerts, vehicle tracking, live cameras or evidence.`,
      actions: [act("What can you do?", "ask:what can you do"), act("Show open alerts", "ask:show open alerts")],
    });
    saveLog();
  }

  function msgHtml(m) {
    const actions = (m.actions || []).map((a) =>
      `<button type="button" class="chip" data-act="${escapeHtml(a.action)}">${escapeHtml(a.label)}</button>`).join("");
    return `<div class="msg ${m.from === "me" ? "me" : "bot"}">
      <div class="msg-body">${m.html}</div>
      ${actions ? `<div class="msg-actions">${actions}</div>` : ""}
      <span class="t">${escapeHtml(m.time || "")}</span>
    </div>`;
  }

  function renderLog() {
    const el = $("chatlog");
    if (!el) return;
    el.innerHTML = log.map(msgHtml).join("") +
      (typing ? `<div class="msg bot typing"><span></span><span></span><span></span></div>` : "");
    el.scrollTop = el.scrollHeight;
    const sug = $("chat-suggest");
    if (sug && !sug.childElementCount) {
      sug.innerHTML = SUGGESTIONS.map((s) =>
        `<button type="button" class="chip" data-act="ask:${escapeHtml(s)}">${escapeHtml(s)}</button>`).join("");
    }
  }

  function renderChatMessages() {
    const dot = $("chatdot");
    if (dot) {
      dot.textContent = unread;
      dot.hidden = unread === 0;
    }
  }

  function ask(text) {
    const q = String(text || "").trim();
    if (!q || typing) return;
    log.push({ from: "me", time: clock(), html: escapeHtml(q) });
    typing = true;
    renderLog();
    setTimeout(() => {
      typing = false;
      const r = answer(q);
      log.push({ from: "bot", time: clock(), html: r.html, actions: r.actions });
      saveLog();
      renderLog();
    }, 450);
  }

  function runAction(action) {
    const i = action.indexOf(":");
    const kind = action.slice(0, i);
    const value = action.slice(i + 1);
    if (kind === "ask") return ask(value);
    if (kind === "tab") {
      toggleChat(false);
      SSApp.tab(value, document.querySelector('[data-tab="' + value + '"]'));
    }
    if (kind === "plate") {
      toggleChat(false);
      if ($("qplate")) $("qplate").value = value;
      if ($("qplate2")) $("qplate2").value = value;
      SSVehicleFind.searchPlate();
    }
  }

  function toggleChat(force) {
    const next = typeof force === "boolean" ? force : !SSState.get("chatOpen");
    SSState.set("chatOpen", next);
    $("chatdraw")?.classList.toggle("hidden", !next);
    $("chatback")?.classList.toggle("hidden", !next);
    if (next) {
      if (!log.length) welcome();
      unread = 0;
      renderChatMessages();
      renderLog();
      setTimeout(() => $("chatbox")?.focus(), 50);
    }
  }

  function sendChat(e) {
    if (e && e.preventDefault) e.preventDefault();
    const box = $("chatbox");
    const text = box ? box.value : "";
    if (box) box.value = "";
    ask(text);
  }

  document.addEventListener("click", (e) => {
    const chip = e.target.closest && e.target.closest("#chatdraw [data-act]");
    if (chip) runAction(chip.getAttribute("data-act"));
  });

  return {
    toggleChat,
    renderChatMessages,
    sendChat,
    ask,
    answer,
  };
});
