// Audit → Universe and Plans: everything worth auditing, ranked from the register with its
// working shown, and each period's plan, approved by a named person and tracked against.

import { get, post, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { navigate, query, setQuery } from "../core/router.js";
import { banner, checkbox, field, section, select, submit } from "../components/form.js";
import { personField } from "../components/people-picker.js";
import { openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const BAND_TONE = { high: "danger", medium: "warn", low: "" };
const PATHS = { process: "processes", system: "systems", third_party: "third-parties", scope: "scopes" };
const STATUS_TONE = { planned: "info", planning: "info", fieldwork: "accent", reporting: "accent", reported: "ok", dropped: "" };

function entityLink(row) {
  if (row.kind === "unit") return h("span", { class: "cell-main" }, row.name);
  return h("a", { class: "cell-main", href: `/${PATHS[row.kind]}/${row.ref}` }, row.name);
}

function working(row) {
  return h("ul", { class: "plain-list stack-sm" }, row.parts.map((part) => h("li", { class: "row-sm" },
    h("span", { class: "numeric mono" }, `${part.points > 0 ? "+" : ""}${part.points}`), h("span", {}, part.label))));
}

function sayForm(row, onDone) {
  openOverlay({ title: `What audit says about ${row.name}`, subtitle: `${row.kind_label}${row.ref ? ` · ${row.ref}` : ""} · ranked ${row.score}`,
    render: (body, footer, close) => {
      const adjustment = field("Move it up or down, in points", { type: "number", min: -30, max: 30, step: 1, value: row.adjustment ?? 0, hint: "At most 30 either way. Zero takes a move away." });
      const why = field("Why", { type: "textarea", rows: 2, value: row.adjustment_reason ?? "", hint: "Needed to move it: a tip-off, a change of system, a regulator's interest." });
      const last = field("Last audited before RiskWren", { type: "date", value: row.last_audit_note ? (row.last_audited_on ?? "") : "" });
      const lastNote = field("Which audit", { value: row.last_audit_note ?? "", maxlength: 300 });
      const out = checkbox("Leave it out of the universe", { checked: row.left_out });
      const outWhy = field("Why it is left out", { type: "textarea", rows: 2, value: row.left_out_reason ?? "" });
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { adjustment, adjustment_reason: why, last_audited_on: last, left_out_reason: outWhy },
          run: () => put(`/api/v1/audit/universe/${row.kind}/${row.key}`, {
            adjustment: Number(adjustment.input.value || 0), adjustment_reason: why.input.value || null,
            last_audited_on: last.input.value || null, last_audit_note: lastNote.input.value || null,
            left_out: out.input.checked, left_out_reason: outWhy.input.value || null }) });
        if (!done) return;
        close();
        toast("Recorded.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("Its ranking", adjustment.node, why.node),
        section("Audits before RiskWren", last.node, lastNote.node),
        section("The universe", out.node, outWhy.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function universePage(main) {
  const asked = query();
  return show(main, {
    title: "Audit universe",
    load: async () => (await get("/api/v1/audit/universe", { kind: asked.get("kind") || undefined, left_out: asked.get("left_out") === "true" ? "true" : undefined }, { fresh: true })).data,
    view: (data, reload) => {
      const kind = h("select", { class: "select", "aria-label": "Kind", onchange: () => setQuery({ kind: kind.value || null }) },
        h("option", { value: "" }, "Every kind"), Object.entries(data.kinds).map(([key, label]) => h("option", { value: key, selected: key === asked.get("kind") }, label)));
      const out = asked.get("left_out") === "true";
      const bar = h("div", { class: "filters" }, kind,
        button(out ? "Show the universe" : `Left out (${data.left_out})`, { kind: "btn-ghost", onclick: () => setQuery({ left_out: out ? null : "true" }) }),
        h("span", { class: "subtle" }, Object.entries(data.bands).map(([key, label]) => `${data.counts[key]} ${label.toLowerCase()}`).join(" · ")));
      const rows = data.entities.map((row) => h("tr", {},
        h("td", {}, entityLink(row), h("div", { class: "cell-sub" }, [row.kind_label, row.ref, row.unit].filter(Boolean).join(" · "))),
        h("td", {}, pill(`${row.band_label} · ${row.score}`, BAND_TONE[row.band]), h("details", { class: "working" }, h("summary", {}, "How"), working(row))),
        h("td", {}, row.last_audited_on ? date(row.last_audited_on) : h("span", { class: "subtle" }, "Never")),
        h("td", {}, row.planned.length ? row.planned.join(", ") : h("span", { class: "subtle" }, "—")),
        h("td", { class: "no-print" }, data.can_work ? button("Say", { kind: "btn-sm", "aria-label": `What audit says about ${row.name}`, onclick: () => sayForm(row, reload) }) : null)));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Audit", title: "Universe",
          lede: "Everything worth auditing: every unit beneath the organization, and every process, system, third party, and scope in use, ranked by what the register says about it today and how long since it was last audited. Each ranking shows how it was reached; audit may move one with a reason." }),
        bar,
        rows.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("caption", { class: "sr-only" }, "The audit universe, highest ranked first"),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "What"), h("th", { scope: "col" }, "Ranking"), h("th", { scope: "col" }, "Last audited"),
            h("th", { scope: "col" }, "Planned"), h("th", { scope: "col", class: "no-print" }, h("span", { class: "sr-only" }, "Actions")))),
          h("tbody", {}, rows))))
          : emptyState({ iconName: "search", title: out ? "Nothing is left out" : "Nothing to show", text: out ? "Everything in use is in the universe." : "Nothing of that kind is in use." }));
    },
  });
}

