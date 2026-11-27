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
    article: "a third party", iconName: "third_party", section: "Third parties", kinds: "third_party_kinds",
    lede: "The outside organizations the work depends on or shares with: suppliers, partners, sponsors." },
  service: { prefix: "SVC", path: "services", label: "Service", plural: "Services", noun: "service", nouns: "services",
    article: "a service", iconName: "service", section: "Third parties", kinds: "service_kinds",
    lede: "What each third party provides: the hosted application, the maintenance contract, the tests sent out. A service is what reaches systems and handles information." },
  information: { prefix: "INF", path: "information", label: "Information asset", plural: "Information", noun: "information asset", nouns: "information assets",
    article: "an information asset", iconName: "information", section: "Inventory", kinds: "information_kinds",
    lede: "The bodies of information the organization holds: what each is, where it is kept, and who it is shared with. A record describes the information and never contains it." },
  scope: { prefix: "SCP", path: "scopes", label: "Scope", plural: "Scopes", noun: "scope", nouns: "scopes",
    article: "a scope", iconName: "scope", section: "Compliance",
    lede: "A scope is a boundary that must meet one or more frameworks: the clinical systems, a data enclave, the whole organization. Each says what is inside it, which requirements apply, and how each control is done there." },
  evidence: { prefix: "EV", path: "evidence", label: "Evidence", plural: "Evidence", noun: "item", nouns: "items",
    article: "evidence", iconName: "evidence", section: "Compliance",
    lede: "What shows that a control is done: a file, a link, a note of what was seen, or an attestation. Each is collected once, attached to whatever it supports, and counts until the date it holds to." },
  assessment: { prefix: "ASM", path: "assessments", label: "Assessment", plural: "Assessments", noun: "assessment", nouns: "assessments",
    article: "an assessment", iconName: "assessment", section: "Compliance",
    lede: "An assessment tests the controls a scope does itself. Each result is recorded by someone who does not own the control and confirmed by a second person; it then counts everywhere the control is relied on." },
  issue: { prefix: "ISS", path: "issues", label: "Issue", plural: "Issues", noun: "issue", nouns: "issues",
    article: "an issue", iconName: "issue", section: "Compliance",
    lede: "Something found to be wrong that must be put right: a failed test, a gap, a finding, or what somebody noticed. Its date follows from its severity, and it closes when someone who does not own it has confirmed that it is fixed." },
  exception: { prefix: "EXC", path: "exceptions", label: "Exception", plural: "Exceptions", noun: "exception", nouns: "exceptions",
    article: "an exception", iconName: "exception", section: "Compliance",
    lede: "An approved departure from a control, a requirement, or a document, for a time, with what makes up for it. It is decided by someone who did not ask for it, and when it ends the state underneath returns." },
  indicator: { prefix: "IND", path: "indicators", label: "Indicator", plural: "Indicators", noun: "indicator", nouns: "indicators",
    article: "an indicator", iconName: "chart", section: "Risks",
    lede: "A number read on a schedule that warns of a risk before it happens: with a level to worry at, and a limit." },
  document: { prefix: "POL", path: "documents", label: "Document", plural: "Documents", noun: "document", nouns: "documents",
    article: "a document", iconName: "document", section: "Policies",
    lede: "A policy, standard, procedure, or guideline. Each version is approved by named people before it is published, and is never changed after." },
  objective: { prefix: "OBJ", path: "objectives", label: "Objective", plural: "Objectives", noun: "objective", nouns: "objectives",
    article: "an objective", iconName: "objective", section: "Risks",
    lede: "What the organization means to achieve. A risk names the objectives it threatens, and each objective shows its risks." },
  committee_session: { prefix: "SES", path: "sessions", label: "Session", plural: "Sessions", noun: "session", nouns: "sessions",
    article: "a session", iconName: "session", section: "Reports",
    lede: "A meeting of a risk or compliance committee: its agenda, drawn from the register, the decision taken on each item, and the minutes." },
  third_party_review: { prefix: "DDR", path: "reviews", label: "Review", plural: "Due diligence", noun: "review", nouns: "reviews",
    article: "a review", iconName: "file", section: "Third parties",
    lede: "Questionnaires sent to third parties through a link, the concerns among their answers, and what was concluded." },
  scenario: { prefix: "SCN", path: "scenarios", label: "Scenario", plural: "Scenarios", noun: "scenario", nouns: "scenarios",
    article: "a scenario", iconName: "risk", section: "Risks",
    lede: "What might happen, told on purpose: what it assumes, the risks and processes it would touch, and what was concluded." },
  leadership_report: { prefix: "LDR", path: "leadership-reports", label: "Leadership report", plural: "Leadership reports", noun: "report", nouns: "reports",
    article: "a leadership report", iconName: "document", section: "Reports",
    lede: "A report given to leadership once, frozen with a fingerprint, that reopens exactly as it was issued." },
  agreement: { prefix: "AGR", path: "agreements", label: "Agreement", plural: "Agreements", noun: "agreement", nouns: "agreements",
    article: "an agreement", iconName: "agreement", section: "Compliance",
    lede: "What the organization has promised others: who it is with, when it runs, what it covers, and the requirements it imposes." },
  risk_analysis: { prefix: "RAN", path: "risk-analyses", label: "Risk analysis", plural: "Risk analyses", noun: "risk analysis", nouns: "risk analyses",
    article: "a risk analysis", iconName: "scope", section: "Risks",
    lede: "A structured look at what is in a scope: each thing against each threat, with what was decided. It raises risks, refreshes the ones already there, and leaves a report of what was considered." },
  risk: { prefix: "RSK", path: "risks", label: "Risk", plural: "Risks", noun: "risk", nouns: "risks",
    article: "a risk", iconName: "risk", section: "Risks",
    lede: "What could go wrong, how much is at stake, and whether each risk is in order." },
  control: { prefix: "CTL", path: "controls", label: "Control", plural: "Controls", noun: "control", nouns: "controls",
    article: "a control", iconName: "control", section: "Controls", kinds: "control_kinds",
    lede: "What the organization does about its risks, each described once, with what is known of how well it works." },
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
