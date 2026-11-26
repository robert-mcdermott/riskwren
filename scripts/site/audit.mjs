#!/usr/bin/env node
// Checks the built documentation site as a reader's browser sees it. It builds the site into
// a temporary directory, serves it on this machine only, opens every page by day and after
// dark at desk and phone widths, and runs the same checks as the application's audit, plus
// two of its own: nothing is wider than the screen, and every picture loads.
//
//   node scripts/site/audit.mjs                every page
//   node scripts/site/audit.mjs compliance     pages whose name contains a word given
//   SHOTS=/some/dir node scripts/site/audit.mjs   also save a picture of each page there
//
// It exits with 1 if anything is found.

import { mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { extname, join, normalize, resolve } from "node:path";

import { AUDIT } from "../lib/audit.mjs";
import { openBrowser } from "../lib/browser.mjs";
import { build, MENU } from "./build.mjs";

const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".svg": "image/svg+xml", ".webp": "image/webp", ".png": "image/png" };
const SIZES = [["desk", 1360, 900], ["phone", 375, 812]];
const MODES = ["light", "dark"];

// Also runs in the page: what the shared audit does not look for.
const LAYOUT = String.raw`(() => {
  const findings = [];
  const wide = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  if (wide > 1) {
    const culprits = [...document.querySelectorAll("body *")].filter((el) => {
      const box = el.getBoundingClientRect();
      return box.right > document.documentElement.clientWidth + 1 && !el.closest(".table-wrap, pre, .visually-hidden, .skip");
    }).slice(0, 3).map((el) => el.tagName.toLowerCase() + (el.className ? "." + String(el.className).split(" ").join(".") : ""));
    findings.push({ rule: "wider-than-screen", detail: wide + "px too wide: " + culprits.join(", ") });
  }
  for (const img of document.querySelectorAll("img")) {
    if (getComputedStyle(img).display !== "none" && img.complete && !img.naturalWidth) findings.push({ rule: "picture-missing", detail: img.getAttribute("src") });
  }
  return findings;
})()`;

const out = mkdtempSync(join(tmpdir(), "riskwren-site-"));
const result = build(out);
if (result.problems.length) {
  console.error(`Broken links:\n  ${result.problems.join("\n  ")}`);
  rmSync(out, { recursive: true, force: true });
  process.exit(1);
}

const server = createServer((request, response) => {
  const path = normalize(decodeURIComponent(new URL(request.url, "http://x").pathname)).replace(/^[/\\]+/, "") || "index.html";
  const file = resolve(out, path);
  try {
    if (!file.startsWith(out)) throw new Error("outside");
    response.writeHead(200, { "content-type": TYPES[extname(file)] ?? "application/octet-stream" }).end(readFileSync(file));
  } catch {
    response.writeHead(404).end("Not found");
  }
});
await new Promise((ready) => server.listen(0, "127.0.0.1", ready));
const base = `http://127.0.0.1:${server.address().port}/`;

const only = process.argv.slice(2);
const pages = MENU.flatMap(([, items]) => items.map(([name]) => name)).filter((name) => !only.length || only.some((word) => name.includes(word)));
const shots = process.env.SHOTS ? resolve(process.env.SHOTS) : null;
if (shots) mkdirSync(shots, { recursive: true });
const page = await openBrowser();
let total = 0;
try {
  for (const name of pages) {
    const found = new Set();
    for (const [size, width, height] of SIZES) {
      await page.size(width, height);
      for (const mode of MODES) {
        await page.scheme(mode);
        await page.goto(`${base}${name}.html`);
        await page.settled();
        // Pictures load as they are scrolled to; the checks want them all.
        await page.evaluate(`(async () => { for (const img of document.images) img.loading = "eager"; await Promise.all([...document.images].filter((i) => getComputedStyle(i).display !== "none" && !i.complete).map((i) => new Promise((done) => { i.onload = i.onerror = done; }))); })()`);
        for (const finding of [...await page.evaluate(AUDIT), ...await page.evaluate(LAYOUT)]) {
          const where = finding.rule === "contrast" ? ` [${mode}]` : finding.rule === "wider-than-screen" || finding.rule === "target-size" ? ` [${size}]` : "";
          found.add(`${finding.rule}: ${finding.detail}${where}`);
        }
        if (shots) await page.screenshot(join(shots, `${name}-${size}-${mode}.webp`), { fullPage: size === "phone", scale: 0.5 });
      }
    }
    total += found.size;
    console.log(`${found.size ? "✗" : "✓"} ${name}`);
    for (const line of [...found].slice(0, 40)) console.log(`    ${line}`);
    if (found.size > 40) console.log(`    … and ${found.size - 40} more`);
  }
} catch (error) {
  console.error(`\nThe audit stopped: ${error.message}`);
  total += 1;
} finally {
  await page.close();
  server.close();
  rmSync(out, { recursive: true, force: true });
}
console.log(total ? `\n${total} findings.` : `\nNo findings in ${pages.length} pages, ${SIZES.length} widths, ${MODES.length} modes.`);
process.exit(total ? 1 : 0);
