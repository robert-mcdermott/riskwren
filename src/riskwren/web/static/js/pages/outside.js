// The page a person outside the organization sees when they open the link an auditor gave
// them: one reported engagement or one scope, read-only. The link's token is after "#",
// which the browser never sends to a server, and goes back in a header of its own. Every
// time the page is opened, the history records who looked.

import { h } from "../core/dom.js";
import { date } from "../core/format.js";
import { brand } from "../components/shell.js";
import { alert, card, pill } from "../components/ui.js";
import { setTitle } from "./page.js";

const HEADER = "X-RiskWren-Access";
const STATES = { verified: "Verified", in_place: "In place", failing: "Failing", planned: "Planned", gap: "Gap", excepted: "Excepted", excluded: "Not applicable" };

function frame(meta, ...children) {
  return h("div", { class: "respond" },
    h("header", { class: "respond-top" }, h("div", { class: "sign-in-brand" }, brand(meta))),
    h("main", { class: "respond-main outside-main", id: "main" }, children));
}

function table(caption, head, rows) {
  return h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("caption", { class: "sr-only" }, caption),
    h("thead", {}, h("tr", {}, head.map((label) => h("th", { scope: "col" }, label)))),
    h("tbody", {}, rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, cell ?? "")))))));
}

function engagementView(data) {
  const e = data.engagement;
  return [
    h("h1", { tabindex: "-1" }, e.name),
    h("p", { class: "muted" }, `${e.entity.kind_label}: ${e.entity.name}. Reported ${date(e.reported_on)}.`),
    e.report ? card({ title: `Report: ${e.report.opinion_label}` }, h("p", {}, e.report.summary)) : null,
    e.scope_note ? card({ title: "What it covered" }, h("p", {}, e.scope_note)) : null,
    card({ title: "Team" }, h("p", {}, e.team.map((each) => `${each.name}${each.role === "lead" ? " (lead)" : ""}`).join(", "))),
    h("h2", {}, "Program of work"),
    e.workpapers.map((paper) => card({ title: `${paper.sequence}. ${paper.title}`, actions: paper.signed_off_by ? pill(`Signed off by ${paper.signed_off_by}`, "ok") : null },
      h("div", { class: "stack" },
        paper.procedure ? h("p", { class: "muted" }, paper.procedure) : null,
        paper.done ? h("p", {}, h("strong", {}, "Done: "), paper.done) : null,
        paper.found ? h("p", {}, h("strong", {}, "Found: "), paper.found) : null,
        paper.evidence.length ? h("p", {}, `Evidence: ${paper.evidence.join(", ")}`) : null,
        paper.prepared_by ? h("p", { class: "subtle" }, `Prepared by ${paper.prepared_by} on ${date(paper.prepared_at)}.`) : null))),
    e.findings.length ? card({ title: "Findings", flush: true }, table("Findings", ["Finding", "Severity", "Due", "Where it stands"],
      e.findings.map((f) => [`${f.ref} ${f.name}`, f.severity, date(f.due_on), f.status]))) : null,
  ];
}

function scopeView(data) {
  return [
    h("h1", { tabindex: "-1" }, data.scope.name),
    data.scope.summary ? h("p", {}, data.scope.summary) : null,
    data.scope.boundary ? card({ title: "Its boundary" }, h("p", {}, data.scope.boundary)) : null,
    data.frameworks.map((fw) => card({ title: `${fw.title}: ${fw.applicable} requirements apply`, flush: true },
      table(fw.title, ["Requirement", "Where it stands", "Answered by"], fw.requirements.map((r) =>
        [`${r.code} ${r.title ?? ""}`, STATES[r.state] ?? r.state, r.state === "excluded" ? r.reason : r.controls.join(", ")])))),
    card({ title: "How each control is done here", flush: true }, table("Controls", ["Control", "Status", "Responsibility", "How"],
      data.controls.map((c) => [`${c.ref} ${c.name}`, c.status, c.responsibility, c.statement]))),
    card({ title: "Evidence", flush: true }, table("Evidence", ["Item", "Collected", "Holds until", "State"],
      data.evidence.map((e) => [`${e.ref} ${e.name}`, e.collected_on ? date(e.collected_on) : "", e.valid_until ? date(e.valid_until) : "", e.state]))),
    card({ title: "Plan of action", flush: data.plan_of_action.length > 0 }, data.plan_of_action.length
      ? table("Plan of action", ["Issue", "Severity", "Due", "Status"], data.plan_of_action.map((i) => [`${i.ref} ${i.name}`, i.severity, date(i.due_on), i.status]))
      : h("p", { class: "muted" }, "No open issue bears on it.")),
  ];
}

export async function outsidePage(root, meta) {
  const token = window.location.hash.slice(1);
  if (token) history.replaceState(null, "", "/outside");
  const kept = token || sessionStorage.getItem("riskwren.outside") || "";
  if (token) sessionStorage.setItem("riskwren.outside", token);
  const stop = (text) => {
    setTitle("This link");
    root.replaceChildren(frame(meta, h("h1", { tabindex: "-1" }, "This link cannot be used"), h("p", {}, text)));
    root.querySelector("h1").focus();
  };
  if (!kept) {
    stop("The address is missing the part that opens what you were given. Open the link you were sent, or ask whoever sent it for a new one.");
    return;
  }
  const response = await fetch("/api/v1/outside", { credentials: "omit", cache: "no-store", headers: { Accept: "application/json", [HEADER]: kept } });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    stop(payload?.detail || "This link cannot be used.");
    return;
  }
  const data = payload.data;
  setTitle(data.about.kind === "engagement" ? data.engagement.name : data.scope.name);
  root.replaceChildren(frame(meta,
    alert("info", h("strong", {}, `For ${data.about.name}, ${data.about.organization}. `),
      `Read-only, given by ${data.about.granted_by}, until ${date(data.about.expires_at)}. Each time this page is opened, it is recorded.`),
    data.about.kind === "engagement" ? engagementView(data) : scopeView(data)));
  root.querySelector("h1")?.focus();
}
