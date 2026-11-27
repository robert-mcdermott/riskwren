// Issues: the register, and one issue with what it is about, its actions, and its closure.

import { listTools, similarHint } from "../components/tidy.js";
import { get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural, relative } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query, setQuery } from "../core/router.js";
import { session } from "../core/session.js";
import { evidenceUnits, freshness } from "../components/evidence-state.js";
import { banner, checkbox, field, section, select, submit } from "../components/form.js";
import { ISSUE_STATUS, issueDue, issueStatus, recordPicker, SEVERITY, severityPill } from "../components/issue.js";
import { openOverlay } from "../components/overlay.js";
import { personField } from "../components/people-picker.js";
import { recordChip, TYPES } from "../components/record.js";
import { toast } from "../components/toast.js";
import { actionButtons, actionStatus, dueCell } from "../components/treatment.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { exportButton } from "../components/exchange.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const TABS = [["overview", "Overview"], ["history", "History"]];
const severityOptions = (vocab, blank = null) => [...(blank == null ? [] : [["", blank]]), ...Object.keys(SEVERITY).map((key) => [key, label(vocab, "issue_severities", key)])];
const days = (count) => (count % 30 === 0 && count < 360 ? plural(count / 30, "month") : plural(count, "day"));

function footerOf(footer, save, close) {
  footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
  footer.hidden = false;
}

// ---- Forms ----

/**
 * Raise an issue, or change one. `about` is records it starts out being about;
 * `requirement` ({ framework, code, title }) a requirement; `from` what found it.
 */
export function editIssue({ issue = null, about = [], requirement = null, unitId = null, from = null, name = "", vocab, units: unitIndex, onDone = null }) {
  const chosen = about.map((record) => ({ ...record }));
  openOverlay({
    title: issue ? "Edit the issue" : "Raise an issue",
    subtitle: issue ? `${issue.ref} · ${issue.name}` : "Something that is wrong and must be put right.",
    render: (body, footer, close) => {
      const title = field("What is wrong", { value: issue?.name ?? name, required: true, maxlength: 200, hint: issue ? null : "In a few words, as you would say it to the person who must fix it." });
      const summary = field("Detail", { type: "textarea", rows: 4, value: issue?.summary ?? "", hint: "What was seen, where, and how it was found." });
      const unit = select("Unit", unitOptions(unitIndex.tree, { only: evidenceUnits(), blank: issue || unitId ? null : "Choose…" }), { value: issue?.org_unit_id ?? unitId ?? "", required: true, hint: "The unit that must put it right." });
      const meaning = h("div", { class: "hint" });
      const severity = select("Severity", severityOptions(vocab), { value: issue?.severity ?? "moderate" });
      const explain = () => {
        const item = (vocab.issue_severities ?? []).find((each) => each.key === severity.input.value);
        meaning.replaceChildren(item?.description ?? "", item?.due_days ? `. Due within ${days(item.due_days)} of being raised.` : "");
      };
      severity.input.addEventListener("change", explain);
      explain();
      const source = select("What found it", options(vocab, "issue_sources"), { value: issue?.source_kind ?? from ?? "observation" });
      const me = session().account;
      const owner = issue ? null : personField("Who is to put it right", { value: { account_id: me.id, name: me.name }, hint: "They are told. It can be changed later, under Owners." });
      const restricted = checkbox("Restricted", { checked: issue?.restricted ?? false, hint: "Known only to its owners, its unit's stewards and leaders, managers, and auditors." });
      const picker = issue ? null : recordPicker({ types: ["control", "scope", "risk"], chosen, label: "Add", placeholder: "Find a control, a scope, or a risk", empty: "Not said yet. An issue is easier to find when it names what it is about." });
      const problem = banner();
      const saveButton = button(issue ? "Save" : "Raise it", { kind: "btn-primary" });
      const save = async () => {
        const values = { name: title.input.value, summary: summary.input.value, org_unit_id: unit.input.value ? Number(unit.input.value) : null,
          severity: severity.input.value, source_kind: source.input.value, restricted: restricted.input.checked };
        const fields = { name: title, summary, org_unit_id: unit, severity, source_kind: source, ...(owner ? { owner_id: owner } : {}) };
        const done = await submit({ button: saveButton, fields, banner: problem,
          run: () => (issue ? patch(`/api/v1/issues/${issue.ref}`, { version: issue.version, ...values })
            : post("/api/v1/issues", { ...values, owner_id: owner.value(), subjects: chosen.map((record) => record.ref),
              requirements: requirement ? [{ framework: requirement.framework, code: requirement.code }] : [] })) });
        if (!done) return;
        close();
        toast(issue ? "Saved." : `${done.data.ref} was raised. It is due ${date(done.data.due_on)}.`);
        if (onDone) onDone(done.data);
        else navigate(`/issues/${done.data.ref}`);
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem,
      section("What it is", title.node, similarHint("issue", title.input, { unit: () => unit.input.value, apartFrom: issue?.ref }), summary.node, h("div", { class: "grid-2" }, unit.node, source.node)),
      section("How serious", severity.node, meaning),
      picker ? section("What it is about", requirement ? h("p", {}, h("span", { class: "requirement-code" }, requirement.code), " ", requirement.title ?? "") : null, picker) : null,
      section("Who", owner?.node ?? null, restricted.node)));
      saveButton.addEventListener("click", save);
      footerOf(footer, saveButton, close);
    },
  });
}

