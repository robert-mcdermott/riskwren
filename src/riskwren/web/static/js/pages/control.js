// One control: what is done, what is known of how well, and the risks it bears on.

import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { label, program as loadProgram, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { editControl, rateControl, ratedLine, reducesLabel, statePill } from "../components/control.js";
import { hrefOf } from "../components/record.js";
import { rating, standingPill } from "../components/risk.js";
import { card, emptyState, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";

const TABS = [["overview", "Overview"], ["ratings", "Ratings"], ["history", "History"]];

function overview(control, ctx) {
  const v = ctx.vocab;
  const risks = control.reduces.risks;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      card({ title: "What is done" }, prose(control.statement),
        control.objective ? h("div", {}, h("div", { class: "label" }, "Objective"), prose(control.objective)) : null),
      card({ title: "How well it works",
        actions: control.can.assess && control.status === "active" ? button("Rate", { kind: "btn-sm btn-primary", onclick: () => rateControl({ control, onDone: ctx.reload }) }) : null },
      control.state === "stale" ? h("p", { class: "warn-text" }, "This rating is out of date. Until it is rated again, the control counts for nothing.") : null,
      ratedLine(control.rating)),
      card({ title: "Risks it bears on", flush: risks.length > 0 },
        risks.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "How"), h("th", { scope: "col" }, "Residual"), h("th", { scope: "col" }, "Standing"))),
          h("tbody", {}, risks.map((risk) => h("tr", {},
            h("td", {}, h("a", { class: "cell-main", href: hrefOf(risk.ref) }, risk.name), h("div", { class: "cell-sub" }, risk.ref)),
            h("td", {}, reducesLabel(risk.reduces), h("div", { class: "cell-sub" }, risk.reliance === "primary" ? "Primary" : "Supporting")),
            h("td", {}, rating(ctx.program, risk.residual_rating)),
            h("td", {}, standingPill(risk.standing)))))))
          : h("p", { class: "muted" }, "Not linked to a risk yet. Link it from a risk's Controls tab."),
        control.reduces.hidden ? h("p", { class: "subtle" }, `And ${control.reduces.hidden} more that you do not have access to.`) : null)),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Kind", label(v, "control_kinds", control.kind)],
        ["Nature", label(v, "control_natures", control.nature)],
        ["How often", label(v, "control_frequencies", control.frequency)],
        ["Unit", ctx.units.byId.get(control.org_unit_id)?.name],
        ["Last rated", control.rated_at ? date(control.rated_at) : "Never"],
      ])),
      ownersCard(control, ctx)));
}

function ratingsTab(list) {
  if (!list.length) return card({}, emptyState({ iconName: "control", title: "No ratings yet", text: "Each rating says who found what, when, and on what basis. None is ever edited; a new one supersedes the last." }));
  return h("div", { class: "stack-lg" }, list.map((item) => card({ title: item.superseded ? "Superseded" : "In force" }, ratedLine(item))));
}

export function controlPage(main, params) {
  const wanted = query().get("tab");
  const tab = TABS.some(([key]) => key === wanted) ? wanted : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/controls/${params.ref}`;
      const [control, vocab, unitIndex, programData, extra] = await Promise.all([
        get(base, null, { fresh: true }), vocabularies(), units(), loadProgram(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : tab === "ratings" ? get(`${base}/ratings`, null, { fresh: true }) : null]);
      return { control: control.data, vocab, units: unitIndex, program: programData, extra: extra?.data ?? [] };
    },
    view: (data, reload) => {
      const control = data.control;
      document.title = `${control.name} · ${control.ref}`;
      const ctx = { vocab: data.vocab, units: data.units, program: data.program, reload };
      const edit = control.can.edit ? button("Edit", { iconName: "edit", onclick: () => editControl({ record: control, vocab: data.vocab, units: data.units, onDone: reload }) }) : null;
      return h("div", { class: "stack" },
        recordHeader(control, { badges: [statePill(control.state), control.is_key ? pill("Key control", "accent") : null,
          control.status === "retired" ? pill("Retired") : null], actions: edit }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : tab === "ratings" ? ratingsTab(data.extra) : overview(control, ctx));
    },
  });
}
