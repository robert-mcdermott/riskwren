// One risk: how much is at stake, whether it is in order, the reasoning, and its history.

import { get, patch } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date } from "../core/format.js";
import { program as loadProgram, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { openOverlay } from "../components/overlay.js";
import { recordChip } from "../components/record.js";
import { flags, journey, rating, reasons, standingPill } from "../components/risk.js";
import { assessRisk, closeRisk, editRisk, editSubjects, escalateRisk } from "../components/risk-forms.js";
import { toast } from "../components/toast.js";
import { controlsTab, treatmentTab } from "../components/treatment.js";
import { alert, card, emptyState } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";

const TABS = [["overview", "Overview"], ["controls", "Controls"], ["treatment", "Treatment"], ["assessments", "Assessments"], ["history", "History"]];
const KIND_TITLES = { inherent: "Inherent rating", residual: "Residual rating", target: "Target rating" };

function showReasons(program, risk, kind) {
  openOverlay({
    title: KIND_TITLES[kind],
    subtitle: `${risk.ref} · ${risk.name}`,
    render: (body) => {
      body.append(reasons(program, risk.assessments[kind]));
    },
  });
}

function overview(risk, ctx) {
  const { program } = ctx;
  const unit = ctx.units.byId.get(risk.org_unit_id);
  const escalated = ctx.units.byId.get(risk.escalated_to_unit_id);
  const statement = [["Cause", prose(risk.cause)], ["Event", prose(risk.event)], ["Consequence", prose(risk.consequence)]];
  const concerns = risk.subjects.records;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      risk.status === "closed" ? alert("info", icon("info"), h("div", {}, h("strong", {}, "Closed. "), risk.closed_reason ?? "")) : null,
      risk.residual_in_doubt ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, "The residual rating may be out of date. "),
        risk.residual_doubt_reason ?? "", " Assess it again.")) : null,
      card({ title: "How much is at stake",
        actions: risk.can.assess && risk.status !== "closed" ? button("Assess", { kind: "btn-sm btn-primary", onclick: () => assessRisk({ risk, program, onDone: ctx.reload }) }) : null },
      journey(program, risk, { onOpen: (kind) => showReasons(program, risk, kind) }),
      h("p", { class: "subtle" }, risk.ratings.inherent.rating || risk.ratings.residual.rating
        ? "Choose a rating to see the judgment behind it."
        : "Not assessed yet. Start with the inherent risk: how likely and how bad, if the controls were not there.")),
      card({ title: "What could go wrong" }, h("div", { class: "statement" }, facts(statement))),
      card({ title: "Concerns", actions: risk.can.edit ? button("Edit", { kind: "btn-sm", onclick: () => editSubjects({ risk, onDone: ctx.reload }) }) : null },
        concerns.length ? h("div", { class: "stack-sm" }, concerns.map((record) => h("div", {}, recordChip(record))))
          : h("p", { class: "muted" }, "Not attached to a process, system, or third party yet."),
        risk.subjects.hidden ? h("p", { class: "subtle" }, `And ${risk.subjects.hidden} more that you do not have access to.`) : null)),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Standing", h("div", { class: "row-sm wrap" }, standingPill(risk.standing), flags(risk))],
        ["Category", risk.category_label],
        ["Appetite", risk.appetite ? h("div", {}, rating(program, risk.appetite), h("div", { class: "cell-sub" }, "The highest residual rating this category is held to.")) : null],
        ["Unit", unit?.name],
        ["Escalated to", escalated ? h("div", {}, escalated.name, h("div", { class: "cell-sub" }, risk.escalation_reason)) : null],
        ["Next review", risk.next_review_on ? h("span", { class: risk.review_overdue ? "overdue" : "" }, date(risk.next_review_on)) : null],
      ])),
      ownersCard(risk, ctx)));
}

function assessmentsTab(risk, list, ctx) {
  if (!list.length) return card({}, emptyState({ iconName: "risk", title: "No assessments yet", text: "Each assessment is a dated judgment by a named person. None is ever edited; a new one supersedes the last." }));
  return h("div", { class: "stack-lg" }, list.map((assessment) =>
    card({ title: `${KIND_TITLES[assessment.kind]}${assessment.superseded ? " (superseded)" : ""}` }, reasons(ctx.program, assessment))));
}

export function riskPage(main, params) {
  const wanted = query().get("tab");
  const tab = TABS.some(([key]) => key === wanted) ? wanted : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/risks/${params.ref}`;
      const [risk, programData, unitIndex, vocab, extra] = await Promise.all([
        get(base, null, { fresh: true }), loadProgram(), units(), vocabularies(),
        ["history", "assessments", "controls", "treatment"].includes(tab) ? get(`${base}/${tab}`, null, { fresh: true }) : null]);
      // What the library suggests for a risk started from it, offered on the Controls tab.
      let suggested = [];
      if (tab === "controls" && risk.data.library_key) {
        const [entry] = (await get("/api/v1/risk-library", { key: risk.data.library_key })).data;
        if (entry?.suggested_controls.length) suggested = (await get("/api/v1/control-library", { keys: entry.suggested_controls.join(",") })).data;
      }
      return { risk: risk.data, program: programData, units: unitIndex, vocab, extra: extra?.data ?? [], suggested };
    },
    view: (data, reload) => {
      const risk = data.risk;
      document.title = `${risk.name} · ${risk.ref}`;
      const ctx = { program: data.program, units: data.units, vocab: data.vocab, reload };
      const reopen = async () => {
        await patch(`/api/v1/risks/${risk.ref}`, { version: risk.version, status: "open" });
        toast("The risk was reopened.");
        reload();
      };
      const actions = h("div", { class: "row-sm wrap" },
        risk.can.edit && risk.status !== "closed" ? button("Edit", { iconName: "edit", onclick: () => editRisk({ record: risk, program: data.program, units: data.units, onDone: reload }) }) : null,
        risk.can_escalate && risk.status !== "closed" ? button("Escalate", { onclick: () => escalateRisk({ risk, units: data.units, onDone: reload }) }) : null,
        risk.can.edit ? (risk.status === "closed" ? button("Reopen", { onclick: reopen })
          : button("Close", { kind: "btn-ghost", onclick: () => closeRisk({ risk, onDone: reload }) })) : null);
      return h("div", { class: "stack" },
        recordHeader(risk, { badges: [rating(data.program, risk.ratings.residual.rating), standingPill(risk.standing), flags(risk)], actions }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra))
          : tab === "assessments" ? assessmentsTab(risk, data.extra, ctx)
            : tab === "controls" ? controlsTab(risk, { controls: data.extra, suggested: data.suggested }, ctx)
              : tab === "treatment" ? treatmentTab(risk, data.extra, ctx) : overview(risk, ctx));
    },
  });
}
