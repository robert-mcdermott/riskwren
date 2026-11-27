// Reports → Portfolio: the register and compliance by unit, category, framework, and third
// party over a period, and issues by root cause, source, and age. Every figure opens its list.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date } from "../core/format.js";
import { query, setQuery } from "../core/router.js";
import { bars, listHref } from "../components/charts.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const VIEWS = [["unit", "By unit"], ["category", "By category"], ["framework", "By framework"], ["third_party", "By third party"], ["causes", "Issues and their causes"]];

function cell(figure) {
  if (!figure) return h("td", { class: "numeric" });
  const href = listHref(`/${figure.path}`, figure.filters);
  return h("td", { class: "numeric" }, figure.count ? h("a", { href }, String(figure.count)) : h("span", { class: "subtle" }, "0"));
}

function table(data) {
  if (!data.rows.length) return emptyState({ iconName: "chart", title: "Nothing to show", text: "Nothing you may see falls under this view yet." });
  const extra = data.by === "framework" ? [["Ready", (row) => (row.share == null ? "—" : `${row.share}%`), "Requirements verified or in place, of those that apply, in the scopes you may see"]]
    : data.by === "third_party" ? [["Next review", (row) => (row.next_review_on ? date(row.next_review_on) : "—"), null]] : [];
  return h("div", { class: "table-wrap" }, h("table", { class: "table portfolio-table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, VIEWS.find(([key]) => key === data.by)?.[1].replace("By ", "") ?? ""),
      extra.map(([label, , hint]) => h("th", { scope: "col", title: hint ?? null }, label)),
      data.columns.map(([, label]) => h("th", { scope: "col", class: "numeric" }, label)))),
    h("tbody", {}, data.rows.map((row) => h("tr", {},
      h("td", {}, data.by === "third_party" ? h("a", { class: "cell-main", href: `/third-parties/${row.ref}` }, row.label) : h("span", { class: "cell-main" }, row.label),
        row.note ? h("div", { class: "cell-sub" }, row.note) : null,
        row.scopes ? h("div", { class: "cell-sub" }, row.scopes.map((scope) => scope.name).join(", ")) : null),
      extra.map(([, value]) => h("td", {}, value(row))),
      data.columns.map(([key]) => cell(row.figures[key])))))));
}

function causes(data) {
  const toBars = (rows) => bars(rows.map((row) => ({ label: row.label, value: row.count, href: listHref(`/${row.path}`, row.filters) })));
  return h("div", { class: "stack-lg" },
    h("div", { class: "grid-2" },
      card({ title: "Closed in the period, by why it happened" }, toBars(data.root_causes)),
      card({ title: "Raised in the period, by what found it" }, toBars(data.sources))),
    card({ title: "Open now, by how long ago they were raised" }, toBars(data.ages)),
    card({ title: "Raised and closed, month by month", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Month"), h("th", { scope: "col", class: "numeric" }, "Raised"), h("th", { scope: "col", class: "numeric" }, "Closed"))),
      h("tbody", {}, data.months.map((row) => h("tr", {},
        h("td", {}, new Date(`${row.month}T00:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" })),
        cell(row.raised), cell(row.closed))))))));
}

export function portfolioPage(main) {
  return show(main, {
    title: "Portfolio",
    load: async () => (await get("/api/v1/portfolio", { by: query().get("by") ?? "unit", period: query().get("period") ?? "quarter" }, { fresh: true })).data,
    view: (data) => {
      const picker = (name, choices, current, labelText) => {
        const node = h("select", { class: "select", "aria-label": labelText, onchange: () => setQuery({ [name]: node.value }) },
          choices.map(([key, text]) => h("option", { value: key, selected: key === current }, text)));
        return node;
      };
      const bar = h("div", { class: "filters" },
        picker("by", VIEWS, data.by, "View"),
        picker("period", Object.entries(data.periods), data.period, "Period"),
        h("span", { class: "subtle" }, `${date(data.from)} to ${date(data.to)}`));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Portfolio",
          lede: "The register and compliance cut by unit, category, framework, and third party, with what happened over the period. Every figure opens the records it counts, as you may see them." }),
        bar, data.by === "causes" ? causes(data) : card({ flush: true }, table(data)));
    },
  });
}
