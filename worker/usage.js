(() => {
  if (navigator.globalPrivacyControl || navigator.doNotTrack === "1") return;
  function count(event) {
    fetch("/api/count/" + event, {
      method: "POST", credentials: "omit", referrerPolicy: "no-referrer", keepalive: true
    }).catch(() => {});
  }
  const navigation = performance.getEntriesByType("navigation")[0];
  const sameSite = document.referrer && new URL(document.referrer).origin === location.origin;
  count(navigation?.type === "navigate" && !sameSite ? "arrival" : "view");

  const controls = {
    gpsBtn: "locate", wlGps: "locate", pickBtn: "pick_map",
    themeBtn: "theme", aboutBtn: "about", alTest: "test_alert", issCenter: "center_iss"
  };
  document.addEventListener("click", event => {
    const el = event.target.closest?.("button, a");
    if (!event.isTrusted || !el) return;
    const action = Object.hasOwn(controls, el.id) ? controls[el.id] :
      el.classList.contains("iss-btn") ? ({ "Track the International Space Station live": "iss",
        "Show live satellite cloud cover": "clouds" })[el.title] : null;
    if (action) count(action);
  }, true);
  document.addEventListener("submit", event => {
    if (event.isTrusted && event.target.id === "searchForm") count("search");
  }, true);
})();
