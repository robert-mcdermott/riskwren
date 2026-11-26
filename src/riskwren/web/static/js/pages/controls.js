// The control library. Filters, sort, and page all live in the URL.

import { exportButton } from "../components/exchange.js";
import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural, relative } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { can } from "../core/session.js";
import { editControl, stateOptions, statePill } from "../components/control.js";
import { hrefOf, TYPES } from "../components/record.js";
import { card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

export function controlLibrary(main) {
  const meta = TYPES.control;
  return show(main, {
    title: "Controls",
    load: async () => {
      const [page, vocab, unitIndex] = await Promise.all([
        get("/api/v1/controls", Object.fromEntries(query()), { fresh: true }), vocabularies(), units()]);
      return { page, vocab, units: unitIndex };
    },
    view: (data) => {
      const { vocab } = data;
      const rows = data.page.data;
      const mayAdd = can("steward");
      const add = () => editControl({ vocab, units: data.units });
      const search = searchBox("Search controls");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("kind", options(vocab, "control_kinds", { blank: "Any kind" }), "Kind"),
        filterSelect("state", stateOptions("Any effectiveness"), "Effectiveness"),
        filterSelect("tested", [["", "Tested or not"], ["effective", "Tested, and effective"], ["failing", "Tested, and found wanting"], ["none", "No test that still holds"]], "What its rating rests on"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        mineToggle());
      const body = rows.length
        ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, sortHeader("Control", "name"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Owner"),
            h("th", { scope: "col" }, "Effectiveness"), sortHeader("Last rated", "rated_at"), h("th", { scope: "col", class: "numeric" }, "Risks"), sortHeader("Updated", "updated_at"))),
          h("tbody", {}, rows.map((r) => h("tr", {},
            h("td", {}, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name), r.is_key ? [" ", pill("Key", "accent")] : null,
              h("div", { class: "cell-sub" }, [r.ref, label(vocab, "control_kinds", r.kind), r.status === "retired" ? "Retired" : null].filter(Boolean).join(" · "))),
            h("td", {}, data.units.byId.get(r.org_unit_id)?.name ?? ""),
            ownerCell(r),
            h("td", {}, statePill(r.state)),
            h("td", { class: "nowrap muted" }, r.rated_at ? date(r.rated_at) : "Never"),
            h("td", { class: "numeric" }, r.risks ? String(r.risks) : h("span", { class: "subtle" }, "0")),
            h("td", { class: "nowrap muted" }, relative(r.updated_at)))))))
        : emptyState(isFiltering()
          ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "control", title: "No controls yet", text: "Describe the first one, or start from the library of common controls.",
            action: mayAdd ? button("Add a control", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Controls", title: "Library", lede: meta.lede,
          actions: [mayAdd ? button("Add a control", { kind: "btn-primary", iconName: "plus", onclick: add }) : null,
            can("steward") ? button("Import", { iconName: "upload", onclick: async () => (await import("../components/exchange.js")).openRecordImport({ path: `records/${meta.path}`, what: meta.nouns, onDone: reload }) }) : null, exportButton("controls")] }),
        bar,
        card({ title: plural(data.page.meta.total, "control"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
