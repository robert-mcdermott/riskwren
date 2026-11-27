#!/usr/bin/env node
// Take the documentation's screenshots from a fresh demo organization, by day and after dark,
// each as the sample person its scene names (scripts/lib/scenes.mjs).
//
//   node scripts/capture.mjs                 the pictures the guides and the home page use,
//                                            into docs/img
//   node scripts/capture.mjs risk home       only scenes whose name contains a word given
//   node scripts/capture.mjs --all           every scene
//   OUT=/some/dir node scripts/capture.mjs   somewhere else
//
// A guide uses a picture by naming it: ![What it shows](img/NAME-light.webp). The dark
// version sits beside it and the site shows whichever suits the reader's theme.
// Screenshots are never taken from a real installation.

import { mkdirSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";
import { SCENES } from "./lib/scenes.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(process.env.OUT ?? join(root, "docs", "img"));

/** The names of the pictures the guides and the home page use. */
export function used() {
  const names = new Set();
  const docs = join(root, "docs");
  for (const file of readdirSync(docs).filter((name) => name.endsWith(".md"))) {
    for (const [, name] of readFileSync(join(docs, file), "utf8").matchAll(/\]\(img\/([\w-]+)-light\.webp/g)) names.add(name);
  }
  for (const [, name] of readFileSync(join(root, "scripts", "site", "pages", "index.html"), "utf8").matchAll(/\{\{shot:([\w-]+)\|/g)) names.add(name);
  return names;
}

const args = process.argv.slice(2);
const words = args.filter((arg) => !arg.startsWith("--"));
const wanted = used();
const scenes = SCENES.filter((scene) => (args.includes("--all") ? true
  : words.length ? words.some((word) => scene.name.includes(word)) : wanted.has(scene.name)));
if (!args.includes("--all") && !words.length) {
  const known = new Set(SCENES.map((scene) => scene.name));
  const unknown = [...wanted].filter((name) => !known.has(name));
  if (unknown.length) {
    console.error(`No scene is named: ${unknown.join(", ")}`);
    process.exit(1);
  }
}
mkdirSync(out, { recursive: true });

const demo = await startDemo();
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
      await page.screenshot(join(out, `${scene.name}-${mode}.webp`));
    }
    console.log(`✓ ${scene.name}`);
  }
} finally {
  await page.close();
  demo.stop();
}
console.log(`\n${scenes.length * 2} screenshots in ${out}`);
