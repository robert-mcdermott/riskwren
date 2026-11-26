// One list of everything owed, and the registers of treatment plans and acceptances.

import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { program as loadProgram, unitOptions, units } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { hrefOf, recordChip } from "../components/record.js";
import { rating, standingPill } from "../components/risk.js";
import { acceptanceState, actionButtons, actionStatus, dueCell } from "../components/treatment.js";
import { card, emptyState, pageHeader, pill } from "../components/ui.js";
import { exportButton } from "../components/exchange.js";
import { show } from "./page.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, pager, searchBox } from "./records.js";

function toggle(name, text) {
  const on = query().get(name) === "true";
  return h("button", { type: "button", class: `btn${on ? " btn-primary" : ""}`, "aria-pressed": String(on),
    onclick: () => setQuery({ [name]: on ? null : "true", cursor: null }) }, text);
}

function nothing(title, text) {
  return emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Clear a filter to see more.", action: button("Clear filters", { onclick: clearFilters }) }
    : { iconName: "check", title, text });
}

export function actionList(main) {
  return show(main, {
    title: "Actions",
    load: async () => {
      const [page, unitIndex] = await Promise.all([get("/api/v1/actions", { status: "open", ...Object.fromEntries(query()) }, { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data, reload) => {
      const rows = data.page.data;
      const search = searchBox("Search actions");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("status", [["open", "Not yet done"], ["done", "Done"], ["cancelled", "Cancelled"]], "Status"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        toggle("overdue", "Overdue"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Action"), h("th", { scope: "col" }, "For"), h("th", { scope: "col" }, "Owner"),
          h("th", { scope: "col" }, "Due"), h("th", { scope: "col" }, "Status"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "What you can do")))),
        h("tbody", {}, rows.map((action) => h("tr", {},
          h("td", {}, h("div", { class: "cell-main" }, action.title), h("div", { class: "cell-sub" }, [action.ref, action.plan].filter(Boolean).join(" · "))),
          h("td", {}, action.risk ? recordChip(action.risk) : action.source ? recordChip(action.source) : h("span", { class: "subtle" }, "Something you cannot see")),
          h("td", {}, action.owner.name),
          h("td", { class: "nowrap" }, dueCell(action)),
          h("td", {}, actionStatus(action)),
          h("td", { class: "actions" }, actionButtons(action, reload)))))))
        : nothing("Nothing is owed", "Actions from treatment plans and issues appear here, soonest first, each with an owner and a date.");
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: "Actions", lede: "Everything someone has to do by a date, whatever it came from.", actions: exportButton("actions", { status: "open", ...Object.fromEntries(query()) }) }),
        bar, card({ title: plural(data.page.meta.total, "action"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

export function planList(main) {
  return show(main, {
    title: "Treatment plans",
    load: async () => {
      const [plans, programData, unitIndex] = await Promise.all([
        get("/api/v1/plans", { status: "active", ...Object.fromEntries(query()) }, { fresh: true }), loadProgram(), units()]);
      return { plans: plans.data, program: programData, units: unitIndex };
    },
    view: (data) => {
      const bar = h("div", { class: "filters" },
        filterSelect("status", [["active", "Active"], ["complete", "Complete"], ["cancelled", "Cancelled"]], "Status"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"), toggle("overdue", "Overdue"), mineToggle());
      const rows = data.plans;
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Plan"), h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "Now"),
          h("th", { scope: "col" }, "Target"), h("th", { scope: "col" }, "Owner"), h("th", { scope: "col" }, "Progress"), h("th", { scope: "col" }, "Due"))),
        h("tbody", {}, rows.map((plan) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `${hrefOf(plan.risk.ref)}?tab=treatment` }, plan.objective), h("div", { class: "cell-sub" }, plan.ref)),
          h("td", {}, recordChip(plan.risk)),
          h("td", {}, rating(data.program, plan.risk.residual_rating)),
          h("td", {}, plan.target_rating ? rating(data.program, plan.target_rating) : h("span", { class: "subtle" }, "Not set")),
          h("td", {}, plan.owner.name),
          h("td", { class: "numeric nowrap" }, `${plan.progress.done} of ${plan.progress.total}`),
          h("td", { class: "nowrap" }, plan.overdue ? pill("Overdue", "danger") : null, " ", h("span", { class: plan.overdue ? "overdue" : "" }, date(plan.due_on))))))))
        : nothing("No treatment plans", "A plan is opened from a risk that is above appetite, on its Treatment tab.");
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: "Treatment plans", lede: "What is being done to bring risks down, by whom, and by when.", actions: exportButton("plans", { status: "active", ...Object.fromEntries(query()) }) }),
        bar, card({ title: plural(rows.length, "plan"), flush: true }, body));
    },
  });
}

export function acceptanceList(main) {
  return show(main, {
    title: "Acceptances",
    load: async () => {
      const [list, programData, unitIndex] = await Promise.all([
        get("/api/v1/acceptances", { state: "in_force", ...Object.fromEntries(query()) }, { fresh: true }), loadProgram(), units()]);
      return { list: list.data, program: programData, units: unitIndex };
    },
    view: (data) => {
      const bar = h("div", { class: "filters" },
        filterSelect("state", [["in_force", "In force"], ["expired", "Expired"], ["withdrawn", "Withdrawn"]], "State"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        filterSelect("expiring_within", [["", "Expiring at any time"], ["30", "Within 30 days"], ["90", "Within 90 days"]], "Expiring"),
        toggle("mine", "Given by me"));
      const rows = data.list;
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "Accepted at"), h("th", { scope: "col" }, "Now"),
          h("th", { scope: "col" }, "Accepted by"), h("th", { scope: "col" }, "Until"), h("th", { scope: "col" }, "State"))),
        h("tbody", {}, rows.map((item) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `${hrefOf(item.risk.ref)}?tab=treatment` }, item.risk.name),
            h("div", { class: "cell-sub" }, [item.risk.ref, data.units.byId.get(item.risk.org_unit_id)?.name].filter(Boolean).join(" · "))),
          h("td", {}, rating(data.program, item.rating_accepted)),
          h("td", {}, h("div", { class: "row-sm wrap" }, rating(data.program, item.risk.residual_rating), standingPill(item.risk.standing))),
          h("td", {}, item.accepted_by, h("div", { class: "cell-sub" }, date(item.accepted_at))),
          h("td", { class: "nowrap" }, date(item.expires_on)),
          h("td", {}, acceptanceState(item)))))))
        : nothing("No acceptances", "A risk above appetite is accepted on its Treatment tab, by a leader with the authority for its rating.");
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: "Acceptances", lede: "Risks above appetite that a named person has decided to live with, and until when.", actions: exportButton("acceptances", { state: "in_force", ...Object.fromEntries(query()) }) }),
        bar, card({ title: plural(rows.length, "acceptance"), flush: true }, body));
    },
  });
}
