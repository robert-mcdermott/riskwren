// The scoring method's matrix as a grid: impact up the side, likelihood along the bottom,
// each cell colored by its rating. Used to show the method, and by the heat map to count risks.

import { h } from "../core/dom.js";

/**
 * cell(likelihood, impact, rating) returns what goes in a cell (a count, a link, or nothing).
 * The grid is a real table, so it reads sensibly without the colors.
 */
export function matrixGrid(program, { cell = () => null, caption = "How likelihood and impact combine into a rating" } = {}) {
  const method = program.method;
  const ratings = Object.fromEntries(method.ratings.map((item) => [item.key, item]));
  const impacts = [...method.impact_levels].reverse();
  return h("table", { class: "matrix" },
    h("caption", { class: "sr-only" }, caption),
    h("tbody", {}, impacts.map((impact) => h("tr", {},
      h("th", { scope: "row" }, h("span", { class: "matrix-number" }, String(impact.level)), impact.label),
      method.likelihood.map((likelihood) => {
        const key = method.matrix[impact.level - 1][likelihood.level - 1];
        const rated = ratings[key];
        return h("td", { class: "matrix-cell", "data-level": rated.ramp_level,
          title: `${likelihood.label} likelihood, ${impact.label.toLowerCase()} impact: ${rated.label}` },
        cell(likelihood.level, impact.level, rated) ?? h("span", { class: "matrix-rating" }, rated.label));
      })))),
    h("tfoot", {}, h("tr", {}, h("td", {}),
      method.likelihood.map((likelihood) => h("th", { scope: "col" }, h("span", { class: "matrix-number" }, String(likelihood.level)), likelihood.label)))));
}
