// One inventory record: what it is, who answers for it, what it is connected to, and its history.

import { customCard } from "../components/custom-fields.js";
import { missingNote } from "../components/tidy.js";
import { del, get, patch, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, dateTime, relative } from "../core/format.js";
import { label, program as loadProgram, units, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { session } from "../core/session.js";
import { banner, field, select, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { peoplePicker } from "../components/people-picker.js";
import { criticality, hrefOf, recordChip, statusPill, TYPES } from "../components/record.js";
import { rating, standingPill } from "../components/risk.js";
import { toast } from "../components/toast.js";
import { alert, avatar, card, emptyState } from "../components/ui.js";
import { show } from "./page.js";

// The form is fetched when someone first asks to add or edit.
const editRecord = async (...args) => (await import("../components/record-forms.js")).editRecord(...args);

export function facts(pairs) {
  const shown = pairs.filter(([, value]) => value != null && value !== "" && !(Array.isArray(value) && !value.length));
  if (!shown.length) return h("p", { class: "muted" }, "Nothing recorded yet.");
  return h("dl", { class: "dl" }, shown.map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]));
}

export function prose(text) {
  return text ? h("p", { class: "prose" }, text) : null;
}

export function outside(url) {
  return url ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, url.replace(/^https?:\/\//, "")) : null;
}

function editOwners(record, ctx) {
  const owners = record.owners.map((owner) => ({ ...owner }));
  openOverlay({
    title: "Owners",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const kinds = ctx.vocab.owner_kinds.filter((item) => !item.retired).map((item) => [item.key, item.label]);
      const draw = () => {
        list.replaceChildren(...owners.map((owner, index) => {
          const kind = select("Capacity", kinds, { value: owner.kind });
          kind.input.setAttribute("aria-label", `Capacity of ${owner.name}`);
          kind.input.addEventListener("change", () => {
            owners[index].kind = kind.input.value;
          });
          return h("div", { class: "owner-row" }, avatar(owner.name),
            h("div", { class: "grow" }, h("div", { class: "cell-main" }, owner.name), h("div", { class: "cell-sub" }, owner.email)),
            kind.input,
            button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
              owners.splice(index, 1);
              draw();
            } }));
        }));
        if (!owners.length) list.replaceChildren(h("p", { class: "muted" }, "Nobody yet."));
      };
      draw();
      const picker = peoplePicker({ label: "Add a person",
        exclude: (account) => owners.some((owner) => owner.account_id === account.id),
        onPick: (account) => {
          owners.push({ account_id: account.id, name: account.display_name, email: account.email,
            kind: owners.some((o) => o.kind === "owner") ? "delegate" : "owner" });
          draw();
        } });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/${TYPES[record.type].path}/${record.ref}/owners`,
            { owners: owners.map((owner) => ({ account_id: owner.account_id, kind: owner.kind })) }) });
        if (done) {
          close();
          toast("The owners were saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "The owner answers for the record and keeps it current. A delegate can edit it too. A contact is someone to ask."),
        list, picker));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

// The kinds of record whose forms take external references.
const CARRIES = new Set(["process", "system", "third_party", "information", "risk", "control", "scope", "service"]);

/** Change what a record is called in other systems. */
function editExternal(record, ctx) {
  const systems = (ctx.vocab?.external_systems ?? []).filter((item) => !item.retired);
  const rows = record.external_refs.map((item) => ({ system: item.system, value: item.value }));
  openOverlay({
    title: "Known elsewhere as",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = h("div", { class: "alert alert-danger", role: "alert", hidden: true });
      const draw = () => {
        list.replaceChildren(...(rows.length ? rows.map((row, index) => h("div", { class: "owner-row" },
          h("select", { class: "select", "aria-label": `System ${index + 1}`, onchange: (event) => {
            row.system = event.target.value;
          } }, systems.map((item) => h("option", { value: item.key, selected: item.key === row.system }, item.label))),
          h("input", { class: "input", value: row.value, maxlength: 200, placeholder: "Identifier", "aria-label": `Identifier ${index + 1}`, oninput: (event) => {
            row.value = event.target.value;
          } }),
          button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove identifier ${index + 1}`, onclick: () => {
            rows.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "Nothing yet: an asset tag, a contract number, a ticket.")]));
      };
      draw();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        save.disabled = true;
        problem.hidden = true;
        try {
          await patch(`/api/v1/${TYPES[record.type].path}/${record.ref}`, { version: record.version, external_refs: rows.filter((row) => row.value.trim()) });
          close();
          toast("Saved.");
          ctx.reload();
        } catch (error) {
          problem.textContent = Object.values(error.fields ?? {}).join(" ") || error.detail || "That did not work.";
          problem.hidden = false;
        } finally {
          save.disabled = false;
        }
      });
      body.append(h("div", { class: "stack" }, problem, list,
        button("Add another", { iconName: "plus", kind: "btn-sm", onclick: () => {
          rows.push({ system: systems[0]?.key ?? "other", value: "" });
          draw();
        } }),
        h("p", { class: "subtle" }, "A record is found by these when searching.")));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** What a record is called in other systems, as links where the system has a pattern. */