function planForm(onDone) {
  openOverlay({ title: "Draft a plan", subtitle: "The engagements internal audit means to carry out in a period.",
    render: (body, footer, close) => {
      const year = new Date().getFullYear() + 1;
      const name = field("Plan", { value: `Internal audit plan, ${year}`, required: true, maxlength: 200 });
      const starts = field("From", { type: "date", value: `${year}-01-01`, required: true });
      const ends = field("To", { type: "date", value: `${year}-12-31`, required: true });
      const summary = field("What it sets out to do", { type: "textarea", rows: 3 });
      const problem = banner();
      const save = button("Draft it", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { name, starts_on: starts, ends_on: ends, summary },
          run: () => post("/api/v1/audit/plans", { name: name.input.value, starts_on: starts.input.value, ends_on: ends.input.value, summary: summary.input.value || null }) });
        if (!done) return;
        close();
        onDone(done.data.ref);
      });
      body.append(h("div", { class: "stack-lg" }, problem, name.node, h("div", { class: "grid-2" }, starts.node, ends.node), summary.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function planList(main) {
  return show(main, {
    title: "Audit plans",
    load: async () => (await get("/api/v1/audit/plans", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Audit", title: "Plans", lede: "Each period's plan: the engagements internal audit means to carry out, why each, who approved it, and where each stands.",
        actions: data.can_add ? button("Draft a plan", { kind: "btn-primary", iconName: "plus", onclick: () => planForm((ref) => navigate(`/audit/plans/${ref}`)) }) : null }),
      data.plans.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Plan"), h("th", { scope: "col" }, "Period"), h("th", { scope: "col" }, "Approved"), h("th", { scope: "col" }, "Engagements"))),
        h("tbody", {}, data.plans.map((plan) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/audit/plans/${plan.ref}` }, plan.name), h("div", { class: "cell-sub mono" }, plan.ref)),
          h("td", {}, `${date(plan.starts_on)} to ${date(plan.ends_on)}`),
          h("td", {}, plan.approved_at ? [date(plan.approved_at), h("div", { class: "cell-sub" }, plan.approved_by)] : pill(plan.status === "draft" ? "Draft" : plan.status, "info")),
          h("td", {}, Object.entries(plan.counts).map(([status, count]) => `${count} ${data.statuses[status].toLowerCase()}`).join(", ") || h("span", { class: "subtle" }, "None yet"))))))))
        : emptyState({ iconName: "file", title: "No plan yet", text: "Draft the first: its engagements are chosen from the universe, each with its reason." })),
  });
}

function engagementForm(plan, onDone) {
  openOverlay({ title: "Plan an engagement", subtitle: `${plan.ref} · ${plan.name}`,
    render: async (body, footer, close) => {
      const universe = (await get("/api/v1/audit/universe", null, { fresh: true })).data;
      const choices = universe.entities.map((row) => [`${row.kind}:${row.key}`, `${row.name} (${row.kind_label}${row.ref ? ` ${row.ref}` : ""}) · ${row.band_label} ${row.score}`]);
      const what = select("What it audits", choices, { hint: "Highest ranked first." });
      const name = field("Engagement", { required: true, maxlength: 200, hint: "Such as “Access management” or “Sequencing data”." });
      const reason = field("Why it is in the plan", { type: "textarea", rows: 2, required: true });
      const start = field("Starts", { type: "date", min: plan.starts_on, max: plan.ends_on });
      const end = field("Ends", { type: "date", min: plan.starts_on, max: plan.ends_on });
      const problem = banner();
      const save = button("Add it", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const [kind, key] = what.input.value.split(":");
        const done = await submit({ button: save, banner: problem, fields: { name, reason, key: what, planned_start: start, planned_end: end },
          run: () => post(`/api/v1/audit/plans/${plan.ref}/engagements`, { name: name.input.value, kind, key, reason: reason.input.value,
            planned_start: start.input.value || null, planned_end: end.input.value || null }) });
        if (!done) return;
        close();
        toast("Added to the plan.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, what.node, name.node, reason.node, h("div", { class: "grid-2" }, start.node, end.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function ask(title, label, { required, run, done }) {
  openOverlay({ title,
    render: (body, footer, close) => {
      const note = field(label, { type: "textarea", rows: 3, required });
      const problem = banner();
      const go = button("Record it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const ok = await submit({ button: go, banner: problem, fields: { note, reason: note }, run: () => run(note.input.value) });
        if (!ok) return;
        close();
        done();
      });
      body.append(h("div", { class: "stack-lg" }, problem, note.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function planPage(main, { ref }) {
  return show(main, {
    title: ref,
    load: async () => (await get(`/api/v1/audit/plans/${ref}`, null, { fresh: true })).data,
    view: (plan, reload) => {
      const actions = h("div", { class: "row-sm wrap" },
        plan.can.work ? button("Plan an engagement", { kind: "btn-primary", iconName: "plus", onclick: () => engagementForm(plan, reload) }) : null,
        plan.can.approve ? button("Approve the plan", { onclick: () => ask("Approve the plan", "On whose authority, and when", { required: false, run: (note) => post(`/api/v1/audit/plans/${plan.ref}/approve`, { note: note || null }), done: reload }) }) : null,
        plan.can.close ? button("Close the plan", { kind: "btn-ghost", onclick: async () => { await post(`/api/v1/audit/plans/${plan.ref}/close`); toast("Closed."); reload(); } }) : null);
      const status = plan.status === "approved"
        ? alert("ok", h("strong", {}, "Approved. "), `By ${plan.approved_by} on ${date(plan.approved_at)}.`, plan.approval_note ? ` ${plan.approval_note}` : "")
        : plan.status === "closed" ? alert("info", "Closed. It takes no more engagements.")
          : alert("info", h("strong", {}, "Draft. "), "Approved by an auditor other than the one who drafted it, recording the committee's approval, or by a leader of the whole organization.");
      const rows = plan.engagements.map((row) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/audit/engagements/${row.ref}` }, row.name), h("div", { class: "cell-sub" }, [row.ref, row.added_after_approval ? "added after approval" : null].filter(Boolean).join(" · "))),
        h("td", {}, row.entity.kind === "unit" ? row.entity.name : h("a", { href: `/${PATHS[row.entity.kind]}/${row.entity.ref}` }, row.entity.name),
          h("div", { class: "cell-sub" }, `${row.entity.kind_label} · ranked ${row.entity.band_label.toLowerCase()}, ${row.entity.score}`)),
        h("td", {}, row.reason ?? ""),
        h("td", {}, row.planned_start ? `${date(row.planned_start)}${row.planned_end ? ` to ${date(row.planned_end)}` : ""}` : h("span", { class: "subtle" }, "Not set")),
        h("td", {}, pill(row.status_label, STATUS_TONE[row.status]), row.dropped_reason ? h("div", { class: "cell-sub" }, row.dropped_reason) : null),
        h("td", { class: "no-print" }, plan.can.work && row.status === "planned" ? button("Drop", { kind: "btn-sm btn-ghost", "aria-label": `Drop ${row.name}`,
          onclick: () => ask(`Drop ${row.name}`, "Why it will not be done", { required: true, run: (why) => post(`/api/v1/engagements/${row.ref}/drop`, { reason: why }), done: reload }) })
          : plan.can.work && row.status === "dropped" ? button("Restore", { kind: "btn-sm btn-ghost", "aria-label": `Restore ${row.name}`, onclick: async () => { await post(`/api/v1/engagements/${row.ref}/restore`); reload(); } }) : null)));
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: "/audit/plans" }, "Plans"),
        pageHeader({ eyebrow: `Audit plan · ${plan.ref}`, title: plan.name, lede: `${date(plan.starts_on)} to ${date(plan.ends_on)}. ${plan.summary ?? ""}`, actions }),
        status,
        h("p", { class: "subtle", role: "status" }, Object.entries(plan.counts).filter(([, count]) => count).map(([key, count]) => `${count} ${plan.statuses[key].toLowerCase()}`).join(", ") || "No engagements yet."),
        rows.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Engagement"), h("th", { scope: "col" }, "What it audits"), h("th", { scope: "col" }, "Why"),
            h("th", { scope: "col" }, "When"), h("th", { scope: "col" }, "Where it stands"), h("th", { scope: "col", class: "no-print" }, h("span", { class: "sr-only" }, "Actions")))),
          h("tbody", {}, rows))))
          : emptyState({ iconName: "file", title: "No engagements yet", text: "Plan one from the universe, highest ranked first, with the reason for it." }));
    },
  });
}

