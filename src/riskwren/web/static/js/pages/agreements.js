// Compliance → Agreements: what the organization has promised others, with its dates, what
// each covers, and the requirements it imposes on the scopes that hold what it covers.

import { get, patch, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { exportButton } from "../components/exchange.js";
import { banner, checkbox, field, section, select, submit } from "../components/form.js";
import { recordPicker } from "../components/issue.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { recordChip } from "../components/record.js";
import { listTools, similarHint } from "../components/tidy.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

export const KINDS = {
  award: "Award terms", data_use: "Data use agreement", business_associate: "Business associate agreement",
  contract: "Contract", confidentiality: "Confidentiality agreement", memorandum: "Memorandum of understanding", other: "Other",
};
const STATES = {
  in_force: ["In force", "ok"], notice: ["Notice due", "warn"], ending: ["Ending", "warn"], ended: ["Ended, still open", "danger"],
  upcoming: ["Not yet started", "info"], closed: ["Closed", ""],
};
const mayAdd = () => can("steward") || can("lead");

export function agreementState(row) {
  const [text, tone] = STATES[row.state] ?? [row.state, ""];
  if (row.state === "notice" && row.notice_on) return pill(`Notice due by ${date(row.notice_on)}`, tone);
  if (row.state === "ending" && row.ends_on) return pill(`Ends ${date(row.ends_on)}`, tone);
  return pill(text, tone);
}

function agreementForm({ record = null, unitIndex, onDone }) {
  openOverlay({
    title: record ? `Edit ${record.ref}` : "Add an agreement",
    subtitle: record ? null : "An award's terms, a data use agreement, a contract: who it is with, when it runs, and what it covers.",
    render: async (body, footer, close) => {
      const sources = (await get("/api/v1/frameworks")).data.filter((item) => item.status === "active");
      const name = field("Name", { value: record?.name ?? "", required: true, maxlength: 200, hint: "As people know it, such as “Cohort data use agreement”." });
      const kind = select("Kind", [["", "Choose…"], ...Object.entries(KINDS)], { value: record?.kind ?? "", required: true });
      const parties = field("With", { value: record?.parties ?? "", required: true, maxlength: 300, hint: "The other party or parties: a sponsor, a data provider, a supplier." });
      const reference = field("Their reference", { value: record?.reference ?? "", maxlength: 120, hint: "The award number, or the number on the signed copy." });
      const unit = select("Unit", unitOptions(unitIndex.tree, { blank: record ? null : "Choose…" }), { value: record?.org_unit_id ?? "", required: true, hint: "The unit that answers for it." });
      const summary = field("What it is for", { type: "textarea", rows: 2, value: record?.summary ?? "" });
      const starts = field("Starts", { type: "date", value: record?.starts_on ?? "" });
      const ends = field("Ends", { type: "date", value: record?.ends_on ?? "", hint: "Leave empty for one that runs until it is ended." });
      const notice = field("Notice, in days", { type: "number", min: 0, max: 730, inputmode: "numeric", value: record?.notice_days ?? "",
        hint: "How long before it ends notice must be given, to end it or to keep it going." });
      const renews = checkbox("It carries on by itself unless notice is given", { checked: record?.renews ?? false });
      const terms = select("Its terms", [["", "Not entered"], ...sources.map((item) => [item.key, item.title])], { value: record?.terms?.key ?? "",
        hint: "The requirements it imposes, as a framework: its own terms, entered under Frameworks, or a published one it names. Every scope that holds what it covers is held to them." });
      const url = field("Where the signed copy is kept", { type: "url", value: record?.url ?? "", placeholder: "https://" });
      const problem = banner();
      const save = button(record ? "Save" : "Add", { kind: "btn-primary" });
      const values = () => ({
        name: name.input.value, kind: kind.input.value || null, parties: parties.input.value, reference: reference.input.value || null,
        org_unit_id: unit.input.value ? Number(unit.input.value) : null, summary: summary.input.value,
        starts_on: starts.input.value || null, ends_on: ends.input.value || null,
        notice_days: notice.input.value === "" ? null : Number(notice.input.value), renews: renews.input.checked,
        framework: terms.input.value || null, url: url.input.value || null,
      });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { name, kind, parties, reference, org_unit_id: unit, summary, starts_on: starts, ends_on: ends, notice_days: notice, framework: terms, url }, banner: problem,
          run: () => (record ? patch(`/api/v1/agreements/${record.ref}`, { ...values(), version: record.version }) : post("/api/v1/agreements", values())) });
        if (!done) return;
        close();
        if (record) {
          toast("Saved.");
          onDone(done.data);
        } else {
          toast(`${done.data.ref} was added. Say what it covers.`);
          navigate(`/agreements/${done.data.ref}`);
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("What it is", name.node, similarHint("agreement", name.input, { unit: () => unit.input.value, apartFrom: record?.ref }),
          h("div", { class: "grid-2" }, kind.node, unit.node), parties.node, reference.node, summary.node),
        section("When it runs", h("div", { class: "grid-2" }, starts.node, ends.node), notice.node, renews.node),
        section("What it imposes", terms.node, url.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function agreementList(main) {
  return show(main, {
    title: "Agreements",
    load: async () => {
      const params = Object.fromEntries(query());
      const [page, unitIndex] = await Promise.all([get("/api/v1/agreements", { sort: "ends_on", ...params }, { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data) => {
      const rows = data.page.data;
      const add = () => agreementForm({ unitIndex: data.units, onDone: () => {} });
      const search = searchBox("Search agreements");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search), listTools(),
        filterSelect("kind", [["", "Any kind"], ...Object.entries(KINDS)], "Kind"),
        filterSelect("state", [["", "Any state"], ["in_force", "In force"], ["ending", "Ending within 60 days"], ["ended", "Ended, still open"], ["upcoming", "Not yet started"]], "State"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        filterSelect("status", [["", "Open"], ["closed", "Closed"]], "Status"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Agreement", "name", "ends_on"), h("th", { scope: "col" }, "With"), h("th", { scope: "col" }, "Its terms"),
          h("th", { scope: "col" }, "Owner"), sortHeader("Ends", "ends_on", "ends_on"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/agreements/${row.ref}` }, row.name),
            h("div", { class: "cell-sub" }, [row.ref, KINDS[row.kind], row.reference].filter(Boolean).join(" · "))),
          h("td", {}, row.parties),
          h("td", {}, row.framework ? h("a", { href: `/frameworks/${row.framework.key}` }, row.framework.title) : h("span", { class: "subtle" }, "Not entered")),
          ownerCell(row),
          h("td", { class: "nowrap" }, row.ends_on ? date(row.ends_on) : h("span", { class: "subtle" }, "Runs on"), h("div", {}, agreementState(row))))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "agreement", title: "No agreements yet", text: "Add the awards, data use agreements, and contracts that bind the organization, with their dates.",
            action: mayAdd() ? button("Add an agreement", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Compliance", title: "Agreements",
          lede: "What the organization has promised others: who each is with, when it runs and must be renewed, what it covers, and the requirements it imposes on the scopes that hold what it covers.",
          actions: [mayAdd() ? button("Add an agreement", { kind: "btn-primary", iconName: "plus", onclick: add }) : null, exportButton("agreements")] }),
        bar, card({ title: plural(data.page.meta.total, "agreement"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

// --- One agreement ---------------------------------------------------------------------------

function partiesForm(record, reload) {
  openOverlay({ title: "Who it is with", subtitle: "The third parties it binds. What it covers is shared with them under it.",
    render: (body, footer, close) => {
      const chosen = (record.with ?? []).map((each) => ({ ...each, type: "third_party" }));
      const picker = recordPicker({ types: ["third_party"], chosen, label: "Add a third party", placeholder: "Search third parties", empty: "Nobody yet." });
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/agreements/${record.ref}/parties`, { parties: chosen.map((each) => each.ref) }) });
        if (!done) return;
        close();
        toast("Saved.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, picker));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function coversForm(record, reload) {
  openOverlay({ title: "What it covers", subtitle: "The systems, information, services, and scopes it binds. Every scope that holds one of them, or is one, is held to its terms.",
    render: (body, footer, close) => {
      const chosen = record.covered.records.map((each) => ({ ...each }));
      const picker = recordPicker({ types: ["system", "information", "service", "scope"], chosen, label: "Add a system, information, a service, or a scope",
        placeholder: "Search by name or reference", empty: "Nothing yet." });
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/agreements/${record.ref}/covers`, { covers: chosen.map((each) => each.ref) }) });
        if (!done) return;
        close();
        toast("Saved.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, picker,
        record.covered.hidden ? h("p", { class: "subtle" }, `It also covers ${plural(record.covered.hidden, "record")} you do not have access to. Saving leaves out what you cannot see.`) : null));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function closeBox(record, reload) {
  openOverlay({ title: `Close ${record.ref}?`, subtitle: "It has ended, was ended early, or was replaced. What it imposed leaves the scopes that held it because of it.",
    render: (body, footer, done) => {
      const note = field("Why", { type: "textarea", rows: 3, required: true, hint: "Such as “Ended on its date and not renewed”, or “Replaced by AGR-0007”." });
      const problem = banner();
      const go = button("Close it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const ok = await submit({ button: go, fields: { note }, banner: problem, run: () => post(`/api/v1/agreements/${record.ref}/close`, { note: note.input.value }) });
        if (!ok) return;
        done();
        toast("Closed.");
        reload();
      });
      body.append(h("div", { class: "stack" }, problem, note.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: done })));
      footer.hidden = false;
    } });
}

function overview(record, data, reload) {
  const state = record.state;
  const covered = record.covered;
  const notes = {
    notice: `Notice must be given by ${date(record.notice_on)}, ${record.renews ? "or it carries on by itself" : "to keep it going"}.`,
    ending: `It ends on ${date(record.ends_on)}. Renew it and record its new end date, or let it end and close it.`,
    ended: `It ended on ${date(record.ends_on)}, and what it imposes still binds its scopes. Record its new end date if it was renewed, or close it.`,
    upcoming: `It starts on ${date(record.starts_on)}.`,
    closed: `Closed on ${date(record.closed_on)}${record.closed_note ? `: ${record.closed_note}` : "."}`,
  };
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      notes[state] ? alert(state === "ended" ? "danger" : state === "closed" || state === "upcoming" ? "info" : "warn", icon(state === "closed" || state === "upcoming" ? "info" : "alert"), h("div", {}, notes[state])) : null,
      record.summary ? card({ title: "What it is for" }, prose(record.summary)) : null,
      card({ title: "Who it is with", actions: record.can.edit ? button("Change", { kind: "btn-sm", onclick: () => partiesForm(record, reload) }) : null },
        record.with?.length ? h("ul", { class: "plain-list stack-sm" }, record.with.map((each) => h("li", {}, recordChip(each))))
          : h("p", { class: "muted" }, "No third party is named. Until one is, it covers nothing shared with anyone.")),
      card({ title: covered.records.length ? `What it covers (${covered.records.length})` : "What it covers",
        actions: record.can.edit ? button("Change", { kind: "btn-sm", onclick: () => coversForm(record, reload) }) : null },
      covered.records.length ? h("ul", { class: "plain-list stack-sm" }, covered.records.map((each) => h("li", {}, recordChip(each))))
        : h("p", { class: "muted" }, "Nothing yet. Name the systems, information, services, and scopes it binds."),
      covered.hidden ? h("p", { class: "subtle" }, `And ${covered.hidden} more that you do not have access to.`) : null),
      card({ title: "What it imposes" },
        record.terms ? h("div", { class: "stack" },
          h("p", {}, h("a", { href: `/frameworks/${record.terms.key}` }, record.terms.title), ` · ${plural(record.terms.requirements, "requirement")}`),
          record.scopes.length ? h("div", { class: "stack-sm" }, h("div", { class: "label" }, "The scopes it binds: those it covers, and those that hold what it covers"),
            h("ul", { class: "plain-list stack-sm" }, record.scopes.map((scope) => h("li", {}, h("a", { href: `/scopes/${scope.ref}?tab=requirements&framework=${record.terms.key}` }, scope.name),
              h("span", { class: "cell-sub" }, ` ${scope.ref} · ${scope.because ? "held to it because of this agreement" : "already held to it by its own decision"}`)))))
            : h("p", { class: "muted" }, record.status === "closed" ? "Closed, it binds no scope." : "No scope holds what it covers yet."))
          : h("div", { class: "stack-sm" }, h("p", { class: "muted" }, "Its terms are not entered. Until they are, it binds no scope's requirements."),
            can("configure") ? h("p", {}, "Enter them as a framework of the organization's own under ", h("a", { href: "/frameworks" }, "Frameworks"), ", then choose it here with Edit.")
              : h("p", { class: "subtle" }, "Those who run the program enter an agreement's terms as a framework of its own.")))),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Kind", KINDS[record.kind]],
        ["With", record.parties],
        ["Their reference", record.reference],
        ["Standing", agreementState(record)],
        ["Starts", record.starts_on ? date(record.starts_on) : null],
        ["Ends", record.ends_on ? date(record.ends_on) : "Runs until it is ended"],
        ["Notice", record.notice_days ? `${plural(record.notice_days, "day")}: by ${date(record.notice_on)}` : null],
        ["Renews by itself", record.renews ? "Yes, unless notice is given" : null],
        ["Unit", data.units.byId.get(record.org_unit_id)?.name],
        ["Signed copy", record.url ? h("a", { href: record.url, target: "_blank", rel: "noopener noreferrer" }, "Where it is kept") : null],
      ])),
      ownersCard(record, { vocab: data.vocab, units: data.units, reload })));
}

export function agreementPage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/agreements/${params.ref}`;
      const [record, unitIndex, vocab, entries] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { record: record.data, units: unitIndex, vocab, history: entries?.data ?? [] };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const edit = record.can.edit ? button("Edit", { iconName: "edit", onclick: () => agreementForm({ record, unitIndex: data.units, onDone: reload }) }) : null;
      const end = record.can.close ? button("Close it", { kind: "btn-ghost", onclick: () => closeBox(record, reload) })
        : record.can.reopen ? button("Open it again", { onclick: () => confirmAction({ title: `Open ${record.ref} again?`, text: "What it imposes binds the scopes that hold what it covers again.",
          confirmLabel: "Open it again", run: async () => { await post(`/api/v1/agreements/${record.ref}/reopen`); toast("Open again."); reload(); } }) }) : null;
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [pill(KINDS[record.kind]), agreementState(record)], actions: h("div", { class: "row-sm wrap" }, edit, end) }),
        tabBar([["overview", "Overview"], ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history)) : overview(record, data, reload));
    },
  });
}