function addAction(issue, reload) {
  openOverlay({
    title: "Add an action",
    subtitle: `${issue.ref} · ${issue.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const title = field("What is to be done", { required: true, maxlength: 200 });
      const detail = field("Detail", { type: "textarea", hint: "Optional." });
      const me = session().account;
      const owner = personField("Who will do it", { value: { account_id: me.id, name: me.name }, hint: "They are told, and see the issue." });
      const due = field("Due", { type: "date", required: true, value: issue.due_on });
      // Something a third party's contact does: the owner here follows it up.
      const contact = issue.contacts?.length ? select("Done by, at the third party", [["", "Nobody outside"], ...issue.contacts.map((c) => [String(c.id), `${c.name}, ${c.third_party}`])],
        { hint: "They have no account. The owner here follows it up with them." }) : null;
      const save = button("Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { title, detail, owner_id: owner, due_on: due, ...(contact ? { contact_id: contact } : {}) },
          run: () => post(`/api/v1/issues/${issue.ref}/actions`, { title: title.input.value, detail: detail.input.value || null,
            owner_id: owner.value() ?? 0, due_on: due.input.value || "0001-01-01", contact_id: contact?.input.value ? Number(contact.input.value) : null }) });
        if (done) {
          close();
          toast("The action was added.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, title.node, detail.node, h("div", { class: "grid-2" }, owner.node, due.node), contact?.node ?? null));
      footerOf(footer, save, close);
    },
  });
}

/** A short dialog that sends one or two fields to an action of the issue. */
function ask(issue, { title, text = null, fields, action, send, done, primary, reload }) {
  openOverlay({
    kind: "dialog",
    title,
    subtitle: `${issue.ref} · ${issue.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const save = button(primary, { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const ok = await submit({ button: save, banner: problem, fields, run: () => post(`/api/v1/issues/${issue.ref}/${action}`, send()) });
        if (ok) {
          close();
          toast(done);
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, text ? h("p", { class: "muted" }, text) : null, Object.values(fields).map((each) => each.node)));
      footerOf(footer, save, close);
    },
  });
}

function moveDate(issue, reload) {
  const due = field("New date", { type: "date", required: true, value: issue.due_on });
  const reason = field("Why it is moving", { type: "textarea", rows: 3, required: true });
  ask(issue, { title: "Move the date", primary: "Move it", action: "due-date", done: "The date was moved.", reload,
    text: `It was first due ${date(issue.original_due_on)}. Each move is kept, with its reason.`,
    fields: { due_on: due, reason }, send: () => ({ due_on: due.input.value || "0001-01-01", reason: reason.input.value }) });
}

/** The owner says it is put right: what was done, why it happened, and what shows it. */
function proposeClosure(issue, vocab, reload) {
  const cited = [];
  openOverlay({
    title: "Propose closing it",
    subtitle: `${issue.ref} · ${issue.name}`,
    render: (body, footer, close) => {
      const open = issue.actions.filter((action) => action.status === "open" || action.status === "in_progress").length;
      const note = field("What was done", { type: "textarea", rows: 4, required: true, hint: "What put it right, so that whoever confirms it knows what to look for." });
      const cause = select("Why it happened", options(vocab, "root_causes", { blank: "Choose…" }), { required: true });
      const meaning = h("div", { class: "hint" });
      cause.input.addEventListener("change", () => {
        meaning.textContent = (vocab.root_causes ?? []).find((item) => item.key === cause.input.value)?.description ?? "";
      });
      const picker = recordPicker({ types: ["evidence"], chosen: cited, label: "Cite evidence", placeholder: "Find evidence by name", empty: "None cited. Closure is easier to confirm with something to look at." });
      const evidenceError = h("div", { class: "error", role: "alert", hidden: true });
      const problem = banner();
      const save = button("Propose closure", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        evidenceError.hidden = true;
        const fields = { note, root_cause: cause, evidence: { input: note.input, setError: (message) => {
          evidenceError.hidden = !message;
          evidenceError.textContent = message ?? "";
        } } };
        const done = await submit({ button: save, fields, banner: problem,
          run: () => post(`/api/v1/issues/${issue.ref}/closure`, { note: note.input.value, root_cause: cause.input.value, evidence: cited.map((item) => item.ref) }) });
        if (done) {
          close();
          toast("Proposed. It closes when someone else has confirmed it.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        open ? alert("warn", icon("alert"), h("div", {}, `${plural(open, "action")} still open. Finish or cancel ${open === 1 ? "it" : "them"} first.`)) : null,
        issue.return_note ? alert("warn", icon("alert"), h("div", {}, `Sent back last time: ${issue.return_note}`)) : null,
        section("What was done", note.node), section("Root cause", cause.node, meaning), section("Evidence", picker, evidenceError),
        h("p", { class: "subtle" }, "Nobody confirms the closure of an issue they own. An assessor or a manager for the unit is asked.")));
      footerOf(footer, save, close);
    },
  });
}

function confirmClosure(issue, vocab, reload) {
  openOverlay({
    title: "Is it put right?",
    subtitle: `${issue.ref} · ${issue.name}`,
    render: (body, footer, close) => {
      const note = field("Note", { type: "textarea", rows: 3, hint: "Needed to send it back: say what is still missing." });
      const problem = banner();
      const yes = button("Confirm, and close it", { kind: "btn-primary" });
      const no = button("Send it back");
      const send = (confirm, pressed) => async () => {
        const done = await submit({ button: pressed, fields: { note }, banner: problem, run: () => post(`/api/v1/issues/${issue.ref}/validation`, { confirm, note: note.input.value || null }) });
        if (done) {
          close();
          toast(confirm ? `${issue.ref} is closed.` : "Sent back to its owner.");
          reload();
        }
      };
      yes.addEventListener("click", send(true, yes));
      no.addEventListener("click", send(false, no));
      body.append(h("div", { class: "stack-lg" }, problem, section("What its owner says", closureBody(issue, vocab)), note.node));
      footer.replaceChildren(h("div", { class: "row" }, yes, no, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function closureBody(issue, vocab) {
  return h("div", { class: "stack" }, prose(issue.closure_note),
    facts([["Root cause", issue.root_cause ? label(vocab, "root_causes", issue.root_cause) : null],
      ["Proposed", issue.proposed ? `${issue.proposed.by}, ${date(issue.proposed.at)}` : null],
      ["Confirmed", issue.validated ? `${issue.validated.by}, ${date(issue.validated.at)}` : null]]),
    issue.closure_evidence.length ? h("div", { class: "stack-sm" }, issue.closure_evidence.map((item) => h("div", { class: "row-sm wrap" }, recordChip({ ...item, type: "evidence" }), freshness(item.state)))) : null);
}

// ---- One issue ----

function overview(issue, ctx) {
  const v = ctx.vocab;
  const about = issue.subjects;
  const can = issue.can_act;
  const progress = issue.progress;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      issue.status === "proposed" ? alert("info", icon("info"), h("div", {}, `${issue.proposed.by} says this is put right. It closes when someone who does not own it has confirmed that.`)) : null,
      issue.status === "open" && issue.return_note ? alert("warn", icon("alert"), h("div", {}, `Sent back: ${issue.return_note}`)) : null,
      issue.status === "cancelled" ? alert("info", icon("info"), h("div", {}, `Withdrawn: ${issue.closure_note}`)) : null,
      card({ title: "What is wrong" }, issue.summary ? prose(issue.summary) : h("p", { class: "muted" }, "No detail was given."),
        issue.source?.engagement ? h("p", { class: "subtle" }, "A finding of internal audit, from ", h("a", { href: `/audit/engagements/${issue.source.engagement.ref}` }, `${issue.source.engagement.ref} ${issue.source.engagement.name}`), ". Internal audit confirms its closure.")
          : issue.source?.review ? h("p", { class: "subtle" }, "From ", h("a", { href: `/reviews/${issue.source.review.ref}` }, `${issue.source.review.ref} ${issue.source.review.name}`), ".")
          : issue.source ? h("p", { class: "subtle" }, "From ", h("a", { href: `/assessments/${issue.source.assessment.ref}` }, `${issue.source.assessment.ref} ${issue.source.assessment.name}`),
            `, tested by ${issue.source.tested_by} on ${date(issue.source.tested_at)}.`) : null),
      card({ title: "What it is about" },
        about.records.length || about.requirements.length ? h("div", { class: "stack" },
          about.records.length ? h("div", { class: "chips" }, about.records.map((record) => recordChip(record))) : null,
          about.requirements.map((item) => h("div", {}, h("a", { href: `/frameworks/${item.framework.key}?r=${encodeURIComponent(item.code)}` }, h("span", { class: "requirement-code" }, item.code), " ", item.title ?? ""),
            h("span", { class: "subtle" }, ` ${item.framework.title}`))))
          : h("p", { class: "muted" }, "Nothing is named."),
        about.hidden ? h("p", { class: "subtle" }, `And ${about.hidden} more that you do not have access to.`) : null),
      card({ title: progress.total ? `Actions: ${progress.done} of ${progress.total} done` : "Actions", flush: issue.actions.length > 0,
        actions: can.work ? button("Add an action", { kind: "btn-sm", iconName: "plus", onclick: () => addAction(issue, ctx.reload) }) : null },
      issue.actions.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Action"), h("th", { scope: "col" }, "Owner"), h("th", { scope: "col" }, "Due"), h("th", { scope: "col" }, "Status"),
          h("th", { scope: "col" }, h("span", { class: "sr-only" }, "What you can do")))),
        h("tbody", {}, issue.actions.map((action) => h("tr", {},
          h("td", {}, h("div", { class: "cell-main" }, action.title), h("div", { class: "cell-sub" }, action.ref, action.completion_note ? ` · ${action.completion_note}` : "")),
          h("td", {}, action.owner.name, action.contact ? h("div", { class: "cell-sub" }, `with ${action.contact.name}, ${action.contact.third_party}`) : null), h("td", { class: "nowrap" }, dueCell(action)), h("td", {}, actionStatus(action)),
          h("td", { class: "actions" }, actionButtons(action, ctx.reload)))))))
        : h("p", { class: "muted" }, "None yet. An issue is put right through actions, each with an owner and a date.")),
      issue.closure_note && issue.status !== "cancelled" ? card({ title: issue.status === "closed" ? "How it was put right" : "What its owner says was done" }, closureBody(issue, v)) : null),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Severity", h("div", {}, severityPill(issue.severity, Object.fromEntries((v.issue_severities ?? []).map((item) => [item.key, item.label]))),
          h("div", { class: "cell-sub" }, `Due within ${days(issue.due_days)} of being raised`))],
        ["Due", issueDue(issue)],
        ["Raised", date(issue.created_at)],
        ["Found by", label(v, "issue_sources", issue.source_kind)],
        ["Unit", ctx.units.byId.get(issue.org_unit_id)?.name],
        ["Closed", issue.closed_at ? date(issue.closed_at) : null],
      ]),
      issue.extensions.length ? h("details", { class: "disclosure" }, h("summary", {}, `The date has moved ${issue.extensions.length === 1 ? "once" : `${issue.extensions.length} times`}`),
        h("ul", { class: "prose" }, issue.extensions.map((move) => h("li", {}, `${date(move.from)} to ${date(move.to)}: ${move.reason} (${move.by}, ${date(move.on)})`)))) : null),
      ownersCard(issue, ctx)));
}

