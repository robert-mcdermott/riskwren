// The small Markdown documents are written in: read into plain objects, never markup.

import assert from "node:assert/strict";
import { test } from "node:test";

import { contents, inline, parse, plainText, safeHref } from "../../src/riskwren/web/static/js/core/markdown.js";

test("headings, paragraphs, and rules are blocks", () => {
  const blocks = parse("# Purpose\n\nWe keep\nwhat we hold.\n\n---\n\n## Scope ##\nAll staff.");
  assert.deepEqual(blocks.map((block) => block.type), ["heading", "paragraph", "rule", "heading", "paragraph"]);
  assert.equal(blocks[0].id, "purpose");
  assert.equal(blocks[3].level, 2);
  assert.equal(plainText(blocks[3].inline), "Scope");
  assert.equal(plainText(blocks[1].inline), "We keep what we hold.");
});

test("headings with the same words get anchors of their own", () => {
  const blocks = parse("## Rules\n\n## Rules\n\n## Who it applies to");
  assert.deepEqual(blocks.map((block) => block.id), ["rules", "rules-2", "who-it-applies-to"]);
  assert.deepEqual(contents(blocks).map((item) => item.text), ["Rules", "Rules", "Who it applies to"]);
  const titled = parse("# Acceptable use\n\n## You may\n\n## You must not");
  assert.deepEqual(contents(titled).map((item) => [item.text, item.level]), [["You may", 1], ["You must not", 1]]);
});

test("lists keep their kind, their start, and one level of nesting", () => {
  const [bullets] = parse("- Accounts are personal.\n- Restricted data stays in approved systems:\n  - the enclave\n  - research storage\n- Report what you see.");
  assert.equal(bullets.type, "list");
  assert.equal(bullets.ordered, false);
  assert.equal(bullets.items.length, 3);
  assert.equal(bullets.items[1].children[0].items.length, 2);
  const [steps] = parse("3. Isolate the machine.\n4. Call the help desk.");
  assert.equal(steps.ordered, true);
  assert.equal(steps.start, 3);
  assert.equal(plainText(steps.items[1].inline), "Call the help desk.");
});

test("a quotation, a fence, and a table", () => {
  const blocks = parse("> Read this first.\n\n```\n**not bold**\n```\n\n| Role | Does |\n|---|---|\n| Owner | Keeps it |\n| Steward | Checks |");
  assert.deepEqual(blocks.map((block) => block.type), ["quote", "code", "table"]);
  assert.equal(blocks[1].text, "**not bold**");
  assert.equal(blocks[2].head.length, 2);
  assert.equal(plainText(blocks[2].rows[1][0]), "Steward");
});

test("inline marks, and links only where they are safe", () => {
  const nodes = inline("Use **strong** and *some* `code`, see [the guide](https://example.org/g) or [here](/documents/POL-0001).");
  assert.deepEqual(nodes.map((node) => node.type), ["text", "strong", "text", "em", "text", "code", "text", "link", "text", "link", "text"]);
  assert.equal(nodes[7].href, "https://example.org/g");
  const unsafe = inline("[click](javascript:alert(1)) and [x](//evil.example)");
  assert.equal(unsafe.some((node) => node.type === "link"), false);
  assert.equal(safeHref("mailto:security@northmere.example"), "mailto:security@northmere.example");
  assert.equal(safeHref("data:text/html,hi"), null);
});

test("words that only look like marks are left alone", () => {
  assert.deepEqual(inline("snake_case_name and 2 * 3 * 4").map((node) => node.type), ["text"]);
  assert.equal(plainText(parse("<script>alert(1)</script>")[0].inline), "<script>alert(1)</script>");
});
