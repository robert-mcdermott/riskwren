#!/usr/bin/env node
// The screen-reader check. It reads each main journey's accessibility tree as the browser
// computes it, which is what a screen reader is given, and checks what a person who cannot
// see the screen needs: one main landmark and a way past the menu, one level-one heading and
// no skipped levels, a name on everything that can be pressed or filled in, a name on every
// dialog that opens, and status messages announced where they appear.
//
//   node scripts/screen-reader-check.mjs
//
// It exits with 1 if anything is found. It does not replace a person going through the app
// with a screen reader; it catches what such a person would trip over first.

import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";

const first = (api, pick = "(rows) => rows[0].ref") => async (page) => page.evaluate(
  `fetch(${JSON.stringify(api)}).then((r) => r.json()).then((body) => (${pick})(body.data))`);
const press = (text) => `(() => { const el = [...document.querySelectorAll("button, a")].find((each) => each.textContent.trim() === ${JSON.stringify(text)}); if (el) el.click(); return Boolean(el); })()`;

// The journeys people take most, as the people who take them.
const JOURNEYS = [
  { name: "home", as: "ciso", path: "/" },
  { name: "the register", as: "cro", path: "/risks" },
  { name: "a risk", as: "cro", path: async (page) => `/risks/${await first("/api/v1/risks?limit=1")(page)}` },
  { name: "assess a risk", as: "bio_mgr", path: async (page) => `/risks/${await first("/api/v1/risks?mine=true&limit=1")(page)}`, step: press("Assess") },
  { name: "the compliance dashboard", as: "ciso", path: "/compliance" },
  { name: "a scope", as: "ciso", path: async (page) => `/scopes/${await first("/api/v1/scopes?limit=1")(page)}` },
  { name: "report something", as: "member", path: "/incidents?report=1" },
  { name: "an incident", as: "ciso", path: async (page) => `/incidents/${await first("/api/v1/incidents?limit=1")(page)}` },
  { name: "the policy library", as: "member", path: "/library" },
  { name: "notices", as: "ciso", path: "/notices" },
  { name: "appearance", as: "admin", path: "/admin/appearance" },
];

const INTERACTIVE = new Set(["button", "link", "textbox", "searchbox", "combobox", "checkbox", "radio", "switch",
  "menuitem", "tab", "slider", "spinbutton", "listbox", "option"]);

function problemsIn(nodes) {
  const found = [];
  const shown = nodes.filter((node) => !node.ignored);
  const role = (node) => node.role?.value ?? "";
  const name = (node) => String(node.name?.value ?? "").trim();
  const mains = shown.filter((node) => role(node) === "main");
  if (mains.length !== 1) found.push(`${mains.length} main landmarks, not one`);
  const headings = shown.filter((node) => role(node) === "heading")
    .map((node) => ({ level: Number(node.properties?.find((p) => p.name === "level")?.value?.value ?? 0), text: name(node) }));
  if (headings.filter((h) => h.level === 1).length !== 1) found.push(`${headings.filter((h) => h.level === 1).length} level-one headings, not one`);
  for (let i = 1; i < headings.length; i += 1) {
    if (headings[i].level > headings[i - 1].level + 1) found.push(`heading "${headings[i].text}" skips from level ${headings[i - 1].level} to ${headings[i].level}`);
  }
  for (const node of shown) {
    if (INTERACTIVE.has(role(node)) && !name(node)) {
      const disabled = node.properties?.some((p) => p.name === "disabled" && p.value?.value);
      if (!disabled) found.push(`a ${role(node)} with no name`);
    }
    if ((role(node) === "dialog" || role(node) === "alertdialog") && !name(node)) found.push("a dialog with no name");
  }
  const links = shown.filter((node) => role(node) === "link").map(name);
  if (!links.some((text) => /skip|main content/i.test(text))) found.push("no way past the menu (a skip link)");
  return [...new Set(found)];
}

const demo = await startDemo();
const page = await openBrowser();
let total = 0;
try {
  await page.size(1360, 900);
  let who = null;
  for (const journey of JOURNEYS) {
    if (journey.as !== who) {
      await signInAs(page, demo.base, journey.as);
      who = journey.as;
    }
    await page.goto(demo.base + (typeof journey.path === "function" ? await journey.path(page) : journey.path));
    await page.settled();
    if (journey.step) {
      await page.evaluate(journey.step);
      await new Promise((done) => setTimeout(done, 400));
    }
    const { nodes } = await page.cdp("Accessibility.getFullAXTree", {});
    const live = await page.evaluate(`document.querySelectorAll('[role="status"], [aria-live="polite"], [aria-live="assertive"], [role="alert"]').length`);
    const found = problemsIn(nodes);
    if (!live) found.push("no live region, so status messages would go unannounced");
    total += found.length;
    console.log(`${found.length ? "✗" : "✓"} ${journey.name} (${journey.as})${found.length ? `\n    ${found.join("\n    ")}` : ""}`);
  }
} finally {
  await page.close();
  demo.stop();
}
console.log(total ? `\n${total} findings.` : `\nNo findings in ${JOURNEYS.length} journeys.`);
process.exit(total ? 1 : 0);
