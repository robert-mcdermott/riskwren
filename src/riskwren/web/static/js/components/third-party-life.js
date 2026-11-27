// A third party over time: when it is next reviewed and why, and ending the relationship.
// Fetched with its page's overview.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, relative } from "../core/format.js";
import { banner, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { alert, card, pill } from "./ui.js";

const EVENTS = [["incident", "An incident at the third party"], ["breach_notice", "It told us of a breach"],
  ["service_change", "What it does for us changed"], ["ownership", "It changed hands"], ["finding", "A finding about it"], ["other", "Something else"]];

function ask(record, { title, subtitle, fields, path, values, doneText, onDone, label }) {
  openOverlay({ title, subtitle,
    render: (body, footer, close) => {
      const problem = banner();
      const go = button(label, { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields, run: () => post(path, values()) });
        if (!done) return;
        close();
        toast(doneText);
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, Object.values(fields).map((each) => each.node)));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function callReview(record, onDone) {
  const event = select("What happened", EVENTS, { value: "incident" });
  const note = field("What, and when", { type: "textarea", rows: 3, required: true });
  ask(record, { title: "Call for a review", subtitle: "Whatever its tier's cadence says, it is due for review now.",
    fields: { event, note }, path: `/api/v1/third-parties/${record.ref}/call-review`, label: "Call for a review",
    values: () => ({ event: event.input.value, note: note.input.value }), doneText: "It is due for review now.", onDone });
}

function startOffboarding(record, onDone) {
  const reason = field("Why the relationship ends", { type: "textarea", rows: 3, required: true });
  ask(record, { title: "End the relationship", subtitle: "A checklist opens. When every step is recorded, it and its services are retired.",
    fields: { reason }, path: `/api/v1/third-parties/${record.ref}/offboarding`, label: "Start offboarding",
    values: () => ({ reason: reason.input.value }), doneText: "Offboarding has started.", onDone });
}

function recordStep(record, step, onDone) {
  const note = field("What was done", { type: "textarea", rows: 3, required: true, hint: step.help });
  ask(record, { title: step.label, subtitle: `${record.ref} · ${record.name}`, fields: { note },
    path: `/api/v1/third-parties/${record.ref}/offboarding/steps/${step.key}`, label: "Record it",
    values: () => ({ note: note.input.value }), doneText: "Recorded.", onDone });
}

export function lifecycleCards(record, ctx) {
  const may = record.can_tier;
  const due = record.next_review_on;
  const late = due && due < new Date().toISOString().slice(0, 10);
  const review = card({ title: "Next review",
    actions: may ? button("Call for a review", { kind: "btn-sm", onclick: () => callReview(record, ctx.reload) }) : null },
    due ? h("div", { class: "row wrap" }, h("span", { class: "tier-mark" }, date(due)), late ? pill("Overdue", "danger") : null)
      : h("p", { class: "muted" }, record.status === "active" ? "Not on a cadence: its tier is reviewed only when something calls for it." : "It is retired."),
    record.review_called ? h("p", {}, `Called for: ${record.review_called}`)
      : due ? h("p", { class: "subtle" }, "Its tier's cadence, from its last concluded review, or from when it was first tiered.") : null);
  const off = record.offboarding;
  let ending = null;
  if (off && off.status !== "cancelled") {
    ending = card({ title: off.status === "done" ? "Offboarded" : "Offboarding",
      actions: off.status === "open" && may ? button("Stop offboarding", { kind: "btn-sm btn-ghost", onclick: async () => {
        await post(`/api/v1/third-parties/${record.ref}/offboarding/cancel`, {});
        toast("Offboarding stopped.");
        ctx.reload();
      } }) : null },
      h("p", {}, off.reason),
      h("ul", { class: "plain-list stack" }, off.steps.map((step) => h("li", { class: "row wrap" },
        h("div", { class: "grow" }, h("div", { class: "cell-main" }, step.label),
          h("div", { class: "cell-sub" }, step.done_at ? `${step.note} · ${step.done_by}, ${relative(step.done_at)}` : step.help)),
        step.done_at ? pill("Done", "ok") : may && off.status === "open" ? button("Record it", { kind: "btn-sm", "aria-label": `Record: ${step.label}`, onclick: () => recordStep(record, step, ctx.reload) }) : pill("To do")))),
      off.status === "done" ? alert("info", h("div", {}, `Every step was recorded ${relative(off.finished_at)}, and it was retired with its services.`)) : null);
  } else if (may && record.status === "active") {
    ending = card({ title: "Ending the relationship" },
      h("p", { class: "muted" }, "Ending it opens a checklist: access removed, information returned or destroyed, agreements ended, and its attestation recorded."),
      h("div", {}, button("End the relationship", { kind: "btn-sm btn-ghost", onclick: () => startOffboarding(record, ctx.reload) })));
  }
  return [review, ending];
}
