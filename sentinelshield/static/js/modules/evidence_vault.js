/**
 * Evidence Vault module — sealing evidence packs, SHA-256 fingerprint preview, and ranked seriousness scores
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SSEvidence = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = SSState.escapeHtml;

  async function loadVault() {
    let packs = [];
    let ranked = [];
    try {
      packs = (await SSApi.getEvidence()).packs || [];
    } catch (e) {}
    try {
      ranked = (await SSApi.rankEvidence()).ranked || [];
    } catch (e) {}

    let html = ranked.slice(0, 8).map((e) =>
      "<tr><td>" + escapeHtml(e.created || "") + "</td><td>Score " + (e.rank_score || "") +
      " · " + escapeHtml(e.kind || "") + "</td><td>" + escapeHtml(e.title || "") + "</td></tr>"
    ).join("");

    html += packs.map((e) =>
      "<tr><td>" + escapeHtml(e.created || "") + "</td><td>Saved file</td><td style='font-size:11px'>" +
      escapeHtml((e.sha256 || "").slice(0, 24)) + "…</td></tr>"
    ).join("");

    if ($("tools-evd-rows")) $("tools-evd-rows").innerHTML = html || "<tr><td colspan='3'>Press Save evidence now.</td></tr>";
    if ($("evd-rows")) $("evd-rows").innerHTML = html || "<tr><td colspan='3'>Press Seal evidence pack.</td></tr>";

    try {
      const hc = await SSApi.getHotCams();
      const optionsHtml = (hc.cameras || []).map((c) =>
        '<option value="' + c.id + '">' + c.name + "</option>").join("");
      document.querySelectorAll("select[id='ev-cam']").forEach((sel) => {
        sel.innerHTML = optionsHtml;
      });
    } catch (e) {}
  }

  async function sealEvidence() {
    const activeSelect = document.querySelector("section:not(.hidden) select[id='ev-cam']") || $("ev-cam");
    const id = (activeSelect && activeSelect.value) || "cam-gate";
    const j = await SSApi.sealEvidence(id);
    if (!j.ok) {
      alert(j.error || "Could not save");
      return;
    }
    alert("Saved. Fingerprint:\n" + (j.sha256 || "").slice(0, 32) + "…");
    loadVault();
  }

  return {
    loadVault,
    sealEvidence,
  };
});