export function issuePage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/issues/${params.ref}`;
      const [issue, vocab, unitIndex, extra] = await Promise.all([get(base, null, { fresh: true }), vocabularies(), units(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { issue: { ...issue.data, type: "issue" }, vocab, units: unitIndex, extra: extra?.data ?? [] };
    },
    view: (data, reload) => {
      const issue = data.issue;
      document.title = `${issue.name} · ${issue.ref}`;
      const ctx = { vocab: data.vocab, units: data.units, reload };
      const can = issue.can_act;
      const reason = () => field("Why", { type: "textarea", rows: 3, required: true });
      const actions = h("div", { class: "row wrap" },
        can.validate ? button("Confirm closure", { kind: "btn-primary", onclick: () => confirmClosure(issue, data.vocab, reload) }) : null,
        can.propose ? button("Propose closure", { kind: "btn-primary", onclick: () => proposeClosure(issue, data.vocab, reload) }) : null,
        can.work ? button("Move the date", { onclick: () => moveDate(issue, reload) }) : null,
        issue.can.edit && issue.status === "open" ? button("Edit", { iconName: "edit", onclick: () => editIssue({ issue, vocab: data.vocab, units: data.units, onDone: reload }) }) : null,
        can.cancel ? button("Withdraw", { kind: "btn-ghost", onclick: () => {
          const why = reason();
          ask(issue, { title: "Withdraw this issue?", text: "For an issue raised in error. Its open actions are cancelled with it, and it stays on the record.", primary: "Withdraw it", action: "cancellation",
            done: "Withdrawn.", reload, fields: { reason: why }, send: () => ({ reason: why.input.value }) });
        } }) : null,
        can.reopen ? button("Reopen", { onclick: () => {
          const why = reason();
          ask(issue, { title: "Open this issue again?", text: "Because it turned out not to be put right.", primary: "Reopen it", action: "reopening", done: "Open again.", reload,
            fields: { reason: why }, send: () => ({ reason: why.input.value }) });
        } }) : null);
      return h("div", { class: "stack" },
        recordHeader(issue, { badges: [severityPill(issue.severity), issueStatus(issue), issue.status === "open" && !issue.overdue ? null : issue.overdue ? pill(ISSUE_STATUS[issue.status][0], ISSUE_STATUS[issue.status][1]) : null], actions }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : overview(issue, ctx));
    },
  });
}

// ---- The register ----

export function issueRows(rows, vocab, unitIndex, { sortable = true } = {}) {
  const head = (text, key) => (sortable ? sortHeader(text, key, "due_on") : h("th", { scope: "col" }, text));
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, head("Issue", "name"), h("th", { scope: "col" }, "Severity"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Owner"),
      head("Due", "due_on"), h("th", { scope: "col" }, "Actions"), head("Status", "status"))),
    h("tbody", {}, rows.map((r) => h("tr", {},
      h("td", {}, h("a", { class: "cell-main", href: `/issues/${r.ref}` }, r.name),
        h("div", { class: "cell-sub" }, [r.ref, label(vocab, "issue_sources", r.source_kind), r.restricted ? "Restricted" : null].filter(Boolean).join(" · "))),
      h("td", {}, severityPill(r.severity)),
      h("td", {}, unitIndex.byId.get(r.org_unit_id)?.name ?? ""),
      ownerCell(r),
      h("td", { class: "nowrap" }, issueDue(r)),
      h("td", { class: "nowrap" }, r.progress.total ? `${r.progress.done} of ${r.progress.total}` : h("span", { class: "subtle" }, "None")),
      h("td", {}, issueStatus(r), h("div", { class: "cell-sub" }, `Updated ${relative(r.updated_at)}`)))))));
}

export function issueList(main) {
  const meta = TYPES.issue;
  return show(main, {
    title: "Issues",
    load: async () => {
      const said = Object.fromEntries(query());
      const asked = { status: "live", ...said, ...(said.status === "any" ? { status: undefined } : {}) };
      const [page, vocab, unitIndex] = await Promise.all([get("/api/v1/issues", asked, { fresh: true }), vocabularies(), units()]);
      return { page, vocab, units: unitIndex, asked };
    },
    view: (data, reload) => {
      const rows = data.page.data;
      const add = () => editIssue({ vocab: data.vocab, units: data.units });
      const search = searchBox("Search issues");
      keepSearchFocus(search);
      const overdue = query().get("overdue") === "true";
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search), listTools(),
        filterSelect("status", [["", "Not yet closed"], ["open", "Open"], ["proposed", "Awaiting confirmation"], ["closed", "Closed"], ["cancelled", "Withdrawn"], ["any", "Any status"]], "Status"),
        filterSelect("severity", severityOptions(data.vocab, "Any severity"), "Severity"),
        filterSelect("source_kind", options(data.vocab, "issue_sources", { blank: "Found by anything" }), "What found it"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        filterSelect("age", [["", "Raised at any time"], ["0-30", "Under a month ago"], ["31-90", "1 to 3 months ago"], ["91-180", "3 to 6 months ago"], ["181+", "Over 6 months ago"]], "Age"),
        h("button", { type: "button", class: `btn${overdue ? " btn-primary" : ""}`, "aria-pressed": String(overdue), onclick: () => setQuery({ overdue: overdue ? null : "true", cursor: null }) }, "Overdue"),
        mineToggle());
      void reload;
      const body = rows.length ? issueRows(rows, data.vocab, data.units)
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "issue", title: "No open issues", text: meta.lede, action: button("Raise an issue", { kind: "btn-primary", onclick: add }) });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Compliance", title: "Issues", lede: meta.lede, actions: [button("Raise an issue", { kind: "btn-primary", iconName: "plus", onclick: add }), exportButton("issues", data.asked)] }),
        bar,
        card({ title: plural(data.page.meta.total, "issue"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
