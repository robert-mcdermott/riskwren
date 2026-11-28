// The optional assistant, loaded only when it is turned on and someone uses it: a summary of a
// record, and a risk drafted from someone's own words. What it writes is shown as its own, and a
// draft is made into a risk only by a person, in the ordinary form.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { unitOptions } from "../core/lookups.js";
import { documentText } from "./document.js";
import { banner, field, select, submit } from "./form.js";
import { closeOverlay, openOverlay } from "./overlay.js";
import { editRisk } from "./risk-forms.js";

const WHAT_IS_SENT = "What the assistant reads is sent to the provider your organization chose. Restricted records, and records of a data class it is not allowed to send, are kept back. Every exchange is recorded.";

/** A summary of a record, written by the assistant from what the asker may see. */
export function summarize(record) {
  openOverlay({
    title: "Summary by the assistant",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer) => {
      const said = h("div", { class: "stack", "aria-live": "polite", "aria-busy": "true" }, h("p", { class: "muted" }, "The assistant is reading the record…"));
      body.append(said);
      footer.hidden = false;
      footer.append(button("Close", { kind: "btn-ghost", onclick: closeOverlay }));
      post("/api/v1/assistant/summary", { ref: record.ref }).then((done) => {
        said.replaceChildren(
          done.data.answer ? documentText(done.data.answer, { shift: 2, withContents: false }) : h("p", {}, "The assistant gave no answer."),
          h("p", { class: "hint" }, `Written by the assistant from what you may see, using ${done.data.tools_used.length ? done.data.tools_used.join(", ") : "no tools"}. It is not saved on the record. Check it against the record before relying on it.`));
      }).catch((failed) => {
        said.replaceChildren(h("div", { class: "alert alert-danger", role: "alert" }, failed?.detail ?? failed?.message ?? "The assistant could not answer."));
      }).finally(() => said.setAttribute("aria-busy", "false"));
    },
  });
}

/** Describe what could go wrong; the assistant drafts a risk, which opens in the ordinary form. */
export function draftRisk({ program, units, onDone }) {
  openOverlay({
    title: "Draft a risk with the assistant",
    subtitle: "Say what could go wrong, in your own words. You check and change the draft before anything is made.",
    render: (body, footer) => {
      const description = field("What could go wrong", { type: "textarea", rows: 5, required: true, maxlength: 4000,
        hint: "A few sentences: what could happen, what makes it possible, and what it would mean. For example: visiting researchers plug their own laptops into the lab network, and nothing checks them first." });
      const unit = select("Unit", unitOptions(units.tree, { blank: "Let the assistant leave it open" }), { value: "" });
      const problem = banner();
      const go = button("Draft it", { kind: "btn-primary" });
      const told = h("div", { "aria-live": "polite" });
      go.addEventListener("click", async () => {
        told.replaceChildren(h("p", { class: "muted" }, "The assistant is looking for a risk like it, and drafting…"));
        const done = await submit({ button: go, banner: problem, fields: { description },
          run: () => post("/api/v1/assistant/draft-risk", { description: description.input.value, org_unit_id: unit.input.value ? Number(unit.input.value) : null }) });
        if (!done) {
          told.replaceChildren();
          return;
        }
        if (!done.data.draft_id) {
          told.replaceChildren(done.data.answer ? documentText(done.data.answer, { shift: 2, withContents: false }) : h("p", {}, "The assistant did not draft a risk."));
          return;
        }
        closeOverlay();
        const draft = (await get(`/api/v1/drafts/${done.data.draft_id}`, null, { fresh: true })).data;
        editRisk({ draft, program, units, onDone });
      });
      body.append(h("div", { class: "stack" }, problem, description.node, unit.node, h("p", { class: "hint" }, WHAT_IS_SENT), told));
      footer.hidden = false;
      footer.append(go, button("Cancel", { kind: "btn-ghost", onclick: closeOverlay }));
    },
  });
}
