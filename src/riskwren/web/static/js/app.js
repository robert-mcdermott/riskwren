// The web app's entry point: find out about the product and who is signed in, then draw.

import { get, peek } from "./core/api.js";
import { h } from "./core/dom.js";
import { apply, setOrganizationPalette, setOrganizationRamp } from "./core/prefs.js";
import { fallback, route, start } from "./core/router.js";
import { can, setSession } from "./core/session.js";
import { openPalette } from "./components/cmdk.js";
import { commands, mountShell } from "./components/shell.js";
import { emptyState } from "./components/ui.js";
import { setProduct, setTitle } from "./pages/page.js";

apply(); // paint with the remembered mode and palette before anything else
const root = document.getElementById("app");

function applyBranding(meta) {
  setProduct(meta.branding.product_name);
  setOrganizationPalette(meta.branding.palette);
  setOrganizationRamp(meta.branding.rating_ramp);
  document.getElementById("favicon").href = meta.branding.favicon || "/img/wren-mark.svg";
}

async function boot() {
  let meta;
  try {
    meta = (await get("/api/v1/meta", null, { fresh: true })).data;
  } catch {
    root.replaceChildren(h("div", { class: "page" }, emptyState({ iconName: "alert",
      title: "The server is not responding", text: "Check that it is running, then reload this page." })));
    return;
  }
  applyBranding(meta);

  let me = null;
  try {
    me = (await peek("/api/v1/session")).data;
  } catch (error) {
    if (error.status !== 401) throw error;
  }
  if (!me) {
    const path = window.location.pathname + window.location.search;
    if (window.location.pathname !== "/sign-in") {
      history.replaceState({}, "", path === "/" ? "/sign-in" : `/sign-in?next=${encodeURIComponent(path)}`);
    }
    (await import("./pages/sign-in.js")).signIn(root, meta);
    return;
  }
  setSession(me);
  if (window.location.pathname === "/sign-in") history.replaceState({}, "", "/");

  const { main, redrawBrand } = mountShell(root, meta);
  const page = (file, name, ...extra) => async (params) => (await import(`./pages/${file}.js`))[name](main, ...extra, params);

  route("/", page("home", "home", meta));
  route("/account", page("account", "account"));
  if (can("admin")) {
    route("/admin/people", page("admin-people", "adminPeople"));
    route("/admin/units", page("admin-units", "adminUnits"));
    route("/admin/appearance", page("admin-appearance", "adminAppearance"));
  }
  fallback(page("not-found", "notFound"));

  window.addEventListener("riskwren:signed-out", () => window.location.reload());
  window.addEventListener("riskwren:branding", async () => {
    const next = (await get("/api/v1/meta", null, { fresh: true })).data;
    Object.assign(meta, next);
    applyBranding(meta);
    redrawBrand(meta);
    const theme = document.getElementById("theme");
    theme.href = `/theme.css?v=${Date.now()}`;
    setTitle(document.querySelector("h1")?.textContent ?? "");
  });
  document.addEventListener("keydown", (event) => {
    const typing = event.target.closest?.("input, textarea, select, [contenteditable]");
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openPalette(commands(meta));
    } else if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
      openPalette(commands(meta));
    }
  });
  await start();
}

boot();
