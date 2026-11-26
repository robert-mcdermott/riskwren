// The risk register. Filters, sort, and page all live in the URL.

import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { categoryOptions, program as loadProgram, unitOptions, units } from "../core/lookups.js";
import { query } from "../core/router.js";
import { can } from "../core/session.js";
import { hrefOf, TYPES } from "../components/record.js";
import { flags, rating, ratingOptions, standingOptions, standingPill } from "../components/risk.js";
import { editRisk } from "../components/risk-forms.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const SORT = "-residual_rating";

export function riskRegister(main) {
  const meta = TYPES.risk;
  return show(main, {
    title: "Risk register",
    load: async () => {
      const params = { sort: SORT, ...Object.fromEntries(query()) };
      const [page, programData, unitIndex] = await Promise.all([
        get("/api/v1/risks", params, { fresh: true }), loadProgram(), units()]);
      return { page, program: programData, units: unitIndex };
    },
    view: (data, reload) => {
      const { program } = data;
      const rows = data.page.data;
      const total = data.page.meta.total;
      const mayAdd = can("steward");
      const add = () => editRisk({ program, units: data.units, onDone: reload });
      const search = searchBox("Search risks");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("category", categoryOptions(program, { blank: "Any category" }), "Category"),
        filterSelect("residual_rating", ratingOptions(program, "Any residual rating"), "Residual rating"),
        filterSelect("standing", standingOptions("Any standing"), "Standing"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        mineToggle());
      const head = (text, field) => sortHeader(text, field, SORT);
      const body = rows.length
        ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, head("Risk", "name"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Owner"),
            head("Inherent", "inherent_rating"), head("Residual", "residual_rating"), head("Standing", "standing"), head("Next review", "next_review_on"))),
          h("tbody", {}, rows.map((r) => h("tr", {},
            h("td", {}, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name),
              h("div", { class: "cell-sub" }, [r.ref, r.category_label, r.restricted ? "Restricted" : null].filter(Boolean).join(" · "))),
            h("td", {}, data.units.byId.get(r.org_unit_id)?.name ?? "",
              r.escalated_to_unit_id ? h("div", { class: "cell-sub" }, `Escalated to ${data.units.byId.get(r.escalated_to_unit_id)?.name ?? "a unit above"}`) : null),
            ownerCell(r),
            h("td", {}, rating(program, r.ratings.inherent.rating)),
            h("td", {}, rating(program, r.ratings.residual.rating)),
            h("td", {}, h("div", { class: "row-sm wrap" }, standingPill(r.standing), flags(r))),
            h("td", { class: `nowrap${r.review_overdue ? " overdue" : " muted"}` }, r.next_review_on ? date(r.next_review_on) : ""))))))
        : emptyState(isFiltering()
          ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.",
            action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "risk", title: "No risks yet",
            text: "Raise the first one from the library, or write your own: something that could happen, and would matter.",
            action: mayAdd ? button("Raise a risk", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: "Register", lede: meta.lede,
          actions: mayAdd ? button("Raise a risk", { kind: "btn-primary", iconName: "plus", onclick: add }) : null }),
        bar,
        card({ title: plural(total, "risk"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