// --- An engagement ------------------------------------------------------------------------

const STAGES = [["planned", "Planned"], ["planning", "Planning"], ["fieldwork", "Fieldwork"], ["reporting", "Reporting"], ["reported", "Reported"]];
const ADVANCE = { fieldwork: "Start fieldwork", reporting: "Move to reporting", reported: "Issue the report" };

function startForm(engagement, onDone) {
  openOverlay({ title: `Start ${engagement.name}`, subtitle: "Its lead, its team, and what it covers. Until the report is issued, only the team sees its work.",
    render: async (body, footer, close) => {
      const people = (await get("/api/v1/auditors", null, { fresh: true })).data;
      const lead = select("Lead", people.map((each) => [each.account_id, each.name]));
      const members = people.map((each) => ({ id: each.account_id, box: checkbox(each.name) }));
      const scope = field("What it covers", { type: "textarea", rows: 3, hint: "The objectives, the period, and what is in and out." });
      const problem = banner();
      const go = button("Start it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { lead, scope_note: scope },
          run: () => post(`/api/v1/engagements/${engagement.ref}/start`, { lead: Number(lead.input.value),
            members: members.filter((each) => each.box.input.checked).map((each) => each.id), scope_note: scope.input.value || null }) });
        if (!done) return;
        close();
        toast("Started.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, lead.node, section("The rest of the team", members.map((each) => each.box.node)), scope.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function advanceForm(engagement, onDone) {
  if (engagement.next !== "reported") {
    post(`/api/v1/engagements/${engagement.ref}/advance`, {}).then(() => { toast("Moved on."); onDone(); },
      (error) => toast(error.fields?.steps ?? error.detail ?? "It did not move on."));
    return;
  }
  openOverlay({ title: "Issue the report", subtitle: "Its work then opens to those who read the plan.",
    render: (body, footer, close) => {
      const summary = field("What the engagement found", { type: "textarea", rows: 5, required: true });
      const opinion = select("Opinion", Object.entries(engagement.opinions));
      const problem = banner();
      const go = button("Issue it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { summary, opinion },
          run: () => post(`/api/v1/engagements/${engagement.ref}/advance`, { summary: summary.input.value, opinion: opinion.input.value }) });
        if (!done) return;
        close();
        toast("The report is issued.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, summary.node, opinion.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function workForm(paper, onDone) {
  openOverlay({ title: `${paper.sequence}. ${paper.title}`, subtitle: paper.procedure,
    render: (body, footer, close) => {
      const done = field("What was done", { type: "textarea", rows: 4, required: true, value: paper.done ?? "" });
      const found = field("What was found", { type: "textarea", rows: 3, value: paper.found ?? "" });
      const evidence = field("Evidence", { value: paper.evidence.join(", "), hint: "References of evidence items, such as EV-0012, separated by commas." });
      const problem = banner();
      const go = button("Record it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const ok = await submit({ button: go, banner: problem, fields: { done, found, evidence },
          run: () => put(`/api/v1/workpapers/${paper.id}`, { done: done.input.value, found: found.input.value || null,
            evidence: evidence.input.value.split(",").map((ref) => ref.trim()).filter(Boolean) }) });
        if (!ok) return;
        close();
        toast(paper.signed_off_at ? "Recorded. It needs signing off again." : "Recorded.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, done.node, found.node, evidence.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function stepForm(engagement, onDone) {
  openOverlay({ title: "Add a step of the work", subtitle: engagement.name,
    render: (body, footer, close) => {
      const title = field("Step", { required: true, maxlength: 200, hint: "Such as “Restores are tested”." });
      const procedure = field("What is to be done", { type: "textarea", rows: 3 });
      const problem = banner();
      const go = button("Add it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const ok = await submit({ button: go, banner: problem, fields: { title, procedure },
          run: () => post(`/api/v1/engagements/${engagement.ref}/workpapers`, { title: title.input.value, procedure: procedure.input.value || null }) });
        if (!ok) return;
        close();
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, title.node, procedure.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function workpaper(engagement, paper, reload) {
  const working = engagement.can.work && ["fieldwork", "reporting"].includes(engagement.status);
  const act = async (call, said) => {
    try {
      await call();
      if (said) toast(said);
      reload();
    } catch (error) {
      toast(error.detail || "That did not work.");
    }
  };
  const state = paper.signed_off_at ? pill(`Signed off by ${paper.signed_off_by}`, "ok")
    : paper.prepared_at ? pill(`Prepared by ${paper.prepared_by}`, "info") : pill("Not started");
  const open = paper.notes.filter((note) => !note.cleared_at).length;
  return card({ title: `${paper.sequence}. ${paper.title}`, actions: state },
    h("div", { class: "stack" },
      paper.procedure ? h("p", { class: "muted" }, paper.procedure) : null,
      paper.done ? h("div", {}, h("div", { class: "label" }, "What was done"), h("p", {}, paper.done)) : null,
      paper.found ? h("div", {}, h("div", { class: "label" }, "What was found"), h("p", {}, paper.found)) : null,
      paper.evidence.length ? h("p", {}, "Evidence: ", paper.evidence.map((ref, index) => [index ? ", " : "", h("a", { href: `/evidence/${ref}` }, ref)])) : null,
      paper.notes.length ? h("div", { class: "stack-sm" }, h("div", { class: "label" }, `Review notes${open ? ` (${open} open)` : ""}`),
        h("ul", { class: "plain-list stack-sm" }, paper.notes.map((note) => h("li", {},
          h("div", {}, h("strong", {}, note.by), ": ", note.note, note.cleared_at ? pill("Cleared", "ok") : null),
          note.answer ? h("div", { class: "muted" }, "Answered: ", note.answer) : null,
          working && !note.cleared_at && !note.answer && paper.mine ? button("Answer", { kind: "btn-sm", onclick: () => ask("Answer the note", "What was done about it", { required: true, run: (text) => post(`/api/v1/review-notes/${note.id}/answer`, { answer: text }), done: reload }) }) : null,
          working && !note.cleared_at && note.answer && note.mine ? button("Clear", { kind: "btn-sm", onclick: () => act(() => post(`/api/v1/review-notes/${note.id}/clear`), "Cleared.") }) : null)))) : null,
      working ? h("div", { class: "row-sm wrap no-print" },
        button(paper.prepared_at ? "Record again" : "Record the work", { kind: "btn-sm", onclick: () => workForm(paper, reload) }),
        paper.prepared_at && !paper.mine && !paper.signed_off_at ? button("Sign off", { kind: "btn-sm btn-primary", onclick: () => act(() => post(`/api/v1/workpapers/${paper.id}/sign-off`), "Signed off.") }) : null,
        paper.prepared_at && !paper.mine ? button("Add a review note", { kind: "btn-sm btn-ghost", onclick: () => ask("Add a review note", "What needs looking at", { required: true, run: (text) => post(`/api/v1/workpapers/${paper.id}/notes`, { note: text }), done: reload }) }) : null) : null));
}

export function engagementPage(main, { ref }) {
  return show(main, {
    title: ref,
    load: async () => (await get(`/api/v1/engagements/${ref}`, null, { fresh: true })).data,
    view: (data, reload) => {
      const reached = STAGES.findIndex(([key]) => key === data.status);
      const stages = data.status === "dropped" ? null : h("ol", { class: "stages", "aria-label": "Stages" }, STAGES.map(([key, label], index) =>
        h("li", { class: index < reached ? "stage-done" : index === reached ? "stage-now" : "", "aria-current": index === reached ? "step" : null }, label)));
      const actions = h("div", { class: "row-sm wrap" },
        data.can.start ? button("Start it", { kind: "btn-primary", onclick: () => startForm(data, reload) }) : null,
        data.can.advance && !data.waiting ? button(ADVANCE[data.next], { kind: "btn-primary", onclick: () => advanceForm(data, reload) }) : null,
        data.can.advance && data.waiting ? h("span", { class: "subtle" }, `${ADVANCE[data.next]}: ${data.waiting}`) : null,
        data.can.work && ["planning", "fieldwork"].includes(data.status) ? button("Add a step", { iconName: "plus", onclick: () => stepForm(data, reload) }) : null);
      const entity = data.entity.kind === "unit" ? data.entity.name : h("a", { href: `/${PATHS[data.entity.kind]}/${data.entity.ref}` }, data.entity.name);
      return h("div", { class: "stack-lg" },
        data.plan ? h("a", { class: "back-link", href: `/audit/plans/${data.plan.ref}` }, data.plan.name) : null,
        pageHeader({ eyebrow: `Engagement · ${data.ref}`, title: data.name, actions }),
        h("p", {}, `${data.entity.kind_label}: `, entity, `. ${data.reason ?? ""}`),
        stages,
        data.status === "dropped" ? alert("info", h("strong", {}, "Dropped. "), data.dropped_reason ?? "") : null,
        data.restricted ? alert("info", h("strong", {}, "Work in progress. "), "Until its report is issued, an engagement's work is seen by its team alone.") : null,
        h("div", { class: "grid-2" },
          card({ title: "Team" }, data.team.length ? h("ul", { class: "plain-list stack-sm" }, data.team.map((each) => h("li", {}, each.name, each.role === "lead" ? h("span", { class: "subtle" }, " · lead") : null)))
            : h("p", { class: "muted" }, "Not started yet.")),
          card({ title: "Progress" }, h("p", {}, `${data.progress.steps} steps; ${data.progress.prepared} prepared; ${data.progress.signed_off} signed off.`),
            data.started_on ? h("p", { class: "subtle" }, `Started ${date(data.started_on)}${data.fieldwork_on ? `; fieldwork from ${date(data.fieldwork_on)}` : ""}${data.reported_on ? `; reported ${date(data.reported_on)}` : ""}.`) : null)),
        data.report ? card({ title: `Report: ${data.report.opinion_label}` }, h("p", {}, data.report.summary)) : null,
        data.scope_note ? card({ title: "What it covers" }, h("p", {}, data.scope_note)) : null,
        data.restricted ? null : requestsCard(data, reload),
        data.restricted ? null : data.workpapers.length ? h("div", { class: "stack" }, h("h2", {}, "Program of work"), data.workpapers.map((paper) => workpaper(data, paper, reload)))
          : data.status !== "planned" && data.status !== "dropped" ? emptyState({ iconName: "file", title: "No steps yet", text: "Plan the work as steps; each has a workpaper." }) : null);
    },
  });
}


// --- Requests to the audited ------------------------------------------------------------------

const REQUEST_STATUS = { open: ["Open", "info"], answered: ["Answered", "accent"], accepted: ["Accepted", "ok"] };

function askForm(engagement, onDone) {
  openOverlay({ title: "Ask for something", subtitle: `${engagement.ref} · ${engagement.name}. The person asked sees what is asked, by whom, and by when, and nothing else of the engagement.`,
    render: (body, footer, close) => {
      const what = field("What is needed", { type: "textarea", rows: 3, required: true, hint: "Such as “The last full restore test of research storage, with its result”." });
      const who = personField("Asked of");
      const soon = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
      const due = field("By", { type: "date", value: soon, required: true });
      const problem = banner();
      const go = button("Ask", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { what, assignee: who, due_on: due },
          run: () => post(`/api/v1/engagements/${engagement.ref}/requests`, { what: what.input.value, assignee: who.value(), due_on: due.input.value }) });
        if (!done) return;
        close();
        toast("Asked. It is on their home page.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, what.node, who.node, due.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function requestsCard(engagement, reload) {
  const asking = engagement.can.work && ["planning", "fieldwork"].includes(engagement.status);
  const rows = engagement.requests.map((item) => h("tr", {},
    h("td", {}, h("a", { class: "cell-main", href: `/audit/requests/${item.id}` }, item.what)),
    h("td", {}, item.assignee.name),
    h("td", {}, date(item.due_on), item.overdue ? h("div", { class: "cell-sub warn-text" }, "Past its date") : null),
    h("td", {}, pill(...REQUEST_STATUS[item.status]))));
  return card({ title: "Requests to the audited", flush: rows.length > 0, actions: asking ? button("Ask for something", { kind: "btn-sm", onclick: () => askForm(engagement, reload) }) : null },
    rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "What"), h("th", { scope: "col" }, "Asked of"), h("th", { scope: "col" }, "By"), h("th", { scope: "col" }, "Where it stands"))),
      h("tbody", {}, rows)))
      : h("p", { class: "muted" }, "Nothing asked yet."));
}

export function requestPage(main, { id }) {
  return show(main, {
    title: "Internal audit asks",
    load: async () => (await get(`/api/v1/audit/requests/${id}`, null, { fresh: true })).data,
    view: (item, reload) => {
      const header = pageHeader({ eyebrow: `Internal audit · ${item.engagement.ref}`, title: "Internal audit asks",
        lede: `For ${item.engagement.name}, asked by ${item.asked_by} on ${date(item.asked_at)}, of ${item.assignee.name}, by ${date(item.due_on)}.` });
      const asked = card({ title: "What is needed", actions: pill(...REQUEST_STATUS[item.status]) }, h("p", {}, item.what),
        item.returned_reason && item.status === "open" ? alert("warn", h("strong", {}, "Sent back. "), item.returned_reason) : null);
      const answered = item.status !== "open" || item.answer ? card({ title: "The answer" },
        item.answer ? h("p", {}, item.answer) : null,
        item.evidence.length ? h("p", {}, "Evidence: ", item.evidence.map((ref, index) => [index ? ", " : "", h("a", { href: `/evidence/${ref}` }, ref)])) : null,
        item.accepted_at ? h("p", { class: "subtle" }, `Accepted by ${item.accepted_by} on ${date(item.accepted_at)}.`) : null,
        item.team && item.status === "answered" ? h("div", { class: "row-sm" },
          button("Accept it", { kind: "btn-primary", onclick: async () => { await post(`/api/v1/audit/requests/${item.id}/accept`); toast("Accepted."); reload(); } }),
          button("Send it back", { onclick: () => ask("Send it back", "What is still needed", { required: true, run: (why) => post(`/api/v1/audit/requests/${item.id}/return`, { reason: why }), done: reload }) })) : null) : null;
      let form = null;
      if (item.mine && item.status === "open") {
        const words = field("Your answer", { type: "textarea", rows: 4 });
        const picks = item.on_file.map((each) => ({ ref: each.ref, box: checkbox(`${each.ref} ${each.name}`, { hint: each.valid_until ? `Holds until ${date(each.valid_until)}` : null }) }));
        const more = field("Other evidence", { hint: "References of other items of evidence, such as EV-0012, separated by commas. Add a new item under Compliance, Evidence, first." });
        const problem = banner();
        const go = button("Send the answer", { kind: "btn-primary" });
        go.addEventListener("click", async () => {
          const refs = [...picks.filter((each) => each.box.input.checked).map((each) => each.ref), ...more.input.value.split(",").map((ref) => ref.trim()).filter(Boolean)];
          const done = await submit({ button: go, banner: problem, fields: { answer: words, evidence: more },
            run: () => post(`/api/v1/audit/requests/${item.id}/answer`, { answer: words.input.value || null, evidence: refs }) });
          if (!done) return;
          toast("Sent. Internal audit will read it.");
          reload();
        });
        form = card({ title: "Answer it" }, h("div", { class: "stack-lg" }, problem, words.node,
          picks.length ? section("Already on file", h("p", { class: "subtle" }, "Evidence kept about what is being audited. Choose what answers the request; nothing needs sending twice."), picks.map((each) => each.box.node)) : null,
          more.node, h("div", { class: "row" }, go)));
      }
      return h("div", { class: "stack-lg" }, header, asked, form, answered);
    },
  });
}
