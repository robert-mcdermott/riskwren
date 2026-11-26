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

import { AUDIT } from "./lib/audit.mjs";
import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";
import { SCENES } from "./lib/scenes.mjs";

const PALETTES = ["wren", "slate", "garnet"];
const MODES = ["light", "dark"];

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
        if (scene.step) {
          await page.evaluate(scene.step);
          await new Promise((r) => setTimeout(r, 400));
          const missed = await page.evaluate("window.__sceneMissed || null");
          if (missed) found.set(`step: ${missed}`, true);
        }
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
