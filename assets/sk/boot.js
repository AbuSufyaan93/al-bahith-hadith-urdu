/* Al-Bahith Al-Hadithi — External CSP-Safe & Proxy-Aware SvelteKit 2 Bootstrapper */
import * as kit from "./immutable/entry/start.9l1BeuGn.js";
import * as app from "./immutable/entry/app.DLfzROMA.js";

const base = globalThis.__ALBAHITH_BASE_PATH__ || "";
const cfg = {
  base,
  assets: base,
  version: "1794313800351",
};
globalThis.__sveltekit_16nttps = cfg;
globalThis.__SVELTEKIT_PAYLOAD__ = cfg;

const element = document.getElementById("sveltekit-root") || document.body;

function reportBoot(ok, detail) {
  try {
    const payload = JSON.stringify({
      ok: !!ok,
      href: String(location.href || ""),
      base,
      detail: String(detail || ""),
    });
    const url = base + "/api/v1/client-boot";
    fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: payload,
      keepalive: true,
    }).catch(() => {});
  } catch (_) {}
}

try {
  kit.init(cfg);
  kit
    .start(app, element)
    .then(() => {
      document.documentElement.setAttribute("data-sk-mounted", "1");
      window.dispatchEvent(new CustomEvent("albahith:mounted"));
      reportBoot(true, "mounted");
    })
    .catch((err) => {
      document.documentElement.setAttribute("data-sk-mounted", "error");
      console.error("[Al-Bahith Boot Error]", err);
      reportBoot(false, err && (err.stack || err.message || err));
    });
} catch (syncErr) {
  document.documentElement.setAttribute("data-sk-mounted", "error");
  console.error("[Al-Bahith Sync Boot Error]", syncErr);
  reportBoot(false, syncErr && (syncErr.stack || syncErr.message || syncErr));
}
