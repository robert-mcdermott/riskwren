// The browser's scoring arithmetic, held to the same cases as the server's.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import * as scoring from "../../src/riskwren/web/static/js/core/scoring.js";

const root = new URL("../../", import.meta.url);
const read = (path) => JSON.parse(readFileSync(new URL(path, root), "utf8"));
const method = read("src/riskwren/resources/packs/default-program.json").scoring_method;
const { cases } = read("tests/fixtures/scoring-cases.json");

const run = {
  rating: (args) => scoring.rating(method, ...args),
  overall_impact: (args) => scoring.overallImpact(...args),
  ramp_level: (args) => scoring.rampLevel(...args),
  position: (args) => scoring.position(method, ...args),
  exceeds: (args) => scoring.exceeds(method, ...args),
  control_state: (args, options) => scoring.controlState(...args, { stale: Boolean(options.stale) }),
  suggest: (args) => scoring.suggest(method, ...args),
};

for (const [index, item] of cases.entries()) {
  test(`${item.fn} ${item.name ?? JSON.stringify(item.args)} (${index})`, () => {
    if (item.expect && item.expect.error) {
      assert.throws(() => run[item.fn](item.args, item));
      return;
    }
    const got = run[item.fn](item.args, item);
    if (item.fn === "suggest") {
      for (const key of Object.keys(item.expect)) assert.deepEqual(got[key], item.expect[key], key);
    } else {
      assert.deepEqual(got, item.expect);
    }
  });
}

test("every case names a function this module has", () => {
  assert.deepEqual([...new Set(cases.map((item) => item.fn))].filter((name) => !run[name]), []);
});
