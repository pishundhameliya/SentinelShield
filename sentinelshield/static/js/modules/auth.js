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
    const j = await SSApi.login(userVal, passVal);
    if (!j.ok) {
      alert(j.error || "Login failed");
      return;
    }
    SSState.set("token", j.token);
    SSState.set("user", j.user);
    localStorage.setItem("ss_token", j.token);
    if (onSuccess) onSuccess();
  }

  function logout() {
    SSState.set("token", "");
    SSState.set("user", null);
    localStorage.removeItem("ss_token");
    $("app")?.classList.add("hidden");
    $("login")?.classList.remove("hidden");
  }

  async function checkSession(onSuccess) {
    const token = SSState.get("token");
    if (!token) return;
    try {
      const j = await SSApi.getMe(token);
      if (j.ok && j.user) {
        SSState.set("user", j.user);
        if (onSuccess) onSuccess();
      }
    } catch (e) {}
  }

  return {
    doLogin,
    logout,
    checkSession,
  };
});
