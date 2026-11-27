// Risks → Scenarios: what might happen, told on purpose, what it assumes, the risks and
// processes it would touch, and what was concluded.

import { get, patch, post, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { program as loadProgram, unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { banner, field, section, select, submit } from "../components/form.js";
import { recordPicker } from "../components/issue.js";
import { openOverlay } from "../components/overlay.js";
import { rating, standingPill } from "../components/risk.js";
import { toast } from "../components/toast.js";
import { card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const STATUS = { draft: ["Draft", "info"], concluded: ["Concluded", "ok"], retired: ["Retired", ""] };
const statusOf = (status) => pill(STATUS[status]?.[0] ?? status, STATUS[status]?.[1] ?? "");
const mayAdd = () => can("steward") || can("lead") || can("assess");

function scenarioForm({ record = null, unitIndex, onDone }) {
  openOverlay({ title: record ? `Edit ${record.ref}` : "Add a scenario", subtitle: record ? null : "Something that might happen, told as a story, to work through on purpose.",
    render: (body, footer, close) => {
      const name = field("Scenario", { value: record?.name ?? "", required: true, maxlength: 200, hint: "Such as “Ransomware takes research computing down for two weeks”." });
      const unit = select("Unit", unitOptions(unitIndex.tree, { blank: record ? null : "Choose…" }), { value: record?.org_unit_id ?? "", required: true });
      const summary = field("What happens", { type: "textarea", rows: 3, value: record?.summary ?? "", hint: "The story, as it would unfold." });
      const assumptions = field("What it assumes", { type: "textarea", rows: 3, value: record?.assumptions ?? "", hint: "What is taken as given: what still works, how long things take." });
      const conclusion = record ? field("What was concluded", { type: "textarea", rows: 3, value: record.conclusion ?? "", hint: "Needed to conclude it." }) : null;
      const status = record ? select("Status", Object.entries(STATUS).map(([key, [text]]) => [key, text]), { value: record.status }) : null;
      const problem = banner();
      const save = button(record ? "Save" : "Add", { kind: "btn-primary" });
      const values = () => ({ name: name.input.value, org_unit_id: unit.input.value ? Number(unit.input.value) : null, summary: summary.input.value,
        assumptions: assumptions.input.value || null, ...(record ? { conclusion: conclusion.input.value || null, status: status.input.value } : {}) });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { name, org_unit_id: unit, summary, assumptions, ...(record ? { conclusion, status } : {}) }, banner: problem,
          run: () => (record ? patch(`/api/v1/scenarios/${record.ref}`, { ...values(), version: record.version }) : post("/api/v1/scenarios", values())) });
        if (!done) return;
        close();
        toast(record ? "Saved." : `${done.data.ref} was added.`);
        if (record) onDone(); else navigate(`/scenarios/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("The scenario", name.node, unit.node, summary.node, assumptions.node),
        record ? section("Working it through", conclusion.node, status.node) : null));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function touchesForm(record, reload) {
  openOverlay({ title: "What it touches", subtitle: "The risks it would bring about or make worse, and the processes it would stop or slow.",
    render: (body, footer, close) => {
      const chosen = [...record.touches.risks.map((each) => ({ ...each, type: "risk" })), ...record.touches.processes.map((each) => ({ ...each, type: "process" }))];
      const picker = recordPicker({ types: ["risk", "process"], chosen, label: "Add a risk or a process", placeholder: "Search risks and processes", empty: "Nothing yet." });
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/scenarios/${record.ref}/subjects`, { subjects: chosen.map((each) => each.ref) }) });
        if (!done) return;
        close();
        toast("Saved.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, picker));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function scenarioList(main) {
  return show(main, {
    title: "Scenarios",
    load: async () => {
      const [page, unitIndex] = await Promise.all([get("/api/v1/scenarios", { sort: "name", ...Object.fromEntries(query()) }, { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data) => {
      const rows = data.page.data;
      const add = () => scenarioForm({ unitIndex: data.units, onDone: () => {} });
      const search = searchBox("Search scenarios");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("status", [["", "Draft and concluded"], ["draft", "Draft"], ["concluded", "Concluded"], ["retired", "Retired"]], "Status"));
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Scenario", "name", "name"), h("th", { scope: "col" }, "Touches"), h("th", { scope: "col" }, "Owner"), h("th", { scope: "col" }, "Status"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/scenarios/${row.ref}` }, row.name), h("div", { class: "cell-sub" }, [row.ref, data.units.byId.get(row.org_unit_id)?.name].filter(Boolean).join(" · "))),
          h("td", {}, [row.risks ? plural(row.risks, "risk") : null, row.processes ? plural(row.processes, "process", "processes") : null].filter(Boolean).join(", ") || h("span", { class: "subtle" }, "Nothing yet")),
          ownerCell(row),
          h("td", {}, statusOf(row.status), row.concluded_on ? h("div", { class: "cell-sub" }, date(row.concluded_on)) : null))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "risk", title: "No scenarios yet", text: "Tell a story of what might happen, say what it assumes and what it would touch, and record what was concluded.",
            action: mayAdd() ? button("Add a scenario", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: "Scenarios", lede: "What might happen, told on purpose: what it assumes, the risks and processes it would touch, what the estimates of those risks add up to, and what was concluded.",
          actions: mayAdd() ? button("Add a scenario", { kind: "btn-primary", iconName: "plus", onclick: add }) : null }),
        bar, card({ title: plural(data.page.meta.total, "scenario"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

export function scenarioPage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/scenarios/${params.ref}`;
      const [record, unitIndex, vocab, program, entries] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies(), loadProgram(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      const views = record.data.simulation && !record.data.simulation.refused ? await import("../components/risk-views.js") : null;
      return { record: record.data, units: unitIndex, vocab, program, history: entries?.data ?? [], views };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const touches = record.touches;
      const edit = record.can.edit;
      const found = record.simulation;
      const numbers = !found ? h("p", { class: "muted" }, "None of the risks it touches has an estimate in ranges. Estimate them on each risk's In numbers tab, and what they add up to appears here.")
        : found.refused ? h("p", { class: "muted" }, found.refused)
          : h("div", { class: "stack" }, data.views.simulationView(found, found.currency),
            found.without.length ? h("p", { class: "subtle" }, `Not counted, having no estimate: ${found.without.join(", ")}.`) : null);
      const overview = h("div", { class: "split" },
        h("div", { class: "stack-lg" },
          card({ title: "The scenario" }, h("div", { class: "stack" }, prose(record.summary),
            record.assumptions ? h("div", {}, h("div", { class: "label" }, "What it assumes"), prose(record.assumptions)) : null,
            record.conclusion ? h("div", {}, h("div", { class: "label" }, "What was concluded"), prose(record.conclusion)) : null)),
          card({ title: "What it touches", actions: edit ? button("Change", { kind: "btn-sm", onclick: () => touchesForm(record, reload) }) : null, flush: touches.risks.length + touches.processes.length > 0 },
            touches.risks.length || touches.processes.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
              h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Record"), h("th", { scope: "col" }, "Where it stands"), h("th", { scope: "col" }, "In numbers"))),
              h("tbody", {},
                touches.risks.map((risk) => h("tr", {},
                  h("td", {}, h("a", { class: "cell-main", href: `/risks/${risk.ref}` }, risk.name), h("div", { class: "cell-sub" }, risk.ref)),
                  h("td", {}, h("div", { class: "row-sm wrap" }, rating(data.program, risk.residual_rating), standingPill(risk.standing))),
                  h("td", {}, risk.estimated ? h("a", { href: `/risks/${risk.ref}?tab=estimate` }, "Estimated") : h("span", { class: "subtle" }, "No estimate")))),
                touches.processes.map((process) => h("tr", {},
                  h("td", {}, h("a", { class: "cell-main", href: `/processes/${process.ref}` }, process.name), h("div", { class: "cell-sub" }, process.ref)),
                  h("td", {}, `Process · ${process.criticality ?? ""}`), h("td", {}))))))
              : h("p", { class: "muted" }, "Nothing yet. Name the risks it would bring about and the processes it would stop."),
            touches.hidden ? h("p", { class: "subtle card-pad" }, `And ${touches.hidden} more that you do not have access to.`) : null),
          card({ title: "What its risks add up to" }, numbers)),
        h("div", { class: "stack-lg" },
          card({ title: "At a glance" }, facts([
            ["Status", statusOf(record.status)],
            ["Concluded on", record.concluded_on ? date(record.concluded_on) : null],
            ["Unit", data.units.byId.get(record.org_unit_id)?.name],
          ])),
          ownersCard(record, { vocab: data.vocab, units: data.units, reload })));
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [statusOf(record.status)], actions: edit ? button("Edit", { iconName: "edit", onclick: () => scenarioForm({ record, unitIndex: data.units, onDone: reload }) }) : null }),
        tabBar([["overview", "Overview"], ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history)) : overview);
    },
  });
}
