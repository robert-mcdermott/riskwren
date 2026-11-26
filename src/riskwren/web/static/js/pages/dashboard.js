// The risk dashboard: where the register stands. Every figure opens the records behind it.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { program as loadProgram, unitOptions, units } from "../core/lookups.js";
import { query } from "../core/router.js";
import { bars, listHref, sizeBars, statTile } from "../components/charts.js";
import { STATES, statePill } from "../components/control.js";
import { hrefOf } from "../components/record.js";
import { flags, rating, STANDING, standingPill } from "../components/risk.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { heatGrid } from "./heat-map.js";
import { show } from "./page.js";
import { filterSelect } from "./records.js";

export function dashboard(main) {
  return show(main, {
    title: "Dashboard",
    load: async () => {
      const [board, programData, unitIndex] = await Promise.all([
        get("/api/v1/dashboard", Object.fromEntries(query()), { fresh: true }), loadProgram(), units()]);
      return { board: board.data, program: programData, units: unitIndex };
    },
    view: (data) => {
      const { board, program } = data;
      const t = board.totals;
      const risks = (figure) => listHref("/risks", figure.filters);
      const scope = board.unit ? { unit: board.unit } : {};
      const unitName = board.unit ? data.units.byId.get(board.unit)?.name : null;
      if (!t.open.count && !board.controls.total.count) {
        return h("div", { class: "stack-lg" }, pageHeader({ eyebrow: "Reports", title: "Dashboard" }),
          card({}, emptyState({ iconName: "risk", title: "Nothing to report yet", text: "Once risks are raised and assessed, this page shows where the register stands." })));
      }
      const tiles = h("div", { class: "tiles" },
        statTile({ value: t.open.count, label: "Open risks", href: risks(t.open) }),
        statTile({ value: t.above_appetite.count, label: "Above appetite", href: risks(t.above_appetite) }),
        statTile({ value: t.needs_decision.count, label: "Need a decision", href: risks(t.needs_decision), tone: "danger" }),
        statTile({ value: t.review_overdue.count, label: "Reviews overdue", href: risks(t.review_overdue), tone: "warn" }),
        statTile({ value: t.in_doubt.count, label: "Ratings in doubt", href: risks(t.in_doubt), tone: "warn" }),
        statTile({ value: t.actions_overdue.count, label: `Actions overdue, of ${t.actions_open.count} open`, href: listHref("/actions", t.actions_overdue.filters), tone: "danger" }));
      const top = board.top_risks.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "Residual"), h("th", { scope: "col" }, "Standing"))),
        h("tbody", {}, board.top_risks.map((risk) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: hrefOf(risk.ref) }, risk.name),
            h("div", { class: "cell-sub" }, [risk.ref, data.units.byId.get(risk.org_unit_id)?.name].filter(Boolean).join(" · "))),
          h("td", {}, rating(program, risk.ratings.residual.rating)),
          h("td", {}, h("div", { class: "row-sm wrap" }, standingPill(risk.standing), flags(risk))))))))
        : h("p", { class: "muted" }, "No risk has a residual rating yet.");
      return sizeBars(h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Dashboard",
          lede: unitName ? `Where the register stands for ${unitName} and everything beneath it.` : "Where the register stands, for everything you may see.",
          actions: filterSelect("unit", unitOptions(data.units.tree, { blank: "The whole organization" }), "Unit") }),
        tiles,
        h("div", { class: "grid-2" },
          card({ title: "Residual risk", actions: h("a", { href: listHref("/heat-map", scope) }, "Open the heat map") }, heatGrid(program, board.heat_map, scope)),
          card({ title: "Highest risks", flush: board.top_risks.length > 0, actions: h("a", { href: risks(t.open) }, "The register") }, top)),
        h("div", { class: "grid-2" },
          card({ title: "By standing" }, bars(board.by_standing.map((figure) => ({ label: STANDING[figure.key][0], badge: standingPill(figure.key), value: figure.count, href: risks(figure) })))),
          card({ title: "By residual rating" }, bars(board.by_rating.map((figure) => ({ label: figure.label, badge: rating(program, figure.key), value: figure.count, href: risks(figure) })),
            { empty: "No risk has a residual rating yet." }))),
        h("div", { class: "grid-2" },
          card({ title: "By category" }, bars(board.by_category.map((figure) => ({ label: figure.name, value: figure.count, href: risks(figure), part: figure.above, partLabel: "above appetite" })))),
          card({ title: unitName ? `Within ${unitName}` : "By unit" }, bars(board.by_unit.map((figure) => ({ label: figure.name, value: figure.count, href: risks(figure), part: figure.above, partLabel: "above appetite" })),
            { empty: "No unit beneath this one has an open risk." }))),
        card({ title: "What is known about the controls", actions: h("a", { href: listHref("/controls", board.controls.total.filters) }, `All ${board.controls.total.count}`) },
          bars([...board.controls.by_state.map((figure) => ({ label: STATES[figure.key][0], badge: statePill(figure.key), value: figure.count, href: listHref("/controls", figure.filters) })),
            { label: STATES.stale[0], badge: statePill("stale"), value: board.controls.stale.count, href: listHref("/controls", board.controls.stale.filters) }]),
          h("p", { class: "subtle" }, "A control that is not assessed, or whose rating is out of date, counts for nothing when a residual rating is suggested."))));
    },
  });
}
