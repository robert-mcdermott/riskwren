// What an incident taught the register: the risks it realized, the controls that failed or
// held, why it happened, what was learned, what it cost, and the issues raised from it.

import { post, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime } from "../core/format.js";
import { label, options } from "../core/lookups.js";
import { session } from "../core/session.js";
import { banner, field, section, select, submit } from "../components/form.js";
import { recordPicker, severityPill } from "../components/issue.js";
import { openOverlay } from "../components/overlay.js";
import { personField } from "../components/people-picker.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { card, pill } from "../components/ui.js";
import { prose } from "./record.js";

const KINDS = [["response", "Responding to it"], ["recovery", "Recovering from it"], ["lost_revenue", "Revenue or funding lost"],
  ["notification", "Notifying people"], ["legal", "Legal costs"], ["fines", "Fines and penalties"], ["other", "Other"]];

export function money(totals) {
  const entries = Object.entries(totals ?? {});
  if (!entries.length) return "None recorded";
  return entries.map(([currency, amount]) => new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount)).join(" + ");
}

function overlay(title, subtitle, build, run, done) {
  openOverlay({ title, subtitle, render: (body, footer, close) => {
    const { nodes, fields, values } = build();
    const problem = banner();
    const save = button("Save", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const ok = await submit({ button: save, banner: problem, fields, run: () => run(values()) });
      if (!ok) return;
      close();
      done(ok);
    });
    body.append(h("div", { class: "stack-lg" }, problem, ...nodes));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function learningForm(record, vocab, reload) {
  overlay("What it taught", "The risks it realized, the controls that failed or held, why it happened, and what was learned.", () => {
    const realized = [...record.links.realized];
    const failed = [...record.links.failed];
    const held = [...record.links.held];
    const cause = select("Why it happened", options(vocab, "root_causes", { blank: "Not yet known" }), { value: record.root_cause ?? "" });
    const lessons = field("What was learned", { type: "textarea", rows: 5, value: record.lessons ?? "",
      hint: "What will be done differently. Needed before a high or critical incident is closed." });
    return {
      nodes: [
        section("Risks it realized", recordPicker({ types: ["risk"], chosen: realized, label: "Add a risk", placeholder: "Search risks", empty: "None named." })),
        section("Controls that failed", recordPicker({ types: ["control"], chosen: failed, label: "Add a control", placeholder: "Search controls", empty: "None named." })),
        section("Controls that held", recordPicker({ types: ["control"], chosen: held, label: "Add a control", placeholder: "Search controls", empty: "None named." })),
        section("What was learned", cause.node, lessons.node)],
      fields: { root_cause: cause, lessons },
      values: () => ({ realized: realized.map((each) => each.ref), failed: failed.map((each) => each.ref), held: held.map((each) => each.ref),
        root_cause: cause.input.value || null, lessons: lessons.input.value || null }),
    };
  }, (values) => put(`/api/v1/incidents/${record.ref}/learning`, values), () => {
    toast("Saved.");
    reload();
  });
}

function lossForm(record, reload) {
  overlay("Record a cost", "One amount, of one kind. A cost is never edited: to correct one, record the difference, which may be negative.", () => {
    const kind = select("What kind of cost", KINDS, { value: "response" });
    const amount = field("Amount, in whole units", { type: "number", required: true, step: 1 });
    const currency = field("Currency", { value: "USD", maxlength: 3 });
    const note = field("What it was for", { type: "textarea", rows: 2 });
    return { nodes: [kind.node, h("div", { class: "grid-2" }, amount.node, currency.node), note.node], fields: { kind, amount, currency, note },
      values: () => ({ kind: kind.input.value, amount: amount.input.value === "" ? null : Number(amount.input.value), currency: currency.input.value || "USD", note: note.input.value || null }) };
  }, (values) => post(`/api/v1/incidents/${record.ref}/losses`, values), () => {
    toast("Recorded.");
    reload();
  });
}

function issueForm(record, vocab, reload) {
  overlay("Raise an issue from it", "Something it showed must be put right: an issue in the one register, with this incident as its source.", () => {
    const name = field("What is wrong", { required: true, maxlength: 200 });
    const summary = field("What it showed", { type: "textarea", rows: 3 });
    const severity = select("Severity", options(vocab, "issue_severities", { blank: "Choose…" }), { required: true });
    const about = [...record.links.failed, ...record.links.realized];
    const me = session()?.account;
    const owner = personField("Who puts it right", { value: me ? { account_id: me.id, name: me.name } : null });
    return {
      nodes: [name.node, summary.node, severity.node,
        section("What it is about", recordPicker({ types: ["control", "risk", "scope"], chosen: about, label: "Add a control, a risk, or a scope", placeholder: "Search", empty: "Nothing named." })),
        owner.node],
      fields: { name, summary, severity, owner_id: owner },
      values: () => ({ name: name.input.value, summary: summary.input.value || null, severity: severity.input.value || null,
        subjects: about.map((each) => each.ref), owner_id: owner.value() }),
    };
  }, (values) => post(`/api/v1/incidents/${record.ref}/issues`, values), () => {
    toast("Raised.");
    reload();
  });
}

/** The cards an incident's handlers see beneath what happened. */
export function learningCards(record, vocab, reload) {
  const can = record.can?.edit && record.status !== "closed";
  const links = record.links;
  const named = (list, empty) => (list.length ? h("div", { class: "row wrap" }, list.map((chip) => recordChip(chip))) : h("p", { class: "muted" }, empty));
  return [
    card({ title: "What it taught", actions: can ? button(record.lessons || links.realized.length ? "Change" : "Say what it taught", { kind: "btn-sm", onclick: () => learningForm(record, vocab, reload) }) : null },
      h("div", { class: "stack" },
        h("div", {}, h("div", { class: "label" }, "Risks it realized"), named(links.realized, "None named.")),
        h("div", {}, h("div", { class: "label" }, "Controls that failed"), named(links.failed, "None named.")),
        h("div", {}, h("div", { class: "label" }, "Controls that held"), named(links.held, "None named.")),
        links.hidden ? h("p", { class: "subtle" }, `And ${links.hidden} more that you do not have access to.`) : null,
        record.root_cause ? h("p", {}, h("strong", {}, "Why it happened: "), label(vocab, "root_causes", record.root_cause)) : null,
        record.lessons ? h("div", {}, h("div", { class: "label" }, "What was learned"), prose(record.lessons)) : null,
        record.close_blocked && record.status !== "closed" ? h("p", { class: "warn-text" }, record.close_blocked) : null)),
    card({ title: "What it cost", actions: can ? button("Record a cost", { kind: "btn-sm", onclick: () => lossForm(record, reload) }) : null },
      record.losses.length ? h("div", { class: "stack" },
        h("p", {}, h("strong", {}, "In all: "), money(record.loss_totals)),
        h("ul", { class: "plain-list stack-sm" }, record.losses.map((row) => h("li", {},
          h("span", { class: "cell-main" }, `${money({ [row.currency]: row.amount })} · ${row.label}`),
          h("div", { class: "cell-sub" }, [row.note, `${row.by}, ${dateTime(row.at)}`].filter(Boolean).join(" · "))))))
        : h("p", { class: "muted" }, "Nothing recorded. A near miss usually costs nothing; an incident's costs are worth counting, so the register can weigh its risks against what they have cost.")),
    card({ title: "Issues raised from it", actions: can ? button("Raise an issue", { kind: "btn-sm", onclick: () => issueForm(record, vocab, reload) }) : null },
      record.issues.length ? h("ul", { class: "plain-list stack-sm" }, record.issues.map((issue) => h("li", { class: "row wrap" },
        h("a", { class: "cell-main", href: `/issues/${issue.ref}` }, `${issue.ref} ${issue.name}`), severityPill(issue.severity),
        pill(issue.status === "open" ? `Due ${date(issue.due_on)}` : issue.status, issue.status === "open" ? "info" : ""))))
        : h("p", { class: "muted" }, "None yet. What it showed must be put right is raised here, as an issue with this incident as its source.")),
  ];
}
