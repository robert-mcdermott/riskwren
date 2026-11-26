// The browser must show and hide the same questions as the server, on every shared case.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { showing } from "../../src/riskwren/web/static/js/core/questionnaire.js";

const { documents, cases } = JSON.parse(readFileSync(new URL("../fixtures/questionnaire-cases.json", import.meta.url), "utf8"));

for (const { name, questionnaire, answers, keys, kept } of cases) {
  test(name, () => {
    const found = showing(documents[questionnaire], answers);
    assert.deepEqual(found.keys, keys);
    assert.deepEqual(found.kept, kept);
  });
}