export function externalCard(record, ctx) {
  const refs = record.external_refs;
  if (!refs || !CARRIES.has(record.type) || !(refs.length || record.can?.edit)) return null;
  return card({ title: "Known elsewhere as", actions: record.can?.edit ? button("Edit", { kind: "btn-sm", onclick: () => editExternal(record, ctx) }) : null },
    refs.length ? h("dl", { class: "dl" }, refs.map((item) => [h("dt", {}, item.label),
      h("dd", {}, item.url ? h("a", { href: item.url, target: "_blank", rel: "noopener noreferrer" }, item.value) : item.value)]))
      : h("p", { class: "muted" }, "No identifier in another system is recorded."));
}

/** Who answers for a record, beneath that what it is called elsewhere, and what committees
 * decided about it. */
export function ownersCard(record, ctx) {
  return [ownersOnly(record, ctx), externalCard(record, ctx), decisionsCard(record)];
}

const OUTCOMES = { noted: ["Noted", ""], approved: ["Approved", "ok"], declined: ["Declined", "danger"], deferred: ["Deferred", "warn"] };

/** What committees decided about a record, newest first. Nothing when there is nothing. */
export function decisionsCard(record) {
  const found = record.decisions ?? [];
  if (!found.length) return null;
  return card({ title: "Committee decisions" }, h("ul", { class: "plain-list stack" }, found.map((row) => h("li", { class: "stack-sm" },
    h("div", { class: "row wrap" }, h("a", { class: "grow", href: `/sessions/${row.session.ref}` }, `${row.session.committee}, ${date(row.session.held_on)}`),
      h("span", { class: `pill ${OUTCOMES[row.outcome]?.[1] ? `pill-${OUTCOMES[row.outcome][1]}` : ""}` }, OUTCOMES[row.outcome]?.[0] ?? row.outcome)),
    row.decision ? h("p", {}, row.decision) : null))));
}

function ownersOnly(record, ctx) {
  const canEdit = record.can?.edit;
  return card({ title: ctx.ownersTitle ?? "Owners", actions: canEdit ? button("Edit", { kind: "btn-sm", onclick: () => editOwners(record, ctx) }) : null },
    record.orphaned ? alert("warn", icon("alert"), h("div", {}, record.owners.some((o) => o.kind === "owner")
      ? "Its owner's account is disabled. Name a new owner." : "Nobody answers for this record. Name an owner.")) : null,
    record.owners.length ? h("div", { class: "stack" }, record.owners.map((owner) => h("div", { class: "row" },
      avatar(owner.name), h("div", { class: "grow" }, h("div", { class: "cell-main" }, owner.name),
        h("div", { class: "cell-sub" }, label(ctx.vocab, "owner_kinds", owner.kind))))))
      : h("p", { class: "muted" }, "Nobody is named."));
}

// The kinds of link that may start at this type of record, each with the types it may reach.
function linkChoices(vocab, type) {
  const out = [];
  for (const kind of vocab.link_kinds ?? []) {
    if (kind.retired) continue;
    for (const [from, to] of kind.between ?? []) {
      if (from === type && TYPES[to]) out.push({ relation: kind.key, to, text: `${kind.label} ${TYPES[to].article}` });
    }
  }
  return out;
}

