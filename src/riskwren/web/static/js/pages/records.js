// The inventory's list pages. Filters, sort, and page all live in the URL.

import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { plural, relative } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { can } from "../core/session.js";
import { criticality, hrefOf, statusOptions, statusPill, TYPES } from "../components/record.js";
import { exportButton } from "../components/exchange.js";
import { editRecord } from "../components/record-forms.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

export function filterSelect(name, choices, labelText) {
  const node = h("select", { class: "select", "aria-label": labelText, onchange: () => setQuery({ [name]: node.value, cursor: null }) },
    choices.map(([key, text]) => h("option", { value: key, selected: String(key) === (query().get(name) ?? "") }, text)));
  return node;
}

export function sortHeader(text, field, fallback = "-updated_at") {
  const current = query().get("sort") ?? fallback;
  const active = current.replace(/^-/, "") === field;
  const descending = active && current.startsWith("-");
  return h("th", { scope: "col", "aria-sort": active ? (descending ? "descending" : "ascending") : null },
    h("button", { type: "button", class: "sort-button", onclick: () => setQuery({ sort: active && !descending ? `-${field}` : field, cursor: null }) },
      text, active ? h("span", { "aria-hidden": "true" }, descending ? " ↓" : " ↑") : null));
}

/** A search box that writes to the URL a moment after typing stops. */
export function searchBox(placeholder) {
  const search = h("input", { class: "input", type: "search", value: query().get("q") ?? "", placeholder, "aria-label": "Search" });
  let timer = null;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => setQuery({ q: search.value, cursor: null }), 250);
  });
  return search;
}

export function mineToggle() {
  const mine = query().get("mine") === "true";
  return h("button", { type: "button", class: `btn${mine ? " btn-primary" : ""}`, "aria-pressed": String(mine),
    onclick: () => setQuery({ mine: mine ? null : "true", cursor: null }) }, "Mine");
}

/** Keep the caret in the search box when the list redraws under it. */
export function keepSearchFocus(search) {
  if (document.activeElement?.getAttribute?.("aria-label") !== "Search") return;
  queueMicrotask(() => {
    search.focus();
    search.setSelectionRange(search.value.length, search.value.length);
  });
}

export function pager(meta, shown) {
  const { total, offset, next_cursor: next, prev_cursor: prev } = meta;
  if (total <= shown) return null;
  return h("div", { class: "row" },
    h("span", { class: "muted numeric" }, `${offset + 1}–${offset + shown} of ${total}`),
    h("div", { class: "spacer row-sm" },
      button("Previous", { kind: "btn-sm", iconName: "chevron-left", disabled: prev == null, onclick: () => setQuery({ cursor: prev }, { replace: false }) }),
      button("Next", { kind: "btn-sm", disabled: !next, onclick: () => setQuery({ cursor: next }, { replace: false }) })));
}

export function clearFilters() {
  setQuery(Object.fromEntries([...query().keys()].map((key) => [key, null])));
}

export function isFiltering() {
  return [...query().keys()].some((key) => !["sort", "cursor"].includes(key));
}

export function ownerCell(record) {
  return h("td", {}, record.owners.map((owner) => owner.name).join(", "),
    record.orphaned ? h("div", { class: "cell-sub warn-text" }, record.owners.length ? "Owner has left" : "No owner") : null);
}

export function recordList(main, type) {
  const meta = TYPES[type];
  return show(main, {
    title: meta.plural,
    load: async () => {
      const params = Object.fromEntries(query());
      const [page, vocab, unitIndex] = await Promise.all([
        get(`/api/v1/${meta.path}`, params, { fresh: true }), vocabularies(), units()]);
      return { page, vocab, units: unitIndex };
    },
    view: (data, reload) => {
      const { vocab } = data;
      const rows = data.page.data;
      const total = data.page.meta.total;
      const mayAdd = can("steward");
      const add = () => editRecord(type, { vocab, units: data.units, onDone: reload });
      const search = searchBox(`Search ${meta.nouns}`);
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("kind", options(vocab, meta.kinds, { blank: "Any kind" }), "Kind"),
        filterSelect("criticality", options(vocab, "criticalities", { blank: "Any criticality" }), "Criticality"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        filterSelect("status", statusOptions(["active", "retired"], "Any status"), "Status"),
        mineToggle());
      const body = rows.length
        ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, sortHeader(meta.label, "name"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Owner"),
            sortHeader("Criticality", "criticality"), h("th", { scope: "col" }, "Data"), sortHeader("Status", "status"),
            sortHeader("Updated", "updated_at"))),
          h("tbody", {}, rows.map((r) => h("tr", {},
            h("td", {}, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name),
              h("div", { class: "cell-sub" }, [r.ref, label(vocab, meta.kinds, r.kind), r.restricted ? "Restricted" : null].filter(Boolean).join(" · "))),
            h("td", {}, data.units.byId.get(r.org_unit_id)?.name ?? ""),
            ownerCell(r),
            h("td", {}, criticality(vocab, r.criticality)),
            h("td", {}, r.data_class ? label(vocab, "data_classes", r.data_class) : h("span", { class: "subtle" }, "Not said")),
            h("td", {}, statusPill(r.status)),
            h("td", { class: "nowrap muted" }, relative(r.updated_at)))))))
        : emptyState(isFiltering()
          ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.",
            action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: meta.iconName, title: `No ${meta.nouns} yet`, text: meta.lede,
            action: mayAdd ? button(`Add ${meta.article}`, { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: meta.section, title: meta.plural, lede: meta.lede,
          actions: [mayAdd ? button(`Add ${meta.article}`, { kind: "btn-primary", iconName: "plus", onclick: add }) : null,
            mayAdd ? button("Import", { iconName: "upload", onclick: async () => (await import("../components/exchange.js")).openRecordImport({ path: `records/${meta.path}`, what: meta.nouns, onDone: reload }) }) : null, exportButton(meta.path)] }),
        bar,
        card({ title: plural(total, meta.noun, meta.nouns), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
