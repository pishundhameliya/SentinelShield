/**
 * Assistant module — natural language operator query parser and speech recognition
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSAssistant = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);

  async function askBot() {
    const q = ($("askq") && $("askq").value) || "";
    if (!q) return;

    const j = await SSApi.ask(q);
    let msg = j.note || j.hint || ("Done: " + (j.intent || "ok"));

    if (j.intent === "watchlist" && j.data) {
      msg = "Blacklisted / stolen numbers:\n" + j.data.map((w) => w.plate + " — " + (w.note || w.kind)).join("\n");
    }
    if (j.intent === "alerts" && j.data) {
      msg = "Latest alerts:\n" + j.data.slice(0, 6).map((a) => a.title).join("\n");
    }
    if (j.intent === "cyber" && j.data) {
      msg = "Cyber hits:\n" + j.data.slice(0, 6).map((a) => a.kind + " — " + a.detail).join("\n");
    }

    if ($("ask-out")) $("ask-out").textContent = msg;

    if (j.tab && j.tab !== "help" && document.querySelector('[data-tab="' + j.tab + '"]')) {
      SSApp.tab(j.tab, document.querySelector('[data-tab="' + j.tab + '"]'));
    }
    if (j.intent === "vehicle") {
      if ($("qplate")) $("qplate").value = "GJ05SS2026";
      SSVehicleFind.searchPlate();
    }
  }

  function startVoice() {
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Rec) {
      alert("This browser has no voice input. Type in Ask instead.");
      return;
    }
    const r = new Rec();
    r.lang = "en-IN";
    r.onresult = function (ev) {
      const said = ev.results[0][0].transcript;
      if ($("askq")) $("askq").value = said;
      askBot();
    };
    r.start();
  }

  return {
    askBot,
    startVoice,
  };
});
