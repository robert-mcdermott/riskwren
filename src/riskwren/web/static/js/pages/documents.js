// Policies → Documents: policies, standards, procedures, and guidelines. A document's page
// shows the version in force; the draft tab is where the next one is written, sent to named
// people, approved, and published.

import { del, get, patch, post, put, upload } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, dateTime, plural, relative } from "../core/format.js";
import { unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { segments } from "../components/charts.js";
import { comparison, DECISIONS, documentText, KIND_HINTS, KINDS, kindPill, reviewPill, WORKING, workingPill } from "../components/document.js";
import { exportButton } from "../components/exchange.js";
import { banner, checkbox, field, section, select, submit } from "../components/form.js";
import { closeOverlay, confirmAction, openOverlay } from "../components/overlay.js";
import { peoplePicker } from "../components/people-picker.js";
import { statusPill } from "../components/record.js";
import { listTools, similarHint } from "../components/tidy.js";
import { toast } from "../components/toast.js";
import { alert, avatar, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const said = (error) => Object.values(error.fields ?? {}).join(" ") || error.detail || "That did not work.";
const KIND_OPTIONS = Object.entries(KINDS);
const STATES = [["", "Any state"], ["working", "A new version being written"], ["in_review", "Awaiting approval"],
  ["approved", "Approved, not published"], ["unpublished", "Never published"], ["due", "Review due"], ["overdue", "Review overdue"]];
const mayAdd = () => can("steward") || can("lead");

async function documentsIn(unitIndex) {
  // What a new document may implement: those in use, broadest first.
  const found = await get("/api/v1/documents", { status: "active", limit: 200, sort: "kind" });
  return found.data;
}

function documentForm({ record = null, unitIndex, choices, onDone }) {
  openOverlay({
    title: record ? `Edit ${record.ref}` : "Add a document",
    subtitle: record ? null : "A policy, standard, procedure, or guideline. Its first draft can be written here, or added after.",
    render: (body, footer, close) => {
      const name = field("Title", { value: record?.name ?? "", required: true, maxlength: 200, hint: "As people know it, such as “Acceptable use policy”." });
      const kind = select("Kind", [["", "Choose…"], ...KIND_OPTIONS], { value: record?.kind ?? "", required: true });
      const kindHint = h("p", { class: "hint" }, record ? KIND_HINTS[record.kind] : "");
      kind.input.addEventListener("change", () => { kindHint.textContent = KIND_HINTS[kind.input.value] ?? ""; });
      const parents = choices.filter((each) => each.ref !== record?.ref);
      const parent = select("Implements", [["", "Nothing: it stands at the top"], ...parents.map((each) => [each.ref, `${KINDS[each.kind]}: ${each.name} (${each.ref})`])],
        { value: record?.parent?.ref ?? "", hint: "The policy or standard it puts into practice." });
      const unit = select("Unit", unitOptions(unitIndex.tree, { blank: record ? null : "Choose…" }), { value: record?.org_unit_id ?? "", required: true, hint: "The unit that answers for it." });
      const summary = field("What it is for", { type: "textarea", rows: 2, value: record?.summary ?? "" });
      const months = field("Reviewed every", { type: "number", min: 1, max: 120, value: record?.review_months ?? "", inputmode: "numeric",
        hint: record ? `Months. Leave empty for the program's ${record.review_every === 1 ? "month" : `${record.review_every} months`}.` : "Months. Leave empty for the program's cadence." });
      const asks = checkbox("Ask those it applies to to say they have read it", { checked: record?.acknowledge ?? false,
        hint: "They are told when a version is published, and it stays on their Home until they have." });
      const problem = banner();
      const save = button(record ? "Save" : "Add", { kind: "btn-primary" });
      const values = () => ({ name: name.input.value, kind: kind.input.value || null, parent: parent.input.value || null,
        org_unit_id: unit.input.value ? Number(unit.input.value) : null, summary: summary.input.value,
        review_months: months.input.value === "" ? null : Number(months.input.value), acknowledge: asks.input.checked });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { name, kind, parent, org_unit_id: unit, summary, review_months: months }, banner: problem,
          run: () => (record ? patch(`/api/v1/documents/${record.ref}`, { ...values(), version: record.version }) : post("/api/v1/documents", values())) });
        if (!done) return;
        close();
        if (record) {
          toast("Saved.");
          onDone(done.data);
        } else {
          toast(`${done.data.ref} was added. Write its first draft.`);
          navigate(`/documents/${done.data.ref}?tab=draft`);
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("What it is", name.node, similarHint("document", name.input, { unit: () => unit.input.value, apartFrom: record?.ref }),
          h("div", { class: "grid-2" }, kind.node, unit.node), kindHint, parent.node, summary.node),
        section("Reading it", asks.node),
        section("Review", months.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function documentList(main) {
  return show(main, {
    title: "Documents",
    load: async () => {
      const params = Object.fromEntries(query());
      const [page, unitIndex] = await Promise.all([get("/api/v1/documents", { sort: "kind", ...params }, { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data) => {
      const rows = data.page.data;
      const add = async () => documentForm({ unitIndex: data.units, choices: await documentsIn(data.units), onDone: () => {} });
      const search = searchBox("Search documents");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search), listTools(),
        filterSelect("kind", [["", "Any kind"], ...KIND_OPTIONS], "Kind"),
        filterSelect("state", STATES, "State"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        filterSelect("status", [["", "In use"], ["retired", "Retired"]], "Status"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Document", "name", "kind"), h("th", { scope: "col" }, "Implements"), h("th", { scope: "col" }, "Unit"),
          h("th", { scope: "col" }, "Owner"), h("th", { scope: "col" }, "In force"), sortHeader("Next review", "next_review_on", "kind"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/documents/${row.ref}` }, row.name),
            h("div", { class: "cell-sub" }, [row.ref, KINDS[row.kind]].join(" · ")),
            row.working ? h("div", {}, workingPill(row.working)) : null),
          h("td", {}, row.parent ? h("a", { href: `/documents/${row.parent.ref}` }, row.parent.name) : h("span", { class: "subtle" }, "—")),
          h("td", {}, data.units.byId.get(row.org_unit_id)?.name ?? ""), ownerCell(row),
          h("td", { class: "nowrap" }, row.status === "retired" ? statusPill("retired") : row.number ? `Version ${row.number}` : h("span", { class: "subtle" }, "Not published")),
          h("td", { class: "nowrap" }, row.next_review_on ? [date(row.next_review_on), reviewPill(row.review_state, row.next_review_on) ? h("div", {}, reviewPill(row.review_state, row.next_review_on)) : null] : ""))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "document", title: "No documents yet", text: "Add the policies the organization has, and the standards and procedures beneath them.",
            action: mayAdd() ? button("Add a document", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Policies", title: "Documents",
          lede: "The organization's own word: policies, the standards and procedures that put them into practice, and guidelines. Each version is approved by named people before it is published, and is never changed after.",
          actions: [mayAdd() ? button("Add a document", { kind: "btn-primary", iconName: "plus", onclick: add }) : null, exportButton("documents")] }),
        bar, card({ title: plural(data.page.meta.total, "document"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

// --- One document ----------------------------------------------------------------------------

function versionContent(record, version, { withContents = true } = {}) {
  if (version.form === "link") {
    return version.url
      ? h("div", { class: "stack-sm" }, h("p", {}, "This version is kept elsewhere. RiskWren keeps its approvals, its dates, and where it is."),
        h("p", {}, h("a", { href: version.url, target: "_blank", rel: "noopener noreferrer", class: "btn" }, icon("external", "icon icon-sm"), "Open where it is kept")),
        h("p", { class: "subtle mono break" }, version.url))
      : h("p", { class: "muted" }, "No address yet.");
  }
  if (version.form === "file") {
    return version.file
      ? h("div", { class: "row wrap" }, icon("file"), h("div", { class: "grow" }, h("div", { class: "cell-main" }, version.file.name),
        h("div", { class: "cell-sub" }, `${Math.max(1, Math.round(version.file.size / 1024))} KB`)),
      h("a", { class: "btn", href: `/api/v1/documents/${record.ref}/versions/${version.id}/file`, download: "" }, icon("download", "icon icon-sm"), "Download"))
      : h("p", { class: "muted" }, "No file yet.");
  }
  return version.body ? documentText(version.body, { withContents }) : h("p", { class: "muted" }, "Nothing written yet.");
}

function approvalsList(version) {
  return h("ul", { class: "plain-list rows" }, version.approvals.map((each) => h("li", { class: "row" },
    avatar(each.name), h("div", { class: "grow" }, h("div", { class: "cell-main" }, each.name),
      each.note ? h("div", { class: "cell-sub" }, each.note) : null),
    pill(DECISIONS[each.decision][0], DECISIONS[each.decision][1]),
    each.decided_at ? h("span", { class: "subtle nowrap" }, date(each.decided_at)) : null)));
}

function inForceTab(record) {
  const version = record.published;
  if (!version) {
    return card({}, emptyState({ iconName: "document", title: "Nothing has been published yet",
      text: record.working_status ? `A first version is ${WORKING[record.working_status][0].toLowerCase()}.` : "Nobody has started a first version.",
      action: record.can.edit ? h("a", { class: "btn btn-primary", href: `/documents/${record.ref}?tab=draft` }, record.working ? "Open the draft" : "Start the first version") : null }));
  }
  return h("div", { class: "stack-lg" },
    h("div", { class: "doc-meta" },
      h("span", { class: "cell-main" }, `Version ${version.number}`),
      h("span", {}, ` · published ${date(version.published_at)}`),
      version.approved_by.length ? h("span", {}, ` · approved by ${version.approved_by.join(", ")}`) : null),
    version.change_note && version.number > 1 ? alert("info", h("div", {}, h("strong", {}, "What changed: "), version.change_note)) : null,
    card({ title: null }, h("article", { class: "doc-body", "aria-label": record.name }, versionContent(record, version))));
}

function sendForApproval(record, version, reload) {
  const chosen = new Map(version.approvals.filter((each) => each.decision !== "cancelled").map((each) => [each.account_id, each.name]));
  const list = h("ul", { class: "plain-list stack-sm" });
  const errorNode = h("div", { class: "error", role: "alert", hidden: true });
  const draw = () => list.replaceChildren(...(chosen.size ? [...chosen].map(([id, name]) => h("li", { class: "row-sm" }, avatar(name),
    h("span", { class: "grow" }, name),
    button("Remove", { kind: "btn-sm btn-ghost", "aria-label": `Remove ${name}`, onclick: () => { chosen.delete(id); draw(); } })))
    : [h("li", { class: "muted" }, "Nobody yet.")]));
  draw();
  const picker = peoplePicker({ label: "Add someone to approve it", exclude: (account) => chosen.has(account.id),
    onPick: (account) => { chosen.set(account.id, account.display_name); draw(); } });
  const send = button("Send for approval", { kind: "btn-primary" });
  send.addEventListener("click", async () => {
    errorNode.hidden = true;
    send.disabled = true;
    try {
      await post(`/api/v1/documents/${record.ref}/draft/submit`, { approvers: [...chosen.keys()] });
      toast(`Sent to ${plural(chosen.size, "person", "people")} to approve.`);
      reload();
    } catch (error) {
      errorNode.textContent = said(error);
      errorNode.hidden = false;
      send.disabled = false;
    }
  });
  return card({ title: "Send it for approval" }, h("div", { class: "stack" },
    h("p", { class: "muted" }, "Name the people who must approve this version before it can be published. You may not approve what you wrote or send. Each is told, and it appears on their Home."),
    list, picker, errorNode, h("div", {}, send)));
}

function draftEditor(record, version, reload) {
  let form = version.form;
  const choose = h("div", { class: "segmented", role: "group", "aria-label": "Where its words are" },
    [["text", "Write it here"], ["link", "Link to where it is kept"], ["file", "Attach a file"]].map(([key, text]) =>
      h("button", { type: "button", "aria-pressed": String(form === key), onclick: () => { form = key; draw(); } }, text)));
  const text = field("Text", { type: "textarea", rows: 18, value: version.body ?? "", class: "textarea doc-editor",
    hint: "# for a heading, - for a list, **bold**, *emphasis*, and [a link](https://…). A blank line starts a new paragraph." });
  const url = field("Where it is kept", { type: "url", value: version.url ?? "", placeholder: "https://", hint: "The page or file in the place the organization already keeps it. RiskWren tracks its approvals and dates." });
  const fileInput = h("input", { type: "file", class: "input", id: "doc-file", accept: ".pdf,.doc,.docx,.odt,.txt,.md,.rtf" });
  const fileField = h("div", { class: "field" }, h("label", { for: "doc-file" }, "File"), fileInput,
    h("div", { class: "hint" }, version.form === "file" && version.file ? `Now: ${version.file.name}. Choosing another replaces it.` : "A PDF or Word document, up to 25 MB."));
  const note = field("What changed, and why", { type: "textarea", rows: 3, value: version.change_note ?? "",
    hint: record.published ? "Needed before it is sent. It is shown with the version once published." : "Optional for a first version." });
  const again = record.acknowledge && record.published ? checkbox("Everyone must acknowledge this version again", { checked: version.ask_again,
    hint: "Untick it for a change that does not alter what anyone must do: what they said of the earlier version still counts." }) : null;
  const asking = () => (again ? { ask_again: again.input.checked } : {});
  const preview = h("div", { class: "doc-preview", hidden: true });
  const showPreview = button("Preview", { kind: "btn-sm", "aria-pressed": "false", onclick: () => {
    const on = preview.hidden;
    preview.hidden = !on;
    text.input.hidden = on;
    showPreview.setAttribute("aria-pressed", String(on));
    showPreview.textContent = on ? "Back to writing" : "Preview";
    if (on) preview.replaceChildren(documentText(text.input.value, { withContents: false }));
  } });
  const problem = banner();
  const save = button("Save the draft", { kind: "btn-primary" });
  const holder = h("div", { class: "stack" });
  const draw = () => {
    choose.querySelectorAll("button").forEach((each, at) => each.setAttribute("aria-pressed", String(["text", "link", "file"][at] === form)));
    holder.replaceChildren(
      form === "text" ? h("div", { class: "stack-sm" }, h("div", { class: "row" }, h("span", { class: "grow" }), showPreview), text.node, preview) : null,
      form === "link" ? url.node : null,
      form === "file" ? fileField : null,
      note.node, again?.node ?? null);
  };
  draw();
  save.addEventListener("click", async () => {
    const done = await submit({ button: save, fields: { body: text, url, change_note: note }, banner: problem, run: async () => {
      if (form === "file" && fileInput.files?.length) {
        const file = fileInput.files[0];
        await upload(`/api/v1/documents/${record.ref}/draft/file`, file, { name: file.name });
        return patch(`/api/v1/documents/${record.ref}/draft`, { change_note: note.input.value, ...asking() });
      }
      return patch(`/api/v1/documents/${record.ref}/draft`, { form, change_note: note.input.value, ...asking(),
        ...(form === "text" ? { body: text.input.value } : {}), ...(form === "link" ? { url: url.input.value } : {}) });
    } });
    if (!done) return;
    toast("The draft is saved.");
    reload();
  });
  const discard = button("Discard the draft", { kind: "btn-ghost", onclick: () => confirmAction({
    title: "Discard this draft?", text: record.published ? `Version ${record.published.number} stays in force.` : "Nothing has been published, so the document will have no text.",
    confirmLabel: "Discard", danger: true,
    run: async () => {
      try {
        await del(`/api/v1/documents/${record.ref}/draft`);
        toast("Discarded.");
        reload();
      } catch (error) {
        toast(said(error));
      }
    } }) });
  return card({ title: record.published ? `The next version (after ${record.published.number})` : "The first version" },
    h("div", { class: "stack" }, problem, choose, holder, h("div", { class: "row" }, save, h("span", { class: "grow" }), discard)));
}

function reviewing(record, version, reload) {
  const parts = [];
  if (version.awaiting_me) {
    const note = field("Why", { type: "textarea", rows: 2, hint: "Needed to return it; kept with your approval if you approve." });
    const problem = banner();
    const decide = (decision) => async (event) => {
      const done = await submit({ button: event.currentTarget, fields: { note }, banner: problem,
        run: () => post(`/api/v1/documents/${record.ref}/draft/decision`, { decision, note: note.input.value || null }) });
      if (!done) return;
      toast(decision === "approved" ? "Approved." : "Returned to its author, with your reason.");
      reload();
    };
    parts.push(card({ title: "You are asked to approve this version" }, h("div", { class: "stack" }, problem,
      h("p", { class: "muted" }, "Read it below. Approve it, or return it with what needs to change."), note.node,
      h("div", { class: "row" }, button("Approve", { kind: "btn-primary", onclick: decide("approved") }), button("Return it", { onclick: decide("returned") })))));
  }
  const take = record.can.edit ? button("Take it back to change it", { onclick: async () => {
    try {
      await post(`/api/v1/documents/${record.ref}/draft/withdraw`);
      toast("Taken back. Those not yet asked are told it is no longer needed.");
      reload();
    } catch (error) {
      toast(said(error));
    }
  } }) : null;
  const publishNow = record.can.edit && version.status === "approved" ? button(`Publish as version ${(record.published?.number ?? 0) + 1}`, { kind: "btn-primary", onclick: () => confirmAction({
    title: "Publish this version?", text: `It is put in force${record.published ? ` in place of version ${record.published.number}` : ""} and can never be changed. Its next review is set from today.`,
    confirmLabel: "Publish",
    run: async () => {
      try {
        await post(`/api/v1/documents/${record.ref}/draft/publish`);
        toast("Published.");
        navigate(`/documents/${record.ref}`);
      } catch (error) {
        toast(said(error));
      }
    } }) }) : null;
  parts.push(card({ title: version.status === "approved" ? "Approved by everyone named" : "Awaiting approval",
    actions: h("div", { class: "row-sm" }, take, publishNow) },
  h("div", { class: "stack" }, h("p", { class: "muted" }, `Sent by ${version.submitted_by} ${relative(version.submitted_at)}.`), approvalsList(version))));
  return parts;
}

function draftTab(record, reload) {
  const version = record.working;
  if (!version) {
    if (record.working_status) {
      return card({}, emptyState({ iconName: "lock", title: `A new version is ${WORKING[record.working_status][0].toLowerCase()}`,
        text: "It is for those writing and approving it until it is published." }));
    }
    const start = record.can.draft ? button(record.published ? "Start a new version" : "Start the first version", { kind: "btn-primary", onclick: async () => {
      try {
        await post(`/api/v1/documents/${record.ref}/draft`);
        reload();
      } catch (error) {
        toast(said(error));
      }
    } }) : null;
    return card({}, emptyState({ iconName: "edit", title: "No new version is being written",
      text: record.published ? "A new version starts as a copy of the one in force." : "Nobody has started one.", action: start }));
  }
  const returned = version.returned ? alert("warn", h("div", {}, h("strong", {}, `${version.returned.by} returned it: `), version.returned.note)) : null;
  if (version.status === "draft") {
    return h("div", { class: "stack-lg" }, returned,
      record.can.edit ? draftEditor(record, version, reload) : card({ title: "The draft" }, versionContent(record, version)),
      record.can.edit ? sendForApproval(record, version, reload) : null);
  }
  return h("div", { class: "stack-lg" }, ...reviewing(record, version, reload),
    version.change_note ? card({ title: "What changed, and why" }, h("p", {}, version.change_note)) : null,
    card({ title: "The version to approve" }, h("article", { class: "doc-body", "aria-label": `${record.name}, the version to approve` }, versionContent(record, version))));
}

function versionsTab(record) {
  if (!record.versions.length) return card({}, emptyState({ iconName: "history", title: "No version has been published yet" }));
  const pick = (name, chosen) => h("select", { class: "select", "aria-label": name === "from" ? "Compare from" : "Compare to" },
    record.versions.map((each) => h("option", { value: each.id, selected: each.id === chosen }, `Version ${each.number}`)));
  const from = pick("from", record.versions[1]?.id ?? record.versions[0].id);
  const to = pick("to", record.versions[0].id);
  return h("div", { class: "stack-lg" },
    record.versions.length > 1 ? card({ title: "Compare two versions" }, h("div", { class: "row wrap" }, from, h("span", {}, "with"), to,
      button("Compare", { onclick: () => navigate(`/documents/${record.ref}/compare?from=${from.value}&to=${to.value}`) }))) : null,
    card({ title: plural(record.versions.length, "version"), flush: true }, h("ul", { class: "plain-list rows" }, record.versions.map((each, at) => h("li", { class: "stack-sm" },
      h("div", { class: "row wrap" }, h("a", { class: "cell-main", href: `/documents/${record.ref}/versions/${each.id}` }, `Version ${each.number}`),
        each.status === "published" ? pill("In force", "ok") : h("span", { class: "subtle" }, `Superseded ${date(each.superseded_at)}`),
        h("span", { class: "grow" }),
        record.versions[at + 1] && each.form === "text" && record.versions[at + 1].form === "text"
          ? h("a", { href: `/documents/${record.ref}/compare?from=${record.versions[at + 1].id}&to=${each.id}` }, `What changed from version ${record.versions[at + 1].number}`) : null),
      h("div", { class: "cell-sub" }, `Published ${dateTime(each.published_at)} by ${each.published_by}${each.approved_by.length ? `; approved by ${each.approved_by.join(", ")}` : ""}`),
      each.change_note ? h("div", {}, each.change_note) : null)))));
}

function reviewBox(record, reload) {
  openOverlay({ title: "Review and keep it as it is", subtitle: `Version ${record.published.number} stays in force, and its next review moves to ${record.review_every} months from today.`, kind: "dialog",
    render: (body, footer, close) => {
      const note = field("What was looked at", { type: "textarea", rows: 3, required: true, hint: "Such as “Checked against the new remote access standard; nothing to change.”" });
      const problem = banner();
      const go = button("Record the review", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, fields: { note }, banner: problem, run: () => post(`/api/v1/documents/${record.ref}/review`, { note: note.input.value }) });
        if (!done) return;
        close();
        toast("Recorded.");
        reload();
      });
      body.append(h("div", { class: "stack" }, problem, note.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function retireBox(record, reload) {
  openOverlay({ title: `Retire ${record.name}?`, subtitle: "It leaves use. Its versions and history stay on record, and it can be put back.", kind: "dialog",
    render: (body, footer, close) => {
      const note = field("Why", { type: "textarea", rows: 2, required: true });
      const problem = banner();
      const go = button("Retire it", { kind: "btn-danger" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, fields: { note }, banner: problem, run: () => post(`/api/v1/documents/${record.ref}/retire`, { note: note.input.value }) });
        if (!done) return;
        close();
        toast("Retired.");
        reload();
      });
      body.append(h("div", { class: "stack" }, problem, note.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function glance(record, data) {
  return card({ title: "At a glance" }, facts([
    ["Kind", KINDS[record.kind]],
    ["Implements", record.parent ? h("a", { href: `/documents/${record.parent.ref}` }, `${record.parent.name} (${record.parent.ref})`) : "Nothing: it stands at the top"],
    ["Unit", data.units.byId.get(record.org_unit_id)?.name ?? ""],
    ["In force", record.published ? `Version ${record.published.number}, since ${date(record.published.published_at)}` : "Nothing yet"],
    ["Reviewed every", `${plural(record.review_every, "month")}${record.review_months ? "" : " (the program's)"}`],
    ["Last reviewed", record.last_reviewed_on ? date(record.last_reviewed_on) : "Not yet"],
    ["Next review", record.next_review_on ? h("span", {}, date(record.next_review_on), " ", reviewPill(record.review_state, record.next_review_on)) : "When it is published"],
  ]));
}

const ROLE_NAMES = { admin: "Administrators", manager: "Managers", assessor: "Assessors", auditor: "Auditors", leader: "Leaders", steward: "Stewards" };

function listed(words) {
  return words.length < 2 ? words.join("") : `${words.slice(0, -1).join(", ")}${words.length > 2 ? "," : ""} or ${words.at(-1)}`;
}

function audienceWords(audience) {
  if (audience.everyone) return "Everyone who can sign in.";
  const parts = [
    audience.units.length ? `those who work in ${listed(audience.units.map((unit) => unit.name))}, or in a unit beneath` : null,
    audience.roles.length ? `${listed(audience.roles.map((role) => (ROLE_NAMES[role] ?? role).toLowerCase()))}, wherever they are` : null,
  ].filter(Boolean);
  const said = parts.join("; and ");
  return `${said.charAt(0).toUpperCase()}${said.slice(1)}.`;
}

function audienceForm(record, unitIndex, reload) {
  openOverlay({ title: "Who it applies to", subtitle: "Those it applies to find it in their library, and are asked to acknowledge it when it asks.",
    render: (body, footer, close) => {
      const everyone = checkbox("Everyone", { checked: record.audience.everyone, hint: "Everyone who can sign in." });
      const chosenUnits = new Set(record.audience.units.map((unit) => unit.id));
      const unitBoxes = [];
      const walk = (nodes, depth) => nodes.flatMap((node) => {
        const box = checkbox(node.name, { checked: chosenUnits.has(node.id), value: String(node.id) });
        box.node.dataset.depth = String(Math.min(depth, 4));
        unitBoxes.push(box);
        return [box.node, ...walk(node.children ?? [], depth + 1)];
      });
      const unitsNode = h("fieldset", { class: "stack-sm" }, h("legend", {}, "Those who work in these units, and the units beneath them"),
        h("div", { class: "stack-sm unit-checks" }, walk(unitIndex.tree, 0)));
      const roleBoxes = Object.entries(ROLE_NAMES).map(([key, text]) => checkbox(text, { checked: record.audience.roles.includes(key), value: key }));
      const rolesNode = h("fieldset", { class: "stack-sm" }, h("legend", {}, "And those who hold these roles, wherever they hold them"),
        h("div", { class: "stack-sm" }, roleBoxes.map((box) => box.node)));
      const sync = () => { unitsNode.hidden = everyone.input.checked; rolesNode.hidden = everyone.input.checked; };
      everyone.input.addEventListener("change", sync);
      sync();
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/documents/${record.ref}/audience`, {
          everyone: everyone.input.checked,
          units: unitBoxes.filter((box) => box.input.checked).map((box) => Number(box.input.value)),
          roles: roleBoxes.filter((box) => box.input.checked).map((box) => box.input.value) }) });
        if (!done) return;
        close();
        toast("Saved.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, everyone.node, unitsNode, rolesNode));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function audienceCard(record, data, reload) {
  const counts = record.acknowledgments;
  return card({ title: "Who it applies to", actions: record.can.edit ? button("Change", { kind: "btn-sm", onclick: () => audienceForm(record, data.units, reload) }) : null },
    h("div", { class: "stack-sm" }, h("p", {}, audienceWords(record.audience)),
      record.acknowledge ? h("p", { class: "muted" }, "Each is asked to say they have read it.") : null,
      counts && counts.required ? h("p", {}, h("a", { href: `/documents/${record.ref}?tab=acknowledgments` },
        `${counts.acknowledged} of ${plural(counts.people, "person", "people")} have acknowledged it`)) : null,
      record.published ? h("p", {}, h("a", { href: `/library/${record.ref}` }, "Read it as they do")) : null));
}

function askForAcknowledgment(record, unitIndex) {
  openOverlay({ title: "Ask for acknowledgment", subtitle: "A campaign asks those who have not yet said they read it, by a date, with reminders and a count by unit.",
    render: (body, footer, close) => {
      const name = field("Name", { value: `${record.name}, version ${record.acknowledgments.required.number}`, required: true });
      const due = field("Due", { type: "date", required: true });
      const unit = select("Only those in", unitOptions(unitIndex.tree, { blank: "Everyone it applies to" }));
      const problem = banner();
      const go = button("Start, and tell those asked", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, fields: { name, due_on: due, org_unit_id: unit }, banner: problem,
          run: () => post("/api/v1/campaigns", { kind: "acknowledgment", document: record.ref, name: name.input.value, due_on: due.input.value,
            org_unit_id: unit.input.value ? Number(unit.input.value) : null }) });
        if (!done) return;
        close();
        toast(`${done.data.ref} is started.`);
        navigate(`/campaigns/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack" }, problem, name.node, due.node, unit.node,
        h("p", { class: "muted" }, "Those who have already acknowledged the version they must are counted as done from the start.")));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function acknowledgmentsTab(record, data) {
  const found = data.standing;
  const required = found.required;
  const said = (row) => row.acknowledged ? `Version ${row.version}, ${date(row.at)}`
    : row.version ? pill(`Only version ${row.version}`, "warn") : pill("Not yet", "warn");
  return h("div", { class: "stack-lg" },
    card({ title: "Who has acknowledged it", actions: can("assess") && required ? button("Ask for acknowledgment", { kind: "btn-sm", onclick: () => askForAcknowledgment(record, data.units) }) : null },
      h("div", { class: "stack" },
        h("p", {}, required ? `Everyone it applies to is asked to have acknowledged version ${required.number} or later.` : "Nothing is published yet."),
        segments([{ label: "have", value: found.acknowledged, tone: "ok" }, { label: "have not yet", value: found.outstanding, tone: "gap" }],
          { label: `${found.acknowledged} of ${found.people} have acknowledged it` }))),
    found.by_unit.length ? card({ title: "By unit", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Unit"), h("th", { scope: "col", class: "numeric" }, "People"), h("th", { scope: "col", class: "numeric" }, "Have acknowledged"))),
      h("tbody", {}, found.by_unit.map((row) => h("tr", {}, h("td", {}, row.unit.name), h("td", { class: "numeric" }, String(row.people)),
        h("td", { class: "numeric" }, `${row.acknowledged} (${row.share}%)`))))))) : null,
    card({ title: plural(found.people, "person", "people"), flush: true }, found.rows.length
      ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Person"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Acknowledged"))),
        h("tbody", {}, found.rows.slice(0, 500).map((row) => h("tr", {}, h("td", {}, row.name), h("td", {}, row.unit), h("td", {}, said(row)))))))
      : emptyState({ iconName: "people", title: "It applies to no one", text: "Change who it applies to." })));
}

export function documentPage(main, params) {
  const tab = ["draft", "versions", "acknowledgments", "history"].includes(query().get("tab")) ? query().get("tab") : "document";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/documents/${params.ref}`;
      const [record, unitIndex, vocab, entries] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      const standing = tab === "acknowledgments" && record.data.acknowledgments ? (await get(`${base}/acknowledgments`, null, { fresh: true })).data : null;
      return { record: record.data, units: unitIndex, vocab, history: entries?.data ?? [], standing };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const edit = record.can.edit ? button("Edit", { iconName: "edit", onclick: async () => documentForm({ record, unitIndex: data.units, choices: await documentsIn(data.units), onDone: reload }) }) : null;
      const more = record.can.edit ? (record.status === "retired"
        ? button("Put back in use", { onclick: async () => { await post(`/api/v1/documents/${record.ref}/reinstate`); reload(); } })
        : button("Retire", { kind: "btn-ghost", onclick: () => retireBox(record, reload) })) : null;
      const review = record.can.review ? button("Review and keep", { onclick: () => reviewBox(record, reload) }) : null;
      const tabs = [["document", "Document"], ["draft", record.working_status ? `Next version · ${WORKING[record.working_status][0]}` : "Next version"],
        ["versions", "Versions"], ...(record.acknowledgments ? [["acknowledgments", "Acknowledgments"]] : []), ["history", "History"]];
      const body = tab === "draft" ? draftTab(record, reload) : tab === "versions" ? versionsTab(record)
        : tab === "acknowledgments" && data.standing ? acknowledgmentsTab(record, data)
        : tab === "history" ? card({ flush: true }, timeline(data.history)) : inForceTab(record);
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [kindPill(record.kind), record.status === "retired" ? statusPill("retired") : null,
          record.working_status ? workingPill(record.working_status) : null, reviewPill(record.review_state, record.next_review_on)],
        actions: h("div", { class: "row-sm wrap" }, review, edit, more) }),
        tabBar(tabs, tab),
        h("div", { class: "split" }, h("div", { class: "stack-lg" }, body),
          h("div", { class: "stack-lg" }, glance(record, data), audienceCard(record, data, reload), ownersCard(record, { vocab: data.vocab, units: data.units, reload }),
            record.children.length ? card({ title: "Implemented by" }, h("ul", { class: "plain-list stack-sm" }, record.children.map((child) => h("li", {},
              h("a", { href: `/documents/${child.ref}` }, child.name), h("span", { class: "cell-sub" }, ` ${KINDS[child.kind]} · ${child.ref}`))))) : null)));
    },
  });
}

export function documentVersion(main, params) {
  return show(main, {
    title: params.ref,
    load: async () => {
      const [record, version] = await Promise.all([get(`/api/v1/documents/${params.ref}`, null, { fresh: true }),
        get(`/api/v1/documents/${params.ref}/versions/${params.id}`, null, { fresh: true })]);
      return { record: record.data, version: version.data };
    },
    view: (data) => {
      const { record, version } = data;
      const current = record.published && record.published.id === version.id;
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: `/documents/${record.ref}?tab=versions` }, icon("chevron-left", "icon icon-sm"), record.name),
        pageHeader({ eyebrow: `${KINDS[record.kind]} · ${record.ref}`, title: version.number ? `${record.name}, version ${version.number}` : `${record.name}, a draft` }),
        version.status === "superseded" ? alert("warn", h("div", {}, `This version was superseded on ${date(version.superseded_at)}. `,
          record.published ? h("a", { href: `/documents/${record.ref}` }, `Version ${record.published.number} is in force.`) : null)) : null,
        current ? alert("info", "This is the version in force.") : null,
        h("div", { class: "doc-meta" }, version.published_at ? `Published ${dateTime(version.published_at)} by ${version.published_by}` : `Started by ${version.created_by}`,
          version.approved_by.length ? `; approved by ${version.approved_by.join(", ")}` : ""),
        version.change_note ? card({ title: "What changed, and why" }, h("p", {}, version.change_note)) : null,
        card({}, h("article", { class: "doc-body", "aria-label": record.name }, versionContent(record, version))),
        version.fingerprint ? h("p", { class: "subtle mono break" }, `Fingerprint ${version.fingerprint}`) : null);
    },
  });
}

export function documentCompare(main, params) {
  const from = query().get("from");
  const to = query().get("to");
  return show(main, {
    title: params.ref,
    load: async () => {
      const [record, found] = await Promise.all([get(`/api/v1/documents/${params.ref}`, null, { fresh: true }),
        get(`/api/v1/documents/${params.ref}/compare`, { from, to }, { fresh: true })]);
      return { record: record.data, found: found.data };
    },
    view: (data) => {
      const { record, found } = data;
      const name = (side) => (side.number ? `Version ${side.number}` : "The draft");
      const counts = found.counts;
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: `/documents/${record.ref}?tab=versions` }, icon("chevron-left", "icon icon-sm"), record.name),
        pageHeader({ eyebrow: `${KINDS[record.kind]} · ${record.ref}`, title: `${name(found.before)} and ${name(found.after)}`,
          lede: counts ? `${plural(counts.changed, "line")} changed, ${counts.added} added, ${counts.removed} removed. The words that differ are marked.` : null }),
        card({ flush: true }, comparison(found, { before: name(found.before), after: name(found.after) })));
    },
  });
}

