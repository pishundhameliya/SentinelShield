/**
 * Chat Drawer module — real-time WebSocket team room communication
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSChat = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;
  let ws = null;

  function toggleChat() {
    const current = SSState.get("chatOpen");
    const next = !current;
    SSState.set("chatOpen", next);
    $("chatdraw")?.classList.toggle("hidden", !next);
    $("chatback")?.classList.toggle("hidden", !next);
    if (next && $("chatlog")) {
      $("chatlog").scrollTop = $("chatlog").scrollHeight;
    }
  }

  function openWs() {
    if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws");
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "chat") {
          const data = SSState.get("data") || {};
          data.chat = data.chat || [];
          data.chat.push(m);
          renderChatMessages();
        }
      } catch (e) {}
    };
  }

  function renderChatMessages() {
    const data = SSState.get("data") || {};
    const chat = data.chat || [];
    if ($("chatdot")) $("chatdot").textContent = chat.length;
    const log = $("chatlog");
    if (log) {
      const stick = log.scrollTop + log.clientHeight >= log.scrollHeight - 50;
      log.innerHTML = chat.map((m) => `<div class="msg"><b>${escapeHtml(m.user)}</b>
        <span class="t">${(m.created || "").slice(11, 19)}</span><p>${escapeHtml(m.text)}</p></div>`).join("");
      if (stick || SSState.get("chatOpen")) log.scrollTop = log.scrollHeight;
    }
  }

  async function sendChat(e) {
    if (e && e.preventDefault) e.preventDefault();
    const text = $("chatbox")?.value.trim() || "";
    if (!text) return;
    const token = SSState.get("token");

    if (ws && ws.readyState === 1) {
      ws.send(JSON.stringify({ type: "chat", token, text, room: "team" }));
    } else {
      await SSApi.postChat(text, token, "team");
      SSApp.refresh();
    }
    if ($("chatbox")) $("chatbox").value = "";
  }

  return {
    toggleChat,
    openWs,
    renderChatMessages,
    sendChat,
  };
});
