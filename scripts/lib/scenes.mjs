// The screens the documentation shows and the accessibility audit walks. One line each:
// a name, who is signed in (a key from the demo's sample people), a path, and optionally a
// step to run in the page first (a JavaScript expression), such as opening a dialog.
//
// A path may be a function of the page, for addresses that depend on what the demo holds.

const first = (api, pick = "(rows) => rows[0].ref") => async (page) => page.evaluate(
  `fetch(${JSON.stringify(api)}).then((r) => r.json()).then((body) => (${pick})(body.data))`);
const click = (text) => `[...document.querySelectorAll("button, a")].find((el) => el.textContent.trim() === ${JSON.stringify(text)})?.click()`;
const risk = (words, tab = "") => async (page) =>
  `/risks/${await first(`/api/v1/risks?q=${encodeURIComponent(words)}`)(page)}${tab ? `?tab=${tab}` : ""}`;

export const SCENES = [
  { name: "home-manager", as: "cro", path: "/" },
  { name: "home-steward", as: "bio_mgr", path: "/" },
  { name: "home-member", as: "member", path: "/" },
  { name: "dashboard", as: "cro", path: "/dashboard" },
  { name: "heat-map", as: "cro", path: "/heat-map" },
  { name: "risks", as: "cro", path: "/risks" },
  { name: "risk", as: "bio_mgr", path: risk("irreplaceable specimens from freezer") },
  { name: "risk-controls", as: "bio_mgr", path: risk("irreplaceable specimens from freezer", "controls") },
  { name: "risk-treatment", as: "bio_mgr", path: risk("irreplaceable specimens from freezer", "treatment") },
  { name: "risk-assessments", as: "bio_mgr", path: risk("irreplaceable specimens from freezer", "assessments") },
  { name: "risk-history", as: "cro", path: risk("irreplaceable specimens from freezer", "history") },
  { name: "risk-assess", as: "bio_mgr", path: risk("irreplaceable specimens from freezer"), step: click("Assess") },
  { name: "risk-accepted", as: "cores_lead", path: risk("cryo-electron microscope", "treatment") },
  { name: "risk-beyond-limit", as: "bio_dir", path: risk("hosted specimen tracking", "treatment") },
  { name: "risk-new", as: "bio_mgr", path: "/risks", step: click("New risk") },
  { name: "plans", as: "cro", path: "/plans" },
  { name: "acceptances", as: "cro", path: "/acceptances" },
  { name: "actions", as: "cro", path: "/actions" },
  { name: "controls", as: "cro", path: "/controls" },
  { name: "control", as: "assess1",
    path: async (page) => `/controls/${await first("/api/v1/controls?q=cold+storage+monitored")(page)}` },
  { name: "processes", as: "cro", path: "/processes" },
  { name: "process", as: "bio_mgr",
    path: async (page) => `/processes/${await first("/api/v1/processes?q=specimen+storage")(page)}` },
  { name: "systems", as: "cro", path: "/systems" },
  { name: "system", as: "bio_mgr",
    path: async (page) => `/systems/${await first("/api/v1/systems?q=freezer+farm")(page)}` },
  { name: "third-parties", as: "cro", path: "/third-parties" },
  { name: "third-party", as: "cro",
    path: async (page) => `/third-parties/${await first("/api/v1/third-parties?q=brightwater")(page)}` },
  { name: "program", as: "cro", path: "/admin/program" },
  { name: "people", as: "admin", path: "/admin/people" },
  { name: "units", as: "admin", path: "/admin/units" },
  { name: "appearance", as: "admin", path: "/admin/appearance" },
  { name: "account", as: "member", path: "/account" },
  { name: "auditor-risks", as: "auditor", path: "/risks" },
];
