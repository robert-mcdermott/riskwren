// Risks → Objectives: what the organization means to achieve, and the risks that threaten each.

import { get, patch, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { program as loadProgram, unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { exportButton } from "../components/exchange.js";
import { banner, field, section, select, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { rating, standingPill } from "../components/risk.js";
import { listTools, similarHint } from "../components/tidy.js";
import { toast } from "../components/toast.js";
import { card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const STATUS = { active: ["Active", "ok"], achieved: ["Achieved", "info"], retired: ["Retired", ""] };
const statusOf = (status) => pill(STATUS[status]?.[0] ?? status, STATUS[status]?.[1] ?? "");
const mayAdd = () => can("lead") || can("manage");

function objectiveForm({ record = null, unitIndex, onDone }) {
  openOverlay({ title: record ? `Edit ${record.ref}` : "Add an objective", subtitle: record ? null : "What the organization means to achieve. Risks then name the objectives they threaten.",
    render: (body, footer, close) => {
      const name = field("Objective", { value: record?.name ?? "", required: true, maxlength: 200, hint: "As the strategic plan puts it, such as “Grow the cohort to 40,000 participants”." });
      const unit = select("Unit", unitOptions(unitIndex.tree, { blank: record ? null : "Choose…" }), { value: record?.org_unit_id ?? "", required: true, hint: "Usually the whole organization." });
      const period = field("Period", { value: record?.period ?? "", maxlength: 120, hint: "Such as “Strategic plan 2026 to 2030”." });
      const summary = field("Why it matters", { type: "textarea", rows: 2, value: record?.summary ?? "" });
      const measure = field("How it is known to be met", { type: "textarea", rows: 2, value: record?.measure ?? "" });
      const status = record ? select("Status", Object.entries(STATUS).map(([key, [text]]) => [key, text]), { value: record.status }) : null;
      const problem = banner();
      const save = button(record ? "Save" : "Add", { kind: "btn-primary" });
      const values = () => ({ name: name.input.value, org_unit_id: unit.input.value ? Number(unit.input.value) : null, period: period.input.value || null,
        summary: summary.input.value, measure: measure.input.value || null, ...(status ? { status: status.input.value } : {}) });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { name, org_unit_id: unit, period, summary, measure }, banner: problem,
          run: () => (record ? patch(`/api/v1/objectives/${record.ref}`, { ...values(), version: record.version }) : post("/api/v1/objectives", values())) });
        if (!done) return;
        close();
        toast(record ? "Saved." : `${done.data.ref} was added.`);
        if (record) onDone(); else navigate(`/objectives/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("What it is", name.node, similarHint("objective", name.input, { unit: () => unit.input.value, apartFrom: record?.ref }), unit.node, period.node, summary.node),
        section("Knowing it is met", measure.node, status ? status.node : null)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function objectiveList(main) {
  return show(main, {
    title: "Objectives",
    load: async () => {
      const [page, unitIndex, program] = await Promise.all([get("/api/v1/objectives", { sort: "name", ...Object.fromEntries(query()) }, { fresh: true }), units(), loadProgram()]);
      return { page, units: unitIndex, program };
    },
    view: (data) => {
      const rows = data.page.data;
      const add = () => objectiveForm({ unitIndex: data.units, onDone: () => {} });
      const search = searchBox("Search objectives");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search), listTools(),
        filterSelect("status", [["", "Active and achieved"], ["active", "Active"], ["achieved", "Achieved"], ["retired", "Retired"]], "Status"), mineToggle());
      const ratings = data.program.ratings ?? [];
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Objective", "name", "name"), h("th", { scope: "col" }, "Period"), h("th", { scope: "col" }, "Owner"),
          h("th", { scope: "col" }, "Open risks that threaten it"), h("th", { scope: "col" }, "Status"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/objectives/${row.ref}` }, row.name), h("div", { class: "cell-sub" }, row.ref)),
          h("td", {}, row.period ?? ""), ownerCell(row),
          h("td", {}, row.risks ? h("div", { class: "row-sm wrap" }, ratings.slice().reverse().filter((each) => row.by_rating[each.key])
            .map((each) => h("span", { class: "row-sm" }, rating(data.program, each.key), h("span", { class: "numeric" }, String(row.by_rating[each.key])))))
            : h("span", { class: "subtle" }, "None named")),
          h("td", {}, statusOf(row.status)))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "objective", title: "No objectives yet", text: "Add the aims of the strategic plan. Risks then name the ones they threaten.",
            action: mayAdd() ? button("Add an objective", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: "Objectives", lede: "What the organization means to achieve, and the risks that threaten each: the register read against the strategic plan.",
          actions: [mayAdd() ? button("Add an objective", { kind: "btn-primary", iconName: "plus", onclick: add }) : null, exportButton("objectives")] }),
        bar, card({ title: plural(data.page.meta.total, "objective"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

export function objectivePage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/objectives/${params.ref}`;
      const [record, unitIndex, vocab, program, entries] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies(), loadProgram(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { record: record.data, units: unitIndex, vocab, program, history: entries?.data ?? [] };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const risks = record.threatened_by.risks;
      const open = risks.filter((risk) => risk.status === "open");
      const overview = h("div", { class: "split" },
        h("div", { class: "stack-lg" },
          record.summary || record.measure ? card({ title: "What it is" }, prose(record.summary),
            record.measure ? h("div", {}, h("div", { class: "label" }, "How it is known to be met"), prose(record.measure)) : null) : null,
          card({ title: open.length ? `Risks that threaten it (${open.length} open)` : "Risks that threaten it", flush: risks.length > 0 },
            risks.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
              h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "Residual"), h("th", { scope: "col" }, "Standing"))),
              h("tbody", {}, risks.map((risk) => h("tr", {},
                h("td", {}, h("a", { class: "cell-main", href: `/risks/${risk.ref}` }, risk.name), h("div", { class: "cell-sub" }, [risk.ref, data.units.byId.get(risk.org_unit_id)?.name, risk.status === "closed" ? "closed" : null].filter(Boolean).join(" · "))),
                h("td", {}, rating(data.program, risk.residual_rating)),
                h("td", {}, standingPill(risk.standing)))))))
              : h("p", { class: "muted" }, "No risk names it yet. A risk's keepers name the objectives it threatens on the risk."),
            record.threatened_by.hidden ? h("p", { class: "subtle card-pad" }, `And ${record.threatened_by.hidden} more that you do not have access to.`) : null)),
        h("div", { class: "stack-lg" },
          card({ title: "At a glance" }, facts([
            ["Status", statusOf(record.status)],
            ["Period", record.period],
            ["Unit", data.units.byId.get(record.org_unit_id)?.name],
          ])),
          ownersCard(record, { vocab: data.vocab, units: data.units, reload })));
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [statusOf(record.status)], actions: record.can.edit ? button("Edit", { iconName: "edit", onclick: () => objectiveForm({ record, unitIndex: data.units, onDone: reload }) }) : null }),
        tabBar([["overview", "Overview"], ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history)) : overview);
    },
  });
}
