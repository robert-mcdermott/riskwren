// The heat map: every open risk the viewer may see, by likelihood and impact. Each cell is
// a count and a link, and the grid is a real table, so it reads without its colors.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { categoryOptions, program as loadProgram, unitOptions, units } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { position } from "../core/scoring.js";
import { listHref } from "../components/charts.js";
import { matrixGrid } from "../components/matrix.js";
import { rating } from "../components/risk.js";
import { card, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { filterSelect } from "./records.js";

const KINDS = [["residual", "Residual", "As things are, with the controls as they actually work."],
  ["inherent", "Inherent", "If the controls were not there, or did not work."],
  ["target", "Target", "Where each risk should be once its treatment is complete."]];

/** The grid of counts, for the heat map page and for the dashboard. */
export function heatGrid(program, heat, scope = {}) {
  const above = (ratingKey) => heat.appetite && position(program.method, ratingKey) > position(program.method, heat.appetite);
  return matrixGrid(program, {
    caption: `Open risks by ${heat.kind} likelihood and impact`,
    cell: (likelihood, impact, rated) => {
      const count = heat.cells[impact - 1][likelihood - 1];
      const mark = above(rated.key) ? h("span", { class: "matrix-above", title: "Above appetite for this category" }, "above") : null;
      if (!count) return h("span", { class: "matrix-none" }, h("span", { class: "sr-only" }, `No risks. ${rated.label}.`), mark);
      const filters = { status: "open", [`${heat.kind}_likelihood`]: likelihood, [`${heat.kind}_impact`]: impact, ...scope };
      return h("a", { class: "matrix-count", href: listHref("/risks", filters),
        "aria-label": `${plural(count, "risk")} rated ${rated.label}: likelihood ${likelihood}, impact ${impact}` }, String(count), mark);
    },
  });
}

export function heatMap(main) {
  const kind = KINDS.some(([key]) => key === query().get("kind")) ? query().get("kind") : "residual";
  return show(main, {
    title: "Heat map",
    load: async () => {
      const params = Object.fromEntries(query());
      const [heat, programData, unitIndex] = await Promise.all([
        get("/api/v1/heat-map", { kind, ...params }, { fresh: true }), loadProgram(), units()]);
      return { heat: heat.data, program: programData, units: unitIndex };
    },
    view: (data) => {
      const { heat, program } = data;
      const scope = {};
      for (const name of ["unit", "category"]) if (query().get(name)) scope[name] = query().get(name);
      const tabs = h("div", { class: "segmented", role: "group", "aria-label": "Which rating" }, KINDS.map(([key, text]) =>
        h("button", { type: "button", class: `btn${key === kind ? " btn-primary" : ""}`, "aria-pressed": String(key === kind),
          onclick: () => setQuery({ kind: key === "residual" ? null : key }) }, text)));
      const bar = h("div", { class: "filters" }, tabs,
        filterSelect("unit", unitOptions(data.units.tree, { blank: "The whole organization" }), "Unit"),
        filterSelect("category", categoryOptions(program, { blank: "Every category" }), "Category"));
      const summary = h("div", { class: "row wrap" }, program.method.ratings.slice().reverse().map((item) => h("a", { class: "row-sm",
        href: listHref("/risks", { status: "open", [`${kind}_rating`]: item.key, ...scope }) }, rating(program, item.key), h("strong", { class: "numeric" }, String(heat.by_rating[item.key])))),
      heat.unrated ? h("a", { class: "row-sm muted", href: listHref("/risks", { status: "open", ...(kind === "residual" ? { standing: "not_assessed" } : {}), ...scope }) },
        `${plural(heat.unrated, "risk")} with no ${kind} rating`) : null);
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: "Heat map", lede: KINDS.find(([key]) => key === kind)[2] }),
        bar,
        card({ title: `${plural(heat.rated, "open risk")} rated` }, h("div", { class: "stack-lg" },
          heatGrid(program, heat, scope), summary,
          heat.appetite ? h("p", { class: "subtle" }, "Cells marked ", h("em", {}, "above"), " are above this category's appetite, which is ", rating(program, heat.appetite), ".")
            : h("p", { class: "subtle" }, "Choose a category to see where its appetite falls. Rating says how much is at stake; whether a risk is in order is its standing, shown in the register."))));
    },
  });
}
