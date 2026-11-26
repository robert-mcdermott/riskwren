#!/usr/bin/env node
// The automated accessibility audit. It builds a fresh demo organization, opens every scene
// below as the right sample person in every palette, by day and after dark, and checks what
// a machine can check: names on controls, labels on fields, headings, landmarks, duplicate
// ids, and the contrast of every piece of text against what is behind it.
//
//   node scripts/a11y-audit.mjs            every scene, every palette and mode
//   node scripts/a11y-audit.mjs risk       scenes whose name contains "risk"
//
// It exits with 1 if anything is found. It does not replace the keyboard and screen-reader
// checks in the release checklist.

import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";
import { SCENES } from "./lib/scenes.mjs";

const PALETTES = ["wren", "slate", "garnet"];
const MODES = ["light", "dark"];

// Runs in the page. Returns a list of findings, each { rule, detail }.
const AUDIT = String.raw`(() => {
  const findings = [];
  const add = (rule, element, extra = "") => {
    const tag = element.tagName.toLowerCase();
    const where = element.id ? "#" + element.id : element.className && typeof element.className === "string"
      ? "." + element.className.trim().split(/\s+/).join(".") : "";
    const text = (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 50);
    findings.push({ rule, detail: tag + where + (text ? ' "' + text + '"' : "") + (extra ? " — " + extra : "") });
  };
  const visible = (el) => {
    if (!el.isConnected || el.closest("[hidden], [aria-hidden='true']")) return false;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility !== "visible") return false;
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  };
  const named = (el) => {
    if (el.getAttribute("aria-label")?.trim()) return true;
    const by = el.getAttribute("aria-labelledby");
    if (by && by.split(/\s+/).some((id) => document.getElementById(id)?.textContent.trim())) return true;
    if (el.labels && [...el.labels].some((label) => label.textContent.trim())) return true;
    if (el.matches("input[type=submit], input[type=button]") && el.value) return true;
    if (el.matches("img") && el.hasAttribute("alt")) return true;
    if (el.title?.trim()) return true;
    if (el.closest("label")?.textContent.trim()) return true;
    const img = el.querySelector?.("img[alt]:not([alt=''])");
    return Boolean(el.textContent.trim() || img);
  };

  if (!document.documentElement.lang) findings.push({ rule: "page-lang", detail: "html has no lang" });
  if (!document.title.trim()) findings.push({ rule: "page-title", detail: "the page has no title" });
  if (document.querySelectorAll("main").length !== 1) findings.push({ rule: "landmark-main", detail: "expected exactly one main" });

  for (const img of document.querySelectorAll("img")) if (!img.hasAttribute("alt")) add("image-alt", img);
  for (const el of document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [role=menuitem], [role=tab], [role=option]")) {
    if (visible(el) && !named(el)) add("control-name", el);
  }
  for (const el of document.querySelectorAll("[tabindex]")) if (Number(el.getAttribute("tabindex")) > 0) add("tabindex-positive", el);
  const ids = new Map();
  for (const el of document.querySelectorAll("[id]")) ids.set(el.id, (ids.get(el.id) || 0) + 1);
  for (const [id, count] of ids) if (count > 1) findings.push({ rule: "duplicate-id", detail: "#" + id + " appears " + count + " times" });
  for (const el of document.querySelectorAll("[aria-labelledby], [aria-describedby], [aria-controls], label[for]")) {
    for (const attr of ["aria-labelledby", "aria-describedby", "aria-controls", "for"]) {
      const value = el.getAttribute(attr);
      if (!value || (attr === "for" && el.tagName !== "LABEL")) continue;
      for (const id of value.split(/\s+/)) if (id && !document.getElementById(id)) add("reference-missing", el, attr + "=" + id);
    }
  }
  const headings = [...document.querySelectorAll("h1, h2, h3, h4, h5, h6")].filter(visible);
  if (headings.filter((h) => h.tagName === "H1").length !== 1) findings.push({ rule: "heading-one", detail: "expected exactly one h1, found " + headings.filter((h) => h.tagName === "H1").length });
  let last = 0;
  for (const heading of headings) {
    const level = Number(heading.tagName[1]);
    if (last && level > last + 1) add("heading-order", heading, "h" + last + " is followed by h" + level);
    last = level;
  }
  for (const el of document.querySelectorAll("button, a[href], input[type=checkbox], input[type=radio], select")) {
    if (!visible(el) || el.closest(".visually-hidden")) continue;
    const box = el.getBoundingClientRect();
    // Links in running text are exempt; so is a text link that stands alone with space around it.
    const inline = el.tagName === "A" && !/\bbtn\b|nav-link|icon-button/.test(el.className);
    const target = el.matches("input[type=checkbox], input[type=radio]") ? (el.closest("label, .check") ?? el).getBoundingClientRect() : box;
    if (!inline && (target.width < 24 || target.height < 24)) add("target-size", el, Math.round(target.width) + "×" + Math.round(target.height));
  }

  // Contrast. Colors are read back from a canvas, so any CSS color the browser understands works.
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const paint = (colors) => {
    ctx.clearRect(0, 0, 1, 1);
    for (const color of colors) { ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1); }
    return ctx.getImageData(0, 0, 1, 1).data;
  };
  const luminance = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const behind = (el) => {
    const layers = [];
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.backgroundImage !== "none") return null; // cannot be judged by color alone
      layers.unshift(style.backgroundColor);
    }
    return ["#fff", ...layers];
  };
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const el = node.parentElement;
    if (!node.textContent.trim() || seen.has(el) || !visible(el)) continue;
    seen.add(el);
    if (el.closest("[disabled], [aria-disabled='true'], .visually-hidden, option")) continue;
    const style = getComputedStyle(el);
    if (Number(style.opacity) === 0) continue;
    const layers = behind(el);
    if (!layers) continue;
    const bg = paint(layers);
    const fg = paint([...layers, style.color]);
    const [hi, lo] = [luminance(bg), luminance(fg)].sort((a, b) => b - a);
    const ratio = (hi + 0.05) / (lo + 0.05);
    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5) - 0.01) add("contrast", el, ratio.toFixed(2) + ":1, needs " + (large ? "3" : "4.5") + ":1");
  }
  return findings;
})()`;

