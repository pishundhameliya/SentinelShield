/**
 * SentinelShield Shared Reactive Client State
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSState = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const listeners = {};

  const state = {
    token: localStorage.getItem("ss_token") || "",
    user: null,
    data: { alerts: [], watchlist: [], chat: [], cities: [] },
    cams: [],
    liveCams: [],
    city: "",
    area: "",
    areas: [],
    currentLiveCamId: "sentinel-cam-26",
    chatOpen: false,
  };

  function get(key) {
    return state[key];
  }

  function set(key, value) {
    const old = state[key];
    state[key] = value;
    if (listeners[key]) {
      listeners[key].forEach((cb) => cb(value, old));
    }
  }

  function on(key, callback) {
    if (!listeners[key]) listeners[key] = [];
    listeners[key].push(callback);
  }

  function fmt(n) {
    return (n || 0).toLocaleString("en-IN");
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"]/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
    }[c]));
  }

  return {
    state,
    get,
    set,
    on,
    fmt,
    escapeHtml,
  };
});
