// How records, their standing, and what they are worth to the organization are shown everywhere.

import { h, icon } from "../core/dom.js";
import { titleCase } from "../core/format.js";
import { label } from "../core/lookups.js";
import { pill } from "./ui.js";

// Each kind of record: where it lives, what it is called, and what its list says about it.
export const TYPES = {
  process: { prefix: "PRC", path: "processes", label: "Process", plural: "Processes", noun: "process", nouns: "processes",
    article: "a process", iconName: "process", section: "Inventory", kinds: "process_kinds",
    lede: "What the organization does and depends on: its research, clinical, and administrative work." },
  system: { prefix: "SYS", path: "systems", label: "System", plural: "Systems", noun: "system", nouns: "systems",
    article: "a system", iconName: "system", section: "Inventory", kinds: "system_kinds",
    lede: "The applications, platforms, instruments, devices, and infrastructure that work relies on." },
  third_party: { prefix: "TP", path: "third-parties", label: "Third party", plural: "Third parties", noun: "third party", nouns: "third parties",
    article: "a third party", iconName: "third_party", section: "Inventory", kinds: "third_party_kinds",
    lede: "The outside organizations the work depends on or shares with: suppliers, partners, sponsors." },
};

const BY_PREFIX = Object.fromEntries(Object.entries(TYPES).map(([key, type]) => [type.prefix, key]));

/** Another module adds its own kinds of record (risks, controls) to the ones every page knows. */
export function registerType(key, type) {
  TYPES[key] = type;
  BY_PREFIX[type.prefix] = key;
}

export function typeOfRef(ref) {
  return BY_PREFIX[String(ref).split("-")[0]];
}

export function hrefOf(ref) {
  const type = TYPES[typeOfRef(ref)];
  return type ? `/${type.path}/${ref}` : "/";
}

/** A record as a link: its type's icon, its name, and its reference. */
export function recordChip(record, { link = true } = {}) {
  const type = record.type ?? typeOfRef(record.ref);
  const inner = [icon(TYPES[type]?.iconName ?? "dot"), h("span", { class: "truncate" }, record.name), h("span", { class: "ref" }, record.ref)];
  return link
    ? h("a", { class: "chip", "data-record": type, href: hrefOf(record.ref) }, inner)
    : h("span", { class: "chip", "data-record": type }, inner);
}

// Status: a word, a mark, and a tone. Never a color alone.
const STATUS = {
  active: ["Active", "ok", "●"],
  retired: ["Retired", "", "○"],
};

export function statusLabel(status) {
  return STATUS[status]?.[0] ?? titleCase(status);
}

export function statusPill(status) {
  const [text, tone, mark] = STATUS[status] ?? [titleCase(status), "", "○"];
  const node = pill("", tone);
  node.append(h("span", { "aria-hidden": "true" }, mark), text);
  return node;
}

export function statusOptions(keys, blank) {
  return [["", blank], ...keys.map((key) => [key, statusLabel(key)])];
}

/**
 * How much the organization depends on something: a quiet meter of filled squares and the
 * word. It is not a rating and never borrows the rating ramp or the colors of standing.
 */
export function criticality(vocab, key) {
  const levels = (vocab.criticalities ?? []).map((item) => item.key);
  const position = levels.indexOf(key) + 1;
  if (!position) return h("span", { class: "subtle" }, "Not set");
  return h("span", { class: "meter", title: (vocab.criticalities.find((item) => item.key === key) ?? {}).description ?? "" },
    h("span", { class: "meter-marks", "aria-hidden": "true" }, levels.map((_, index) => h("i", { "data-on": String(index < position) }))),
    label(vocab, "criticalities", key));
}