function addLink(record, ctx) {
  const choices = linkChoices(ctx.vocab, record.type);
  openOverlay({
    title: "Add a link",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const how = select("This " + TYPES[record.type].noun, choices.map((choice, index) => [index, choice.text.toLowerCase()]), { value: 0 });
      const search = h("input", { class: "input", type: "search", placeholder: "Name or reference", "aria-label": "Find a record" });
      const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Records found" });
      const note = field("Note", { hint: "Optional. What the link means here, in a few words." });
      const chosen = h("div", {});
      let target = null;
      let latest = 0;
      const find = async () => {
        const choice = choices[Number(how.input.value)];
        const mine = ++latest;
        const found = (await get(`/api/v1/${TYPES[choice.to].path}`, { q: search.value.trim(), sort: "name", limit: 8, status: "active" }, { fresh: true })).data;
        if (mine !== latest) return;
        const offered = found.filter((r) => r.ref !== record.ref);
        results.replaceChildren(...(offered.length ? offered.map((r) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
          target = r;
          chosen.replaceChildren(h("div", { class: "row" }, recordChip(r, { link: false }),
            button("Change", { kind: "btn-ghost btn-sm", onclick: () => {
              target = null;
              chosen.replaceChildren();
              search.hidden = false;
              find();
            } })));
          results.replaceChildren();
          search.hidden = true;
        } }, icon(TYPES[choice.to].iconName), h("span", {}, h("span", { class: "cell-main" }, r.name), h("span", { class: "cell-sub" }, ` ${r.ref}`))))
          : [h("div", { class: "subtle pick-none" }, `No ${TYPES[choice.to].nouns} match. Add it to the inventory first.`)]));
      };
      let timer = null;
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(find, 180);
      });
      how.input.addEventListener("change", () => {
        target = null;
        chosen.replaceChildren();
        search.hidden = false;
        find();
      });
      find();
      const save = button("Add link", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        if (!target) {
          problem.textContent = "Choose the record to link to.";
          problem.hidden = false;
          return;
        }
        const choice = choices[Number(how.input.value)];
        const done = await submit({ button: save, banner: problem, fields: { note },
          run: () => post(`/api/v1/${TYPES[record.type].path}/${record.ref}/links`,
            { relation: choice.relation, to: target.ref, note: note.input.value || null }) });
        if (done) {
          close();
          toast("The link was added.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, how.node,
        h("div", { class: "field" }, h("div", { class: "label" }, "Which one"), chosen, search, results), note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function linksCard(record, ctx) {
  const canEdit = record.can?.edit;
  const { outgoing, incoming, hidden } = record.links;
  const mayStart = linkChoices(ctx.vocab, record.type).length > 0;
  const row = (entry) => h("div", { class: "link-row" },
    h("span", { class: "link-label" }, entry.label),
    h("div", { class: "grow" }, recordChip(entry.record), entry.note ? h("div", { class: "cell-sub" }, entry.note) : null),
    entry.record.criticality ? criticality(ctx.vocab, entry.record.criticality) : null,
    canEdit ? button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove the link to ${entry.record.name}`, onclick: () =>
      confirmAction({ title: "Remove this link?", text: `${record.name} will no longer be shown as linked to ${entry.record.name}. The change stays in the history.`,
        confirmLabel: "Remove", run: async () => {
          await del(`/api/v1/${TYPES[record.type].path}/${record.ref}/links/${entry.id}`);
          toast("The link was removed.");
          ctx.reload();
        } }) }) : null);
  const all = [...outgoing, ...incoming];
  return card({ title: "Links", actions: canEdit && mayStart ? button("Add a link", { kind: "btn-sm", iconName: "link", onclick: () => addLink(record, ctx) }) : null },
    all.length ? h("div", {}, all.map(row)) : h("p", { class: "muted" }, "Not linked to anything yet. Links show what this relies on, and what relies on it."),
    hidden ? h("p", { class: "subtle" }, `And ${hidden} more that you do not have access to.`) : null);
}

/** The risks that concern this record, as far as the viewer may see them. */
export function risksCard(ctx) {
  const risks = ctx.risks;
  return card({ title: "Risks", flush: risks.length > 0 },
    risks.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "Residual"), h("th", { scope: "col" }, "Standing"))),
      h("tbody", {}, risks.map((risk) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: hrefOf(risk.ref) }, risk.name), h("div", { class: "cell-sub" }, risk.ref)),
        h("td", {}, rating(ctx.program, risk.ratings.residual.rating)),
        h("td", {}, standingPill(risk.standing)))))))
      : h("p", { class: "muted" }, "No risk has been raised that concerns this. Raise one from the register and attach it here."));
}

function overview(record, ctx) {
  const v = ctx.vocab;
  const meta = TYPES[record.type];
  const unit = ctx.units.byId.get(record.org_unit_id);
  const about = [record.summary ? card({ title: "About" }, prose(record.summary)) : null];
  if (record.type === "process" && record.purpose) about.push(card({ title: "Purpose" }, prose(record.purpose)));
  if (record.type === "third_party" && record.notes) about.push(card({ title: "Notes" }, prose(record.notes)));
  if (record.type === "information" && (record.held_in || record.shared_with)) {
    about.push(card({ title: "Where it is, and who has it" }, facts([["Held in", record.held_in ? prose(record.held_in) : null],
      ["Shared with", record.shared_with ? prose(record.shared_with) : null], ["Under", record.agreement]])));
  }
  const glance = [
    ["Kind", label(v, meta.kinds, record.kind)],
    ["Unit", unit?.name],
    ["Criticality", criticality(v, record.criticality)],
    ["Data handled", record.data_class ? label(v, "data_classes", record.data_class) : null],
  ];
  if (record.type === "system") {
    glance.push(["Hosting", label(v, "hosting", record.hosting)], ["Lifecycle", label(v, "lifecycles", record.lifecycle)], ["Address", outside(record.url)]);
  }
  if (record.type === "third_party") glance.push(["Website", outside(record.website)]);
  if (record.third_party) glance.unshift(["Provided by", recordChip(record.third_party)]);
  if (record.tags?.length) glance.push(["Tags", record.tags.join(", ")]);
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" }, about, risksCard(ctx), linksCard(record, ctx)),
    h("div", { class: "stack-lg" }, card({ title: "At a glance" }, facts(glance)), customCard(record.custom), ownersCard(record, ctx)));
}

export function timeline(entries) {
  if (!entries.length) return emptyState({ iconName: "history", title: "No history yet" });
  return h("ol", { class: "timeline" }, entries.map((entry) => h("li", {},
    h("div", { class: "timeline-dot", "aria-hidden": "true" }),
    h("div", { class: "grow" },
      h("div", { class: "row wrap" }, h("span", { class: "cell-main" }, entry.title),
        h("span", { class: "muted" }, `by ${entry.actor}`),
        h("time", { class: "subtle spacer", datetime: entry.at, title: dateTime(entry.at) }, relative(entry.at))),
      entry.lines.length ? h("dl", { class: "changes" }, entry.lines.map((line) => [
        h("dt", {}, line.label),
        h("dd", {}, line.before != null ? h("del", {}, String(line.before)) : h("span", { class: "subtle" }, "empty"),
          h("span", { "aria-hidden": "true" }, " → "), h("span", { class: "sr-only" }, " became "),
          line.after != null ? h("ins", {}, String(line.after)) : h("span", { class: "subtle" }, "empty")),
      ])) : null))));
}

// The kinds of record a dossier is taken of: a ZIP of everything known, with a manifest that verifies.
const DOSSIERS = new Set(["scope", "risk", "third_party"]);

/** The top of every record page: where it came from, what it is, and its badges. */
export function recordHeader(record, { badges = [], actions = null } = {}) {
  const meta = TYPES[record.type];
  return [
    h("a", { class: "back-link", href: `/${meta.path}` }, icon("chevron-left", "icon icon-sm"), meta.plural),
    h("header", { class: "record-header" },
      h("div", { class: "record-icon", "data-record": record.type }, icon(meta.iconName, "icon icon-lg")),
      h("div", { class: "grow" },
        h("div", { class: "eyebrow" }, `${meta.label} · ${record.ref}`),
        h("h1", { tabindex: "-1" }, record.name),
        h("div", { class: "row-sm wrap record-badges" }, badges,
          record.restricted ? h("span", { class: "pill" }, icon("lock"), "Restricted") : null,
          h("span", { class: "subtle" }, `Updated ${relative(record.updated_at)}`),
          // A reporter who sees only their report is not offered the views of the whole record.
          record.everything === false ? null : h("a", { class: "connections-link", href: `/graph/${record.ref}` }, icon("link", "icon icon-sm"), "Connections"),
          record.everything === false ? null : h("a", { class: "connections-link", href: `/as-of/${record.ref}` }, icon("history", "icon icon-sm"), "As of a date"),
          DOSSIERS.has(record.type) ? h("a", { class: "connections-link", href: `/api/v1/dossiers/${record.ref}`, download: "" }, icon("download", "icon icon-sm"), "Dossier") : null,
          // The assistant, only when it is turned on: its code is loaded when it is used.
          session()?.assistant && record.everything !== false && !record.restricted
            ? h("button", { type: "button", class: "link-button connections-link", onclick: async () => (await import("../components/assistant.js")).summarize(record) }, icon("document", "icon icon-sm"), "Summarize")
            : null)),
      actions),
    missingNote(record),
  ];
}

export function tabBar(tabs, current) {
  return h("div", { class: "tabs", role: "tablist" }, tabs.map(([key, text]) => h("button", { type: "button", class: "tab", role: "tab",
    "aria-selected": String(current === key), onclick: () => setQuery({ tab: key === tabs[0][0] ? null : key }, { replace: false }) }, text)));
}

/** Where information is shared and no agreement covers it: fetched only when there is any. */
export function stopsOf(record) {
  if (!record.stops?.length) return null;
  const holder = h("div");
  import("../components/stops.js").then(({ stopsBanner }) => holder.append(stopsBanner(record.stops)));
  return holder;
}

// Resilience: a process's needs, and what a system or service delivers.
const MORE = { process: ["impact", "Business impact"], system: ["recovery", "Recovery"], service: ["recovery", "Recovery"], site: ["recovery", "Recovery"] };

// Privacy impact: for a process or a system whose data class needs an assessment.
const PRIVACY = new Set(["process", "system"]);

export function recordPage(main, type, params) {
  const meta = TYPES[type];
  const more = MORE[type];
  const wanted = query().get("tab");
  const tab = wanted === "history" || (more && wanted === more[0]) || (PRIVACY.has(type) && wanted === "privacy") ? wanted : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/${meta.path}/${params.ref}`;
      const [record, vocab, unitIndex, entries, programData, risks] = await Promise.all([
        get(base, null, { fresh: true }), vocabularies(), units(),
        tab === "overview" || tab === "privacy" ? null : get(`${base}/${tab}`, null, { fresh: true }),
        loadProgram(), get("/api/v1/risks", { subject: params.ref, limit: 50 }, { fresh: true })]);
      const views = more && tab === more[0] ? await import("../components/resilience.js") : null;
      const privacy = tab === "privacy" ? await import("../components/privacy.js") : null;
      return { record: record.data, vocab, units: unitIndex, history: entries?.data ?? [], program: programData, risks: risks.data, views, privacy };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const ctx = { vocab: data.vocab, units: data.units, program: data.program, risks: data.risks, reload };
      const edit = record.can?.edit ? button("Edit", { iconName: "edit", onclick: () =>
        editRecord(type, { record, vocab: data.vocab, units: data.units, onDone: reload }) }) : null;
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [statusPill(record.status), criticality(data.vocab, record.criticality)], actions: edit }),
        stopsOf(record),
        tabBar([["overview", "Overview"], ...(more ? [more] : []), ...(record.privacy_impact?.state ? [["privacy", "Privacy"]] : []), ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history))
          : data.privacy ? data.privacy.privacyTab(record, reload)
            : data.views ? data.views.resilienceTab(type, record, data.history, reload) : overview(record, ctx));
    },
  });
}