const only = process.argv.slice(2);
const scenes = SCENES.filter((scene) => !only.length || only.some((word) => scene.name.includes(word)));
const demo = await startDemo();
const page = await openBrowser();
let total = 0;
try {
  await page.size(1360, 900);
  let who = null;
  for (const scene of scenes) {
    if (scene.as !== who) {
      await signInAs(page, demo.base, scene.as);
      who = scene.as;
    }
    const found = new Map();
    for (const palette of PALETTES) {
      for (const mode of MODES) {
        await page.scheme(mode);
        await page.goto(demo.base + (typeof scene.path === "function" ? await scene.path(page) : scene.path));
        await page.evaluate(`localStorage.setItem("riskwren.palette", ${JSON.stringify(palette)}); localStorage.removeItem("riskwren.mode")`);
        await page.goto(demo.base + (typeof scene.path === "function" ? await scene.path(page) : scene.path));
        await page.settled();
        if (scene.step) { await page.evaluate(scene.step); await new Promise((r) => setTimeout(r, 400)); }
        for (const finding of await page.evaluate(AUDIT)) {
          const key = `${finding.rule}: ${finding.detail}`;
          const where = finding.rule === "contrast" ? ` [${palette} ${mode}]` : "";
          if (!found.has(key + where)) found.set(key + where, true);
        }
      }
    }
    const lines = [...found.keys()];
    total += lines.length;
    console.log(`${lines.length ? "✗" : "✓"} ${scene.name} (${scene.as})`);
    for (const line of lines.slice(0, 40)) console.log(`    ${line}`);
    if (lines.length > 40) console.log(`    … and ${lines.length - 40} more`);
  }
} catch (error) {
  console.error(`\nThe audit stopped: ${error.message}`);
  total += 1;
} finally {
  await page.close();
  demo.stop();
}
console.log(total ? `\n${total} findings.` : `\nNo findings in ${scenes.length} scenes, ${PALETTES.length} palettes, ${MODES.length} modes.`);
process.exit(total ? 1 : 0);
