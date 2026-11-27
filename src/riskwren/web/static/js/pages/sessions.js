// Reports → Committee sessions: a risk or compliance committee's meetings, each with an agenda
// drawn from the register, the decision taken on each item, and the minutes.

import { del, get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { documentText } from "../components/document.js";
import { exportButton } from "../components/exchange.js";
import { banner, field, section, select, submit } from "../components/form.js";
import { recordPicker } from "../components/issue.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { recordChip } from "../components/record.js";
import { listTools } from "../components/tidy.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, pager, searchBox, sortHeader } from "./records.js";

const STATUS = { planned: ["Planned", "info"], held: ["Held", "ok"], cancelled: ["Cancelled", ""] };
const OUTCOMES = { noted: ["Noted", ""], approved: ["Approved", "ok"], declined: ["Declined", "danger"], deferred: ["Deferred", "warn"] };
const statusOf = (status) => pill(STATUS[status]?.[0] ?? status, STATUS[status]?.[1] ?? "");
const outcomeOf = (outcome) => pill(OUTCOMES[outcome]?.[0] ?? outcome, OUTCOMES[outcome]?.[1] ?? "");
const mayAdd = () => can("lead") || can("manage");
const AGENDA_TYPES = ["risk", "issue", "exception", "control", "document", "agreement", "scope", "objective", "assessment"];

function sessionForm({ record = null, unitIndex, onDone }) {
  openOverlay({ title: record ? `Edit ${record.ref}` : "Plan a session", subtitle: record ? null : "A meeting of a risk or compliance committee. Its agenda is drawn from the register.",
    render: (body, footer, close) => {
      const name = field("Name", { value: record?.name ?? "", required: true, maxlength: 200, hint: "Such as “Risk committee, December 2026”." });
      const committee = field("Committee", { value: record?.committee ?? "", required: true, maxlength: 120, hint: "Such as “Risk committee” or “Security steering group”." });
      const held = field("Meets on", { type: "date", value: record?.held_on ?? "", required: true });
      const unit = select("Unit", unitOptions(unitIndex.tree, { blank: record ? null : "Choose…" }), { value: record?.org_unit_id ?? "", required: true, hint: "The unit the committee answers to." });
      const summary = field("What it is for", { type: "textarea", rows: 2, value: record?.summary ?? "" });
      const problem = banner();
      const save = button(record ? "Save" : "Plan it", { kind: "btn-primary" });
      const values = () => ({ name: name.input.value, committee: committee.input.value, held_on: held.input.value || null,
        org_unit_id: unit.input.value ? Number(unit.input.value) : null, summary: summary.input.value });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { name, committee, held_on: held, org_unit_id: unit, summary }, banner: problem,
          run: () => (record ? patch(`/api/v1/sessions/${record.ref}`, { ...values(), version: record.version }) : post("/api/v1/sessions", values())) });
        if (!done) return;
        close();
        toast(record ? "Saved." : `${done.data.ref} is planned. Build its agenda.`);
        if (record) onDone(); else navigate(`/sessions/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("The meeting", name.node, committee.node, h("div", { class: "grid-2" }, held.node, unit.node), summary.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function sessionList(main) {
  return show(main, {
    title: "Committee sessions",
    load: async () => {
      const [page, unitIndex] = await Promise.all([get("/api/v1/sessions", { sort: "-held_on", ...Object.fromEntries(query()) }, { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data) => {
      const rows = data.page.data;
      const add = () => sessionForm({ unitIndex: data.units, onDone: () => {} });
      const search = searchBox("Search sessions");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search), listTools(),
        filterSelect("when", [["", "Any time"], ["upcoming", "Coming up"], ["past", "Past"]], "When"),
        filterSelect("status", [["", "Any status"], ...Object.entries(STATUS).map(([key, [text]]) => [key, text])], "Status"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Session", "name", "-held_on"), h("th", { scope: "col" }, "Committee"), sortHeader("Meets on", "held_on", "-held_on"),
          h("th", { scope: "col" }, "Agenda"), h("th", { scope: "col" }, "Status"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/sessions/${row.ref}` }, row.name), h("div", { class: "cell-sub" }, row.ref)),
          h("td", {}, row.committee), h("td", { class: "nowrap" }, date(row.held_on)),
          h("td", {}, row.items ? `${plural(row.items, "item")}, ${row.decided} decided` : h("span", { class: "subtle" }, "Nothing yet")),
          h("td", {}, statusOf(row.status)))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "session", title: "No sessions yet", text: "Plan a committee's next meeting, then put on its agenda the risks, exceptions, and issues it must decide.",
            action: mayAdd() ? button("Plan a session", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Committee sessions",
          lede: "The meetings of the risk and compliance committees: an agenda drawn from the register, the decision taken on each item, which then shows on the record, and the minutes.",
          actions: [mayAdd() ? button("Plan a session", { kind: "btn-primary", iconName: "plus", onclick: add }) : null, exportButton("sessions")] }),
        bar, card({ title: plural(data.page.meta.total, "session"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

// --- One session ------------------------------------------------------------------------------

function addItem(record, reload) {
  openOverlay({ title: "Put an item on the agenda", subtitle: "A record from the register, or a topic of its own.",
    render: (body, footer, close) => {
      const chosen = [];
      const picker = recordPicker({ types: AGENDA_TYPES, chosen, label: "From the register", placeholder: "Search risks, issues, exceptions, controls, documents…",
        empty: "None chosen. Choose one, or give the item a title of its own below." });
      const title = field("Or a topic of its own", { maxlength: 300, hint: "Such as “The year's audit plan”." });
      const note = field("What the committee is asked", { type: "textarea", rows: 3, hint: "Such as “Accept the risk until the second freezer is in, or fund it now?”." });
      const problem = banner();
      const save = button("Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const values = { record: chosen[0]?.ref ?? null, title: title.input.value || null, note: note.input.value || null };
        const done = await submit({ button: save, fields: { title, note }, banner: problem, run: () => post(`/api/v1/sessions/${record.ref}/items`, values) });
        if (!done) return;
        close();
        toast("Added to the agenda.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, picker, title.node, note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function decideItem(record, item, reload) {
  openOverlay({ title: "Record the decision", subtitle: item.title,
    render: (body, footer, close) => {
      const outcome = select("What the committee did", Object.entries(OUTCOMES).map(([key, [text]]) => [key, text]), { value: item.outcome ?? "approved" });
      const decision = field("What was decided", { type: "textarea", rows: 4, value: item.decision ?? "",
        hint: "With any condition, owner, or date. It shows on the record the item is about, and its owners are told." });
      const problem = banner();
      const save = button("Record it", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { outcome, decision }, banner: problem,
          run: () => post(`/api/v1/sessions/${record.ref}/items/${item.id}/decision`, { outcome: outcome.input.value, decision: decision.input.value || null }) });
        if (!done) return;
        close();
        toast("Recorded.");
        reload();
      });
      body.append(h("div", { class: "stack" }, problem, item.note ? h("p", { class: "muted" }, item.note) : null, outcome.node, decision.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function agendaTab(record, reload) {
  const items = record.items_list;
  const act = (path, body, said) => async () => {
    await post(`/api/v1/sessions/${record.ref}/items/${path}`, body);
    if (said) toast(said);
    reload();
  };
  return card({ title: items.length ? `Agenda (${items.length})` : "Agenda", flush: items.length > 0,
    actions: record.can.edit ? button("Add an item", { kind: "btn-sm", iconName: "plus", onclick: () => addItem(record, reload) }) : null },
  items.length ? h("ol", { class: "plain-list rows agenda" }, items.map((item, index) => h("li", { class: "stack-sm" },
    h("div", { class: "row agenda-row" },
      h("span", { class: "agenda-number", "aria-hidden": "true" }, `${index + 1}.`),
      h("div", { class: "grow stack-sm" },
        item.subject?.open ? recordChip(item.subject) : h("strong", {}, item.title),
        item.note ? h("p", { class: "muted" }, item.note) : null),
      record.can.edit && record.status === "planned" ? h("div", { class: "row-sm" },
        index ? button("Up", { kind: "btn-ghost btn-sm", "aria-label": `Move item ${index + 1} up`, onclick: act(`${item.id}/move`, { up: true }) }) : null,
        index < items.length - 1 ? button("Down", { kind: "btn-ghost btn-sm", "aria-label": `Move item ${index + 1} down`, onclick: act(`${item.id}/move`, { up: false }) }) : null,
        !item.outcome ? button("Take off", { kind: "btn-ghost btn-sm", "aria-label": `Take item ${index + 1} off`, onclick: () => confirmAction({
          title: "Take this item off the agenda?", text: item.title, confirmLabel: "Take it off",
          run: async () => { await del(`/api/v1/sessions/${record.ref}/items/${item.id}`); reload(); } }) }) : null) : null),
    item.outcome ? h("div", { class: "decision" }, h("div", { class: "row wrap" }, outcomeOf(item.outcome), h("span", { class: "cell-sub" }, `Recorded by ${item.decided_by}`),
      record.can.decide ? button("Change", { kind: "btn-ghost btn-sm", onclick: () => decideItem(record, item, reload) }) : null),
    item.decision ? h("p", {}, item.decision) : null)
      : record.can.decide ? h("div", {}, button("Record the decision", { kind: "btn-sm", onclick: () => decideItem(record, item, reload) })) : null)))
    : h("p", { class: "muted" }, "Nothing on the agenda yet. Add the risks, exceptions, and issues the committee must decide, or topics of their own."));
}

function minutesTab(record, reload) {
  if (!record.can.edit) {
    return h("div", { class: "stack-lg" },
      record.attendees ? card({ title: "Present" }, h("p", {}, record.attendees)) : null,
      card({ title: "Minutes" }, record.minutes ? h("article", { class: "doc-body" }, documentText(record.minutes, { withContents: false })) : h("p", { class: "muted" }, "No minutes are recorded yet.")));
  }
  const attendees = field("Present", { value: record.attendees ?? "", hint: "Who attended, and who sent apologies." });
  const minutes = field("Minutes", { type: "textarea", rows: 14, value: record.minutes ?? "", class: "textarea doc-editor",
    hint: "# for a heading, - for a list, **bold**. The decisions on each item are kept with the item; the minutes say the rest." });
  const problem = banner();
  const save = button("Save the minutes", { kind: "btn-primary" });
  save.addEventListener("click", async () => {
    const done = await submit({ button: save, fields: { attendees, minutes }, banner: problem,
      run: () => patch(`/api/v1/sessions/${record.ref}`, { attendees: attendees.input.value || null, minutes: minutes.input.value || null, version: record.version }) });
    if (!done) return;
    toast("Saved.");
    reload();
  });
  return card({ title: "Minutes" }, h("div", { class: "stack" }, problem, attendees.node, minutes.node,
    record.minutes ? h("details", { class: "disclosure" }, h("summary", {}, "As they read"), h("article", { class: "doc-body" }, documentText(record.minutes, { withContents: false }))) : null,
    h("div", {}, save)));
}

export function sessionPage(main, params) {
  const tab = ["minutes", "history"].includes(query().get("tab")) ? query().get("tab") : "agenda";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/sessions/${params.ref}`;
      const [record, unitIndex, vocab, entries] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { record: record.data, units: unitIndex, vocab, history: entries?.data ?? [] };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const items = record.items_list;
      const decided = items.filter((item) => item.outcome).length;
      const actions = record.can.edit ? h("div", { class: "row-sm wrap" },
        button("Edit", { iconName: "edit", onclick: () => sessionForm({ record, unitIndex: data.units, onDone: reload }) }),
        record.status === "planned" ? button("Record that it was held", { onclick: async () => { await post(`/api/v1/sessions/${record.ref}/held`); toast("Recorded."); reload(); } }) : null,
        record.status === "planned" && !decided ? button("Cancel it", { kind: "btn-ghost", onclick: () => confirmAction({ title: `Cancel ${record.name}?`, text: "Its agenda is kept on record.",
          confirmLabel: "Cancel it", danger: true, run: async () => { await post(`/api/v1/sessions/${record.ref}/cancel`, {}); reload(); } }) }) : null) : null;
      const body = tab === "history" ? card({ flush: true }, timeline(data.history)) : tab === "minutes" ? minutesTab(record, reload) : agendaTab(record, reload);
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [statusOf(record.status)], actions }),
        tabBar([["agenda", items.length ? `Agenda (${decided} of ${items.length} decided)` : "Agenda"], ["minutes", "Minutes"], ["history", "History"]], tab),
        h("div", { class: "split" }, h("div", { class: "stack-lg" },
          record.status === "cancelled" ? alert("info", icon("info"), h("div", {}, "This session was cancelled.")) : null, body),
        h("div", { class: "stack-lg" },
          card({ title: "At a glance" }, facts([
            ["Committee", record.committee],
            ["Meets on", date(record.held_on)],
            ["Status", statusOf(record.status)],
            ["Unit", data.units.byId.get(record.org_unit_id)?.name],
            ["Decided", items.length ? `${decided} of ${plural(items.length, "item")}` : null],
          ])),
          ownersCard(record, { vocab: data.vocab, units: data.units, reload }))));
    },
  });
}
