// The browser's condition evaluator must agree with the server's on every shared case.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { evaluate } from "../../src/riskwren/web/static/js/core/conditions.js";

const cases = JSON.parse(readFileSync(new URL("../fixtures/conditions-cases.json", import.meta.url), "utf8"));

for (const { name, condition, context, expect } of cases) {
  test(name, () => {
    assert.equal(evaluate(condition, context), expect);
  });
}
