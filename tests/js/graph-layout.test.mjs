import assert from "node:assert/strict";
import { test } from "node:test";

import { layout, VIEW } from "../../src/riskwren/web/static/js/core/graph-layout.js";

const record = (ref, type = "system") => ({ ref, name: `Record ${ref}`, type });
const graph = (groups) => ({ center: record("SYS-0001"), groups });

test("the record is in the middle with a neighbor for each connection", () => {
  const found = layout(graph([{ key: "relies_on:out", label: "Relies on", records: [record("SYS-0002"), record("TP-0001", "third_party")] },
    { key: "risks", label: "Risks to it", records: [record("RSK-0001", "risk")] }]));
  assert.equal(found.nodes.length, 4);
  assert.deepEqual([found.nodes[0].x, found.nodes[0].y, found.nodes[0].ring], [VIEW.width / 2, VIEW.height / 2, 0]);
  assert.deepEqual(found.edges.map((edge) => edge.to), ["relies_on:out/SYS-0002", "relies_on:out/TP-0001", "risks/RSK-0001"]);
  assert.deepEqual(found.labels.map((label) => label.text), ["Relies on", "Risks to it"]);
});

test("everything stays inside the picture and nothing sits on anything else", () => {
  const many = (prefix, count) => Array.from({ length: count }, (_, index) => record(`${prefix}-${String(index + 1).padStart(4, "0")}`));
  const base = graph([{ key: "a", label: "A", records: many("SYS", 6) }, { key: "b", label: "B", records: many("RSK", 5) }, { key: "c", label: "C", records: many("CTL", 4) }]);
  const opened = Object.fromEntries(["SYS-0001", "SYS-0002", "RSK-0001", "CTL-0004"].map((ref) => [ref, { center: record(ref), groups: [{ key: "x", label: "X", records: many(`T${ref.slice(-1)}`.padEnd(2, "P"), 5) }] }]));
  const found = layout(base, opened);
  assert.ok(found.nodes.some((node) => node.ring === 2));
  for (const node of found.nodes) {
    assert.ok(node.x >= VIEW.node.width / 2 && node.x <= VIEW.width - VIEW.node.width / 2, `${node.id} is inside across`);
    assert.ok(node.y >= VIEW.node.height / 2 && node.y <= VIEW.height - VIEW.node.height / 2, `${node.id} is inside down`);
  }
  for (const [index, a] of found.nodes.entries()) {
    for (const b of found.nodes.slice(index + 1)) {
      const apart = Math.abs(a.x - b.x) >= VIEW.node.width || Math.abs(a.y - b.y) >= VIEW.node.height;
      assert.ok(apart, `${a.id} and ${b.id} do not overlap`);
    }
  }
});

test("what does not fit is counted, so the list beside it can say the rest", () => {
  const records = Array.from({ length: 9 }, (_, index) => record(`SYS-00${index + 10}`));
  const found = layout(graph([{ key: "supports:in", label: "Supports", records }]));
  const more = found.nodes.find((node) => node.more);
  assert.equal(more.more, 3);
  assert.equal(found.nodes.filter((node) => node.ring === 1 && node.record).length, 6);
  // With more groups than there is room for, each shows fewer, and still counts the rest.
  const groups = Array.from({ length: 8 }, (_, index) => ({ key: `g${index}`, label: `Group ${index}`, records }));
  const tight = layout(graph(groups));
  assert.ok(tight.nodes.every((node) => node.y >= VIEW.node.height / 2 && node.y <= VIEW.height - VIEW.node.height / 2));
  assert.ok(tight.nodes.filter((node) => node.more).every((node) => node.more >= 4));
});

test("an opened neighbor shows its own neighbors, and none of them twice", () => {
  const base = graph([{ key: "relies_on:out", label: "Relies on", records: [record("SYS-0002")] }]);
  const opened = { "SYS-0002": { center: record("SYS-0002"), groups: [
    { key: "supports:in", label: "Supports", records: [record("SYS-0001"), record("PRC-0001", "process")] },
    { key: "risks", label: "Risks to it", records: [record("RSK-0001", "risk"), record("PRC-0001", "process")] }] } };
  const found = layout(base, opened);
  const beyond = found.nodes.filter((node) => node.ring === 2);
  assert.deepEqual(beyond.map((node) => node.record.ref), ["PRC-0001", "RSK-0001"]);
  assert.deepEqual(beyond.map((node) => node.via), ["Supports", "Risks to it"]);
  assert.ok(found.edges.some((edge) => edge.from === "relies_on:out/SYS-0002" && edge.to.endsWith(">RSK-0001")));
});

test("a record with no connections is alone in the middle", () => {
  const found = layout(graph([]));
  assert.equal(found.nodes.length, 1);
  assert.equal(found.edges.length, 0);
});
