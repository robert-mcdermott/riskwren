#!/usr/bin/env node
// Take the documentation's screenshots from a fresh demo organization: every scene in
// scripts/lib/scenes.mjs, by day and after dark, as the sample person the scene names.
//
//   node scripts/capture.mjs                 every scene, into docs/img
//   node scripts/capture.mjs risk home       only scenes whose name contains a word given
//   OUT=/some/dir node scripts/capture.mjs   somewhere else
//
// Screenshots are never taken from a real installation.

import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";
import { SCENES } from "./lib/scenes.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(process.env.OUT ?? join(root, "docs", "img"));
const only = process.argv.slice(2);
const scenes = SCENES.filter((scene) => !only.length || only.some((word) => scene.name.includes(word)));
mkdirSync(out, { recursive: true });

const demo = await startDemo({ port: 8028 });
const page = await openBrowser();
try {
  let who = null;
  for (const scene of scenes) {
    const [width, height] = scene.size ?? [1360, 860];
    await page.size(width, height);
    if (scene.as !== who) {
      await signInAs(page, demo.base, scene.as);
      who = scene.as;
    }
    for (const mode of ["light", "dark"]) {
      await page.scheme(mode);
      const path = typeof scene.path === "function" ? await scene.path(page) : scene.path;
      await page.goto(demo.base + path);
      await page.evaluate(`localStorage.removeItem("riskwren.palette"); localStorage.removeItem("riskwren.mode")`);
      await page.settled();
      if (scene.step) {
        await page.evaluate(scene.step);
        await new Promise((done) => setTimeout(done, 500));
      }
      await page.screenshot(join(out, `${scene.name}-${mode}.png`));
    }
    console.log(`✓ ${scene.name}`);
  }
} finally {
  await page.close();
  demo.stop();
}
console.log(`\n${scenes.length * 2} screenshots in ${out}`);
