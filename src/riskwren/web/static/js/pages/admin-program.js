// Admin → Program: how risks are rated here. The categories and their appetite, and the
// scoring method with every definition, so that anyone can see what a rating means.

import { patch } from "../core/api.js";
import { h } from "../core/dom.js";
import { program as loadProgram } from "../core/lookups.js";
import { matrixGrid } from "../components/matrix.js";
import { rating } from "../components/risk.js";
import { toast } from "../components/toast.js";
import { alert, card, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

function appetiteSelect(program, category, top, reload) {
  const choices = [...(top ? [] : [["", "The same as above"]]), ...program.method.ratings.map((item) => [item.key, item.label])];
  const node = h("select", { class: "select", "aria-label": `Appetite for ${category.name}` },
    choices.map(([key, text]) => h("option", { value: key, selected: key === (category.appetite ?? "") }, text)));
  node.addEventListener("change", async () => {
    try {
      const done = await patch(`/api/v1/risk-categories/${category.key}`, { appetite: node.value || null });
      const moved = done.meta.risks_whose_standing_changed;
      toast(moved ? `Saved. The standing of ${moved} ${moved === 1 ? "risk" : "risks"} changed.` : "Saved. No risk changed standing.");
      reload();
    } catch (error) {
      toast(Object.values(error.fields ?? {}).join(" ") || error.detail || "That could not be saved.");
      node.value = category.appetite ?? "";
    }
  });
  return node;
}

function taxonomy(program, reload) {
  const row = (category, top) => h("tr", {},
    h("td", {}, h("div", { class: top ? "cell-main" : "", style: null }, top ? category.name : `\u2003${category.name}`),
      top && category.description ? h("div", { class: "cell-sub" }, category.description) : null),
    h("td", {}, appetiteSelect(program, category, top, reload)),
    h("td", {}, rating(program, category.appetite_in_force)));
  return card({ title: "Risk categories and appetite", flush: true },
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Category"), h("th", { scope: "col" }, "Appetite"), h("th", { scope: "col" }, "In force"))),
      h("tbody", {}, program.categories.flatMap((top) => [row(top, true), ...top.children.map((child) => row(child, false))])))));
}

function definitions(program) {
  const method = program.method;
  return [
    card({ title: "Likelihood", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("tbody", {}, method.likelihood.map((level) => h("tr", {}, h("th", { scope: "row" }, `${level.level} ${level.label}`), h("td", {}, level.definition))))))),
    card({ title: "Impact, by dimension", flush: true },
      h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Dimension"), method.impact_levels.map((level) => h("th", { scope: "col" }, `${level.level} ${level.label}`)))),
        h("tbody", {}, method.dimensions.map((dimension) => h("tr", {},
          h("th", { scope: "row" }, dimension.label, h("div", { class: "cell-sub" }, dimension.question)),
          method.impact_levels.map((level) => h("td", { class: "cell-sub" }, dimension.levels[String(level.level)])))))))),
  ];
}

function rules(program) {
  const ratings = program.method.ratings;
  const months = (count) => (count == null ? "" : `${count} ${count === 1 ? "month" : "months"}`);
  return card({ title: "What follows from a rating", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Residual rating"), h("th", { scope: "col" }, "What it means"),
      h("th", { scope: "col" }, "Reviewed every"), h("th", { scope: "col" }, "If above appetite, may be accepted"))),
    h("tbody", {}, ratings.map((item) => {
      const rule = program.authority.acceptance[item.key];
      return h("tr", {}, h("td", {}, rating(program, item.key)), h("td", {}, item.description),
        h("td", {}, months(program.cadences.risk_review_months[item.key])),
        h("td", {}, rule ? `For up to ${months(rule.max_months)}, by a leader${rule.needs_limit ? ` whose limit reaches ${item.label}` : " of the unit or above"}` : "No acceptance is needed"));
    })))));
}

export function adminProgram(main) {
  return show(main, {
    title: "Program",
    load: () => loadProgram({ fresh: true }),
    view: (program, reload) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Admin", title: "Program",
        lede: "How risks are rated here: what each level means, how likelihood and impact combine, and how much each kind of risk may be lived with." }),
      taxonomy(program, reload),
      card({ title: `The matrix (scoring method version ${program.method.version})` },
        matrixGrid(program),
        h("p", { class: "subtle" }, "Impact up the side, likelihood along the bottom. The overall impact of a risk is the highest level rated on any dimension.")),
      rules(program),
      definitions(program),
      alert("info", h("div", {}, "The scoring method, cadences, and vocabularies are changed by importing a program pack: ",
        h("code", {}, "riskwren program export"), " writes the one in force, and ", h("code", {}, "riskwren program import"),
        " loads an edited one. A new method is a new version; assessments already made keep theirs."))),
  });
}
