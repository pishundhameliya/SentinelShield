/**
 * Auth module — login, logout, and session verification
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSAuth = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);

  async function doLogin(onSuccess) {
    const userVal = $("user")?.value || "";
    const passVal = $("pass")?.value || "";
    let j = {};
    try {
      j = await SSApi.login(userVal, passVal);
    } catch (e) {
      j = { ok: false, error: "Server not reachable. Check that the SentinelShield server is running." };
    }
    if (!j.ok) {
      // Never leave a blank page: bring the sign-in form back
      $("app")?.classList.add("hidden");
      $("login")?.classList.remove("hidden");
      alert(j.error || "Login failed");
      return false;
    }
    SSState.set("token", j.token);
    SSState.set("user", j.user);
    localStorage.setItem("ss_token", j.token);
    if (onSuccess) onSuccess();
    return true;
  }

  function logout() {
    SSState.set("token", "");
    SSState.set("user", null);
    localStorage.removeItem("ss_token");
    $("app")?.classList.add("hidden");
    $("login")?.classList.remove("hidden");
  }

  async function checkSession(onSuccess, onInvalid) {
    const token = SSState.get("token");
    if (!token) {
      if (onInvalid) onInvalid();
      return;
    }
    try {
      const j = await SSApi.getMe(token);
      if (j.ok && j.user) {
        SSState.set("user", j.user);
        if (onSuccess) onSuccess();
        return;
      }
    } catch (e) {}
    // Sessions live in server memory, so a server restart invalidates saved tokens
    SSState.set("token", "");
    localStorage.removeItem("ss_token");
    if (onInvalid) onInvalid();
  }

  return {
    doLogin,
    logout,
    checkSession,
  };
});
