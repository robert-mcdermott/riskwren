// A third party's page: what it is, what it provides, how much is at stake with it and why,
// and everything joined to it. Later parts of the program add their own tabs.

import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { relative } from "../core/format.js";
import { label, program as loadProgram, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { criticality, recordChip, statusPill } from "../components/record.js";
import { card, emptyState, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, linksCard, outside, ownersCard, prose, recordHeader, risksCard, stopsOf, tabBar, timeline } from "./record.js";

// The forms are fetched when someone first asks for them.
const editRecord = async (...args) => (await import("../components/record-forms.js")).editRecord(...args);
const openTiering = async (...args) => (await import("../components/tiering.js")).openTiering(...args);
const tieringDetail = async (...args) => (await import("../components/tiering.js")).tieringDetail(...args);

const TABS = [["overview", "Overview"], ["tiering", "Tiering"], ["diligence", "Due diligence"], ["assurance", "Assurance"], ["history", "History"]];
const assuranceTab = async (...args) => (await import("../components/assurance.js")).assuranceTab(...args);
const dueDiligenceTab = async (...args) => (await import("../components/third-party-dd.js")).dueDiligenceTab(...args);

/** A tier as a pill: the tier's name, and nothing louder; it is not a rating. */
export function tierPill(tierLabel) {
  return tierLabel ? pill(tierLabel, "info") : pill("Not tiered");
}

function tierCard(record, ctx) {
  const found = record.tiering;
  const act = record.can_tier ? button(found ? "Tier it again" : "Tier it", { kind: "btn-sm", iconName: "edit",
    onclick: () => openTiering(record, { onDone: ctx.reload }) }) : null;
  if (!found) {
    return card({ title: "Tier", actions: act }, h("p", { class: "muted" },
      "Not tiered yet. A few questions, partly answered from the inventory, set how much is at stake with it, and so how closely it is reviewed."));
  }
  return card({ title: "Tier", actions: act },
    h("div", { class: "row wrap" }, h("span", { class: "tier-mark" }, found.tier_label),
      found.tier !== found.suggested ? h("span", { class: "subtle" }, `The rules give ${found.suggested_label}`) : null),
    h("ul", { class: "plain-list stack-sm reasons" }, (found.tier === found.suggested ? found.reasons : []).map((reason) => h("li", {}, reason))),
    found.tier !== found.suggested && found.rationale ? h("p", {}, found.rationale) : null,
    h("p", { class: "subtle tier-by" }, `By ${found.by}, ${relative(found.at)}. `, h("a", { href: "?tab=tiering" }, "The answers")));
}

function servicesCard(record, ctx) {
  const add = record.can?.edit && record.status === "active" ? button("Add a service", { kind: "btn-sm", iconName: "plus", onclick: () =>
    editRecord("service", { vocab: ctx.vocab, units: ctx.units, preset: { third_party: { ref: record.ref, name: record.name }, org_unit_id: record.org_unit_id } }) }) : null;
  const rows = record.services ?? [];
  return card({ title: "Services", actions: add, flush: rows.length > 0 },
    rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Service"), h("th", { scope: "col" }, "Kind"), h("th", { scope: "col" }, "Data"), h("th", { scope: "col" }, "Status"))),
      h("tbody", {}, rows.map((row) => h("tr", {},
        h("td", {}, recordChip(row)),
        h("td", {}, label(ctx.vocab, "service_kinds", row.kind)),
        h("td", {}, row.data_class ? label(ctx.vocab, "data_classes", row.data_class) : h("span", { class: "subtle" }, "Not said")),
        h("td", {}, statusPill(row.status)))))))
      : h("p", { class: "muted" }, "What it provides is not on record. A service says which systems it reaches and which information it handles."));
}

const AGREEMENT_STATES = { in_force: ["In force", "ok"], notice: ["Notice due", "warn"], ending: ["Ending", "warn"], ended: ["Ended, still open", "danger"],
  upcoming: ["Not yet started", "info"], closed: ["Closed", ""] };

