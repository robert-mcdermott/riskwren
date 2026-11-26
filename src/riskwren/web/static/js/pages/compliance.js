// The compliance dashboard: how ready each scope is against what it is held to, and what
// stands in the way. Every figure opens the records behind it.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { unitOptions, units } from "../core/lookups.js";
import { query } from "../core/router.js";
import { progress } from "./assessments.js";
import { bars, listHref, segments, sizeBars, statTile } from "../components/charts.js";
import { issueDue, severityPill } from "../components/issue.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { filterSelect } from "./records.js";

// Readiness, strongest first: a word and the tone of its part of the bar.
const READY = [["verified", "verified", "ok"], ["in_place", "in place", "info"], ["excepted", "excepted", "excepted"], ["planned", "planned", "warn"],
  ["gap", "with no control", "gap"], ["failing", "failing", "danger"]];
const AGES = { "0-30": "Under a month", "31-90": "1 to 3 months", "91-180": "3 to 6 months", "181+": "Over 6 months" };
const SOURCE = { test: "A test of a control", gap: "A gap", security_test: "Security testing", audit: "An audit", incident: "An incident", review: "A review", observation: "Somebody noticing" };

/** The issues list as these filters make it. "Not yet closed" is that page's own default. */
function issuesHref(filters) {
  const { status, ...rest } = filters;
  return listHref("/issues", status === "live" ? rest : filters);
}

