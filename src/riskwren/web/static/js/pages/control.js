// One control: what is done, what is known of how well, and the risks it bears on.

import { customCard } from "../components/custom-fields.js";
import { del, get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { label, program as loadProgram, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { editControl, rateControl, ratedLine, reducesLabel, statePill } from "../components/control.js";
import { KINDS } from "../components/document.js";
import { coveragePill, mapCrosswalk } from "../components/crosswalk.js";
import { evidenceCard } from "../components/evidence.js";
import { confirmAction } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { hrefOf } from "../components/record.js";
import { rating, standingPill } from "../components/risk.js";
import { card, emptyState, pill } from "../components/ui.js";
import { incidentsCard } from "../components/incident-links.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";

const TABS = [["overview", "Overview"], ["requirements", "Requirements"], ["ratings", "Ratings"], ["history", "History"]];

function overview(control, ctx) {
  const v = ctx.vocab;
  const risks = control.reduces.risks;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      card({ title: "What is done" }, prose(control.statement),
        control.objective ? h("div", {}, h("div", { class: "label" }, "Objective"), prose(control.objective)) : null),
      card({ title: "How well it works",
        actions: control.can.assess && control.status === "active" && !control.tested ? button("Rate", { kind: "btn-sm btn-primary", onclick: () => rateControl({ control, onDone: ctx.reload }) }) : null },
      control.state === "stale" ? h("p", { class: "warn-text" }, "This rating is out of date. Until it is rated again, the control counts for nothing.") : null,
      ratedLine(control.rating),
      control.tested ? h("p", { class: "subtle" }, "This is the result of a test. Until it goes out of date, only another test replaces it.") : null),
      evidenceCard(control, ctx),
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
        ["Key control", control.is_key ? "Yes: tested more often" : null],
        ["Attested by its owner", control.attested ? `${{ yes: "Operates as described", partly: "Operates only partly", no: "Does not operate" }[control.attested.operates] ?? control.attested.operates}, ${control.attested.by}, ${date(control.attested.at)}. An attestation is not a test.` : null],
        ["Next test due", control.next_test_on ? h("span", { class: control.test_due ? "text-danger" : null }, date(control.next_test_on), control.test_due ? " (overdue)" : "") : null],
      ])),
      directedBy(control), reliedOnBy(control),
      incidentsCard(control.incidents),
      customCard(control.custom),
      ownersCard(control, ctx)));
}

/** What third parties' reports leave to the organization, which this control does. */
function reliedOnBy(control) {
  const found = control.responsibilities ?? [];
  if (!found.length) return null;
  return card({ title: "Relied on by suppliers' reports" },
    h("ul", { class: "plain-list stack" }, found.map((row) => h("li", { class: "stack-sm" },
      h("div", {}, row.text),
      h("div", { class: "cell-sub" }, `${row.third_party.name} · ${row.kind_label ?? "Report"} ${row.document.ref}`,
        row.in_date ? "" : " · out of date", row.status === "in_place" ? "" : ` · ${row.status === "not_in_place" ? "not in place" : "does not apply"}`)))));
}

function directedBy(control) {
  const found = control.directed_by;
  return card({ title: "Directed by" },
    found.documents.length ? h("ul", { class: "plain-list stack-sm" }, found.documents.map((doc) => h("li", {},
      h("a", { class: "cell-main", href: `/documents/${doc.ref}` }, doc.name),
      h("div", { class: "cell-sub" }, [`${KINDS[doc.kind]} · ${doc.ref}`, doc.status === "retired" ? "retired" : doc.number ? `version ${doc.number} in force` : "not yet published", doc.note].filter(Boolean).join(" · ")))))
      : h("p", { class: "muted" }, "No document says it directs this control. A policy, standard, or procedure says so on its What it governs tab."),
    found.hidden ? h("p", { class: "subtle" }, `And ${found.hidden} more that you do not have access to.`) : null);
}

/** What the control helps to satisfy, framework by framework. Test it once; it counts in each. */
function requirementsTab(control, held, reload) {
  const base = `/api/v1/controls/${control.ref}/requirements`;
  const add = held.can_edit && control.status === "active"
    ? button("Map to a requirement", { kind: "btn-primary", iconName: "link", onclick: () => mapCrosswalk({ control, onDone: reload }) }) : null;
  const suggested = held.suggested && held.can_edit ? h("div", { class: "alert alert-info row" },
    h("span", { class: "grow" }, `The library suggests ${plural(held.suggested, "more requirement")} for a control like this one.`),
    button("Add them", { kind: "btn-sm", onclick: async () => {
      try {
        const done = await post(`${base}/suggested`);
        toast(`${plural(done.meta.added, "requirement")} mapped. Check that each one fits.`);
        reload();
      } catch (error) {
        toast(error.detail || "That did not work.");
      }
    } })) : null;
  if (!held.total) {
    return h("div", { class: "stack-lg" }, suggested, card({}, emptyState({ iconName: "framework", title: "Not mapped to any requirement yet",
      text: "Map this control to each requirement it helps to satisfy. It is then tested once and counts toward every one of them.", action: add })));
  }
  return h("div", { class: "stack-lg" }, suggested,
    h("div", { class: "row" }, h("p", { class: "muted grow" }, `Helps to satisfy ${plural(held.total, "requirement")} in ${plural(held.frameworks.length, "framework")}.`), add),
    held.frameworks.map((framework) => card({ title: framework.title, flush: true,
      actions: h("a", { href: `/frameworks/${framework.key}` }, "Open the framework") },
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Requirement"), h("th", { scope: "col" }, "Answers it"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Actions")))),
      h("tbody", {}, framework.requirements.map((item) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/frameworks/${framework.key}?r=${encodeURIComponent(item.code)}` },
          h("span", { class: "requirement-code" }, item.code), " ", item.title ?? ""),
        h("div", { class: "cell-sub" }, item.note ?? item.excerpt ?? "")),
        h("td", { class: "nowrap" }, coveragePill(item.coverage), item.source === "pack" ? h("div", { class: "cell-sub" }, "Suggested by the library") : null),
        h("td", { class: "nowrap" }, held.can_edit ? h("div", { class: "row-sm" },
          button("Change", { kind: "btn-sm btn-ghost", "aria-label": `Change how ${item.code} is mapped`, onclick: () => mapCrosswalk({ control, existing: { ...item, framework: framework.key }, onDone: reload }) }),
          button("Remove", { kind: "btn-sm btn-ghost", "aria-label": `Remove ${item.code}`, onclick: () => confirmAction({
            title: `Take ${item.code} off this control?`, text: "The control will no longer count toward it. The change is kept in the history.",
            confirmLabel: "Remove", danger: true,
            run: async () => {
              await del(`${base}/${item.id}`);
              toast(`${item.code} was removed.`);
              reload();
            } }) })) : null)))))))));
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
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : tab === "ratings" ? get(`${base}/ratings`, null, { fresh: true })
          : tab === "requirements" ? get(`${base}/requirements`, null, { fresh: true }) : null]);
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
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : tab === "ratings" ? ratingsTab(data.extra)
          : tab === "requirements" ? requirementsTab(control, data.extra, reload) : overview(control, ctx));
    },
  });
}