function agreementsCard(record) {
  const rows = record.agreements ?? [];
  return card({ title: "Agreements" },
    rows.length ? h("ul", { class: "plain-list stack-sm" }, rows.map((row) => h("li", { class: "row wrap" },
      h("span", { class: "grow" }, recordChip(row)), pill(...(AGREEMENT_STATES[row.state] ?? [row.state, ""])))))
      : h("p", { class: "muted" }, "No agreement on record names it. An agreement says who it is with on its own page."));
}

function overview(record, ctx) {
  const v = ctx.vocab;
  const unit = ctx.units.byId.get(record.org_unit_id);
  const glance = [
    ["Kind", label(v, "third_party_kinds", record.kind)],
    ["Unit", unit?.name],
    ["Criticality", criticality(v, record.criticality)],
    ["Data handled", record.data_class ? label(v, "data_classes", record.data_class) : null],
    ["Website", outside(record.website)],
  ];
  if (record.tags?.length) glance.push(["Tags", record.tags.join(", ")]);
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      record.summary ? card({ title: "About" }, prose(record.summary)) : null,
      record.notes ? card({ title: "Notes" }, prose(record.notes)) : null,
      tierCard(record, ctx), servicesCard(record, ctx), agreementsCard(record), risksCard(ctx), linksCard(record, ctx)),
    h("div", { class: "stack-lg" }, card({ title: "At a glance" }, facts(glance)), ownersCard(record, ctx)));
}

function tieringTab(record, data, ctx) {
  const holder = h("div", { class: "stack-lg" });
  const view = data.tiering;
  if (!view.tierings.length) {
    holder.append(emptyState({ iconName: "third_party", title: "Not tiered yet",
      text: "Tiering asks what it holds, how it reaches the organization, and what relies on it. The program's rules then give its tier, with the reasons.",
      action: record.can_tier ? button("Tier it", { kind: "btn-primary", onclick: () => openTiering(record, { onDone: ctx.reload, view }) }) : null }));
    return holder;
  }
  tieringDetail(view, { record, onTier: () => openTiering(record, { onDone: ctx.reload, view }) }).then((node) => holder.append(node));
  return holder;
}

export function thirdPartyPage(main, params) {
  const asked = query().get("tab");
  const tab = TABS.some(([key]) => key === asked) ? asked : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/third-parties/${params.ref}`;
      const [record, vocab, unitIndex, entries, programData, risks, tiers] = await Promise.all([
        get(base, null, { fresh: true }), vocabularies(), units(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null,
        loadProgram(), get("/api/v1/risks", { subject: params.ref, limit: 50 }, { fresh: true }),
        tab === "tiering" ? get(`${base}/tiering`, null, { fresh: true }) : null]);
      return { record: record.data, vocab, units: unitIndex, history: entries?.data ?? [], program: programData, risks: risks.data,
        tiering: tiers?.data ?? null };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const ctx = { vocab: data.vocab, units: data.units, program: data.program, risks: data.risks, reload };
      const edit = record.can?.edit ? button("Edit", { iconName: "edit", onclick: () =>
        editRecord("third_party", { record, vocab: data.vocab, units: data.units, onDone: reload }) }) : null;
      const badges = [statusPill(record.status), tierPill(record.tiering?.tier_label), criticality(data.vocab, record.criticality)];
      let body;
      if (tab === "history") body = card({ flush: true }, timeline(data.history));
      else if (tab === "tiering") body = tieringTab(record, data, ctx);
      else if (tab === "assurance") {
        body = h("div");
        assuranceTab(record, ctx).then((node) => body.append(node));
      } else if (tab === "diligence") {
        body = h("div");
        dueDiligenceTab(record, ctx).then((node) => body.append(node));
      }
      else body = overview(record, ctx);
      return h("div", { class: "stack" }, recordHeader(record, { badges, actions: edit }), stopsOf(record), tabBar(TABS, tab), body);
    },
  });
}