function readiness(rows, unitIndex) {
  if (!rows.length) {
    return emptyState({ iconName: "scope", title: "No scope is held to a framework yet",
      text: "A scope is a boundary that must meet a framework: the clinical systems, a data enclave, central computing. Add one, hold it to a framework, and its readiness appears here." });
  }
  const link = (row, state) => `/scopes/${row.scope.ref}?tab=requirements&framework=${encodeURIComponent(row.framework.key)}${state ? `&state=${state}` : ""}`;
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Scope"), h("th", { scope: "col" }, "Held to"), h("th", { scope: "col", class: "readiness-col" }, "Readiness"),
      h("th", { scope: "col", class: "numeric" }, "Ready"), h("th", { scope: "col", class: "numeric" }, "Open issues"))),
    h("tbody", {}, rows.map((row) => {
      const said = READY.filter(([key]) => row.counts[key]);
      return h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/scopes/${row.scope.ref}` }, row.scope.name),
          h("div", { class: "cell-sub" }, [row.scope.ref, unitIndex.byId.get(row.org_unit_id)?.name].filter(Boolean).join(" · "))),
        h("td", {}, h("a", { href: link(row) }, row.framework.title), h("div", { class: "cell-sub" }, `${plural(row.applicable, "requirement")} apply`)),
        h("td", {},
          segments(READY.map(([key, text, tone]) => ({ label: text, value: row.counts[key], tone })),
            { label: `${row.scope.name} against ${row.framework.title}: ${said.map(([key, text]) => `${row.counts[key]} ${text}`).join(", ")}`, legend: false }),
          h("div", { class: "cell-sub readiness-said" }, said.map(([key, text], index) => [index ? ", " : "", h("a", { href: link(row, key) }, `${row.counts[key]} ${text}`)]))),
        h("td", { class: "numeric nowrap" }, row.share == null ? h("span", { class: "subtle" }, "Nothing applies") : [h("strong", {}, `${row.share}%`), h("div", { class: "cell-sub" }, `${row.ready} of ${row.applicable}`)]),
        h("td", { class: "numeric" }, row.issues ? h("a", { href: `/scopes/${row.scope.ref}?tab=plan` }, String(row.issues)) : h("span", { class: "subtle" }, "None")));
    }))));
}

function aging(board) {
  const rows = board.issues.by_severity;
  if (!rows.some((row) => row.total.count)) return h("p", { class: "muted" }, "No issue is open.");
  const cell = (figure, tone = "") => h("td", { class: "numeric" }, figure.count ? h("a", { class: tone, href: issuesHref(figure.filters) }, String(figure.count)) : h("span", { class: "subtle" }, "0"));
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("caption", { class: "sr-only" }, "Open issues by severity and by how long ago they were raised"),
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Severity"), board.ages.map((key) => h("th", { scope: "col", class: "numeric" }, AGES[key] ?? key)),
      h("th", { scope: "col", class: "numeric" }, "Open"), h("th", { scope: "col", class: "numeric" }, "Overdue"))),
    h("tbody", {}, rows.map((row) => h("tr", {},
      h("th", { scope: "row" }, severityPill(row.key, { [row.key]: row.label })),
      row.ages.map((figure) => cell(figure)), cell(row.total), cell(row.overdue, "overdue"))))));
}

export function complianceDashboard(main) {
  return show(main, {
    title: "Compliance",
    load: async () => {
      const [board, unitIndex] = await Promise.all([get("/api/v1/compliance", Object.fromEntries(query()), { fresh: true }), units()]);
      return { board: board.data, units: unitIndex };
    },
    view: (data) => {
      const { board } = data;
      const t = board.totals;
      const unitName = board.unit ? data.units.byId.get(board.unit)?.name : null;
      const evidence = Object.fromEntries(board.evidence.map((figure) => [figure.key, figure]));
      const exceptions = Object.fromEntries(board.exceptions.map((figure) => [figure.key, figure]));
      const tested = Object.fromEntries(board.controls.by_test.map((figure) => [figure.key, figure]));
      const tiles = h("div", { class: "tiles" },
        statTile({ value: t.controls_failing.count, label: "Controls failing a test", href: listHref("/controls", t.controls_failing.filters), tone: "danger" }),
        statTile({ value: t.issues_open.count, label: "Open issues", href: issuesHref(t.issues_open.filters) }),
        statTile({ value: t.issues_overdue.count, label: "Issues overdue", href: issuesHref(t.issues_overdue.filters), tone: "danger" }),
        statTile({ value: t.closures_waiting.count, label: "Closures to confirm", href: issuesHref(t.closures_waiting.filters), tone: "warn" }),
        statTile({ value: t.evidence_stale.count, label: "Evidence no longer counting", href: listHref("/evidence", t.evidence_stale.filters), tone: "warn" }),
        statTile({ value: t.exceptions_expiring.count, label: "Exceptions ending within a month", href: listHref("/exceptions", t.exceptions_expiring.filters), tone: "warn" }));
      const overdue = board.worst_issues.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Issue"), h("th", { scope: "col" }, "Severity"), h("th", { scope: "col" }, "Was due"))),
        h("tbody", {}, board.worst_issues.map((issue) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/issues/${issue.ref}` }, issue.name),
            h("div", { class: "cell-sub" }, [issue.ref, data.units.byId.get(issue.org_unit_id)?.name, issue.owners[0]?.name].filter(Boolean).join(" · "))),
          h("td", {}, severityPill(issue.severity)), h("td", { class: "nowrap" }, issueDue(issue)))))))
        : h("p", { class: "muted" }, "No open issue is past its date.");
      const totals = READY.filter(([key]) => board.requirements[key]);
      return sizeBars(h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Compliance",
          lede: unitName ? `Readiness, issues, evidence, and exceptions for ${unitName} and everything beneath it.` : "How ready each scope is against what it is held to, and what stands in the way, for everything you may see.",
          actions: filterSelect("unit", unitOptions(data.units.tree, { blank: "The whole organization" }), "Unit") }),
        tiles,
        card({ title: "Readiness by scope", flush: board.readiness.length > 0, actions: h("a", { href: "/scopes" }, "All scopes") },
          board.readiness.length ? h("div", { class: "card-pad" },
            segments(READY.map(([key, text, tone]) => ({ label: text, value: board.requirements[key], tone })),
              { label: `Every scope together: ${totals.map(([key, text]) => `${board.requirements[key]} ${text}`).join(", ")}` }),
            h("p", { class: "subtle" }, "Each requirement in each scope, counted once per scope. Ready means in place or verified: verified has been tested and found effective, with evidence that still counts.")) : null,
          readiness(board.readiness, data.units)),
        h("div", { class: "grid-2" },
          card({ title: "Open issues, by severity and age", flush: true, actions: h("a", { href: issuesHref(t.issues_open.filters) }, `All ${t.issues_open.count}`) }, aging(board)),
          card({ title: "Longest overdue", flush: board.worst_issues.length > 0, actions: h("a", { href: issuesHref(t.issues_overdue.filters) }, "All overdue") }, overdue)),
        h("div", { class: "grid-2" },
          card({ title: "What the controls' ratings rest on", actions: h("a", { href: listHref("/controls", board.controls.total.filters) }, `All ${board.controls.total.count}`) },
            bars([{ label: "Tested, and effective", value: tested.effective.count, href: listHref("/controls", tested.effective.filters) },
              { label: "Tested, and found wanting", value: tested.failing.count, href: listHref("/controls", tested.failing.filters) },
              { label: "No test that still holds", value: tested.none.count, href: listHref("/controls", tested.none.filters) }]),
            h("p", { class: "subtle" }, "A test holds for as long as a rating does. A control with none is known only by someone's judgment, or not at all.")),
          card({ title: "What found the open issues" }, bars(board.issues.by_source.map((figure) => ({ label: SOURCE[figure.key] ?? figure.label, value: figure.count, href: issuesHref(figure.filters) })),
            { empty: "No issue is open." }))),
        h("div", { class: "grid-2" },
          card({ title: "Evidence" },
            bars([{ label: "Still counts", value: evidence.current.count, href: listHref("/evidence", evidence.current.filters), part: evidence.expiring.count, partLabel: "ending within a month" },
              { label: "No longer counts", value: evidence.stale.count, href: listHref("/evidence", evidence.stale.filters) }], { empty: "No evidence has been collected yet." }),
            h("p", { class: "subtle" }, "Evidence past its date stays on the record and stops counting. A requirement is verified only while evidence for its controls still counts.")),
          card({ title: "Exceptions" },
            bars([{ label: "Waiting to be decided", value: exceptions.requested.count, href: listHref("/exceptions", exceptions.requested.filters) },
              { label: "In force", value: exceptions.in_force.count, href: listHref("/exceptions", exceptions.in_force.filters), part: exceptions.expiring.count, partLabel: "ending within a month" },
              { label: "Ended", value: exceptions.expired.count, href: listHref("/exceptions", exceptions.expired.filters) }], { empty: "No exception has been asked for." }),
            h("p", { class: "subtle" }, "When an exception ends, what it covered goes back to the state underneath without anyone acting."))),
        card({ title: "Assessments in progress", flush: board.assessments.length > 0, actions: h("a", { href: "/assessments" }, "All assessments") },
          board.assessments.length ? h("div", {}, board.assessments.map((item) => h("div", { class: "list-row list-row-wide" },
            h("div", { class: "grow" }, h("a", { class: "cell-main", href: `/assessments/${item.ref}` }, item.name),
              h("div", { class: "cell-sub" }, [item.ref, item.scope?.name, item.lead?.name ? `led by ${item.lead.name}` : null, item.failing ? `${item.failing} failing` : null].filter(Boolean).join(" · "))),
            h("div", { class: "assessment-progress" }, progress(item)))))
            : h("p", { class: "muted" }, t.results_waiting.count ? "" : "No assessment is in progress."))));
    },
  });
}
