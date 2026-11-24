/* Apply the saved theme before first paint to avoid a flash of the wrong colours.
 * Kept as a file (not inline) so the Content Security Policy can forbid inline scripts. */
(() => {
  let pref = "auto";
  try { pref = localStorage.getItem("solarrt.theme") || "auto"; } catch { /* storage blocked */ }
  const dark = pref === "dark" || (pref === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
})();
