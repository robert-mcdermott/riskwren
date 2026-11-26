// How dates are written for people.

import assert from "node:assert/strict";
import { test } from "node:test";

import { date, plural } from "../../src/riskwren/web/static/js/core/format.js";

test("a day with no time is that day in every time zone", () => {
  // The process runs west of Greenwich (see the test that starts it), where reading the
  // day as midnight UTC would show the day before.
  assert.equal(new Date().getTimezoneOffset() > 0, true, "run with TZ set west of UTC");
  assert.match(date("2026-11-20"), /20/);
  assert.match(date("2027-03-31"), /31/);
  assert.match(date("2027-01-01"), /2027/);
});

test("a moment is shown in the reader's own time", () => {
  assert.match(date("2026-11-20T02:00:00Z"), /19/);
  assert.equal(date(null), "");
});

test("counts are written with their noun", () => {
  assert.equal(plural(1, "risk"), "1 risk");
  assert.equal(plural(3, "risk"), "3 risks");
});
