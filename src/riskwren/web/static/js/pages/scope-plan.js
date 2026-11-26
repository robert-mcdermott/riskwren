// A scope's plan of action: the open issues that bear on it, each with its milestones.
// Loaded when the tab is opened, or when an issue is raised from the scope.

import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { units, vocabularies } from "../core/lookups.js";
import { issueDue, issueStatus, severityPill } from "../components/issue.js";
import { card, emptyState } from "../components/ui.js";

/** Raise an issue about this scope. The form is loaded when it is first asked for. */
export async function raiseIssue(scope, more = {}) {
  const [{ editIssue }, vocab, unitIndex] = await Promise.all([import("./issues.js"), vocabularies(), units()]);
  editIssue({ about: [{ type: "scope", ref: scope.ref, name: scope.name }], unitId: scope.org_unit_id, vocab, units: unitIndex, ...more });
}

export function planTab(scope, plan) {
  const rows = plan.issues;
  const raise = button("Raise an issue", { kind: "btn-primary no-print", iconName: "plus", onclick: () => raiseIssue(scope) });
  if (!rows.length) {
    return card({}, emptyState({ iconName: "issue", title: "Nothing is open",
      text: "No open issue bears on this scope: none about the scope itself, and none about a control it uses or inherits.", action: raise }));
  }
  const said = Object.entries(plan.counts).filter(([, count]) => count).map(([key, count]) => `${count} ${(plan.severities[key] ?? key).toLowerCase()}`).join(", ");
  return h("div", { class: "stack-lg" },
    h("div", { class: "statement-head" },
      h("h2", {}, `Plan of action and milestones: ${scope.name}`),
      h("p", { class: "muted" }, `${plural(rows.length, "open issue")} that ${rows.length === 1 ? "bears" : "bear"} on this scope: ${said}. `, plan.overdue ? `${plan.overdue} overdue.` : "None overdue."),
      h("p", { class: "subtle" }, "Issues about the scope itself, and about any control it uses or inherits, most severe first. Each is put right through its actions.")),
    h("div", { class: "row no-print" }, raise, button("Print", { onclick: () => window.print() })),
    card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Weakness"), h("th", { scope: "col" }, "Severity"), h("th", { scope: "col" }, "About"), h("th", { scope: "col" }, "Who"),
        h("th", { scope: "col" }, "Milestones"), h("th", { scope: "col" }, "Due"))),
      h("tbody", {}, rows.map((issue) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/issues/${issue.ref}` }, issue.name), h("div", { class: "cell-sub" }, issue.ref, " · raised ", date(issue.created_at))),
        h("td", {}, severityPill(issue.severity, plan.severities)),
        h("td", {}, issue.subjects.records.filter((record) => record.type !== "scope").map((record) => h("div", {}, record.name)),
          issue.subjects.requirements.map((item) => h("div", { class: "requirement-code" }, item.code))),
        h("td", {}, issue.owners.length ? issue.owners.map((owner) => h("div", {}, owner.name)) : h("span", { class: "subtle" }, "Nobody")),
        h("td", {}, issue.actions.length ? h("ul", { class: "milestones" }, issue.actions.filter((action) => action.status !== "cancelled").map((action) => h("li", {},
          h("span", {}, action.title), h("span", { class: "cell-sub" }, `${action.owner.name} · ${action.status === "done" ? "done" : `due ${date(action.due_on)}`}${action.overdue ? " · overdue" : ""}`))))
          : h("span", { class: "subtle" }, "No actions yet")),
        h("td", { class: "nowrap" }, issueDue(issue), h("div", {}, issueStatus(issue))))))))));
}
