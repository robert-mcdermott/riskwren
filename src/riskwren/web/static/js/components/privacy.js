// Privacy impact assessments: where a process's or a system's stands, its concerns, and its
// review; and the state of one in a word, wherever it is listed.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime } from "../core/format.js";
import { banner, field, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { alert, card, pill } from "./ui.js";

const STATE = { never: ["Never assessed", "danger"], asked: ["Asked, not yet answered", "info"], to_review: ["Answered, to review", "warn"],
  current: ["Reviewed", "ok"], due: ["Due again", "danger"] };

export function privacyState(state) {
  const [text, tone] = STATE[state] ?? [state, ""];
  return pill(text, tone);
}

function reviewForm(item, reload) {
  openOverlay({ title: "Review the assessment", render: (body, footer, close) => {
    const note = field("What was made of it", { type: "textarea", rows: 4, hint: "What follows from it: an agreement to draw up, information to stop collecting, nothing." });
    const problem = banner();
    const save = button("Mark it reviewed", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { note }, run: () => post(`/api/v1/privacy/reviews/${item.item_id}`, { note: note.input.value || null }) });
      if (!done) return;
      close();
      toast("Reviewed.");
      reload();
    });
    body.append(h("div", { class: "stack" }, problem, note.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

export function privacyTab(record, reload) {
  const found = record.privacy_impact;
  const last = found.last;
  const needed = found.required
    ? `Its data class is ${record.data_class}, so it needs a privacy impact assessment, done again every ${found.months} months.`
    : "Its data class no longer needs an assessment; the last one is kept here.";
  return h("div", { class: "stack-lg" },
    card({ title: "Privacy impact assessment", actions: privacyState(found.state) }, h("div", { class: "stack" },
      h("p", { class: "muted" }, needed),
      last ? h("dl", { class: "dl" },
        h("dt", {}, "Answered"), h("dd", {}, `${dateTime(last.answered_at)} by ${last.answered_by}`),
        found.due_on ? [h("dt", {}, "Due again"), h("dd", {}, date(found.due_on))] : null,
        last.note ? [h("dt", {}, "Review"), h("dd", {}, last.note)] : null) : null,
      last?.concerns.length ? alert("warn", h("div", {}, h("strong", {}, "Concerns in the answers"),
        h("ul", {}, last.concerns.map((each) => h("li", {}, each))))) : null,
      h("div", { class: "row wrap" },
        last ? h("a", { class: "btn btn-sm", href: `/campaign-items/${last.item_id}` }, "Read the answers") : null,
        found.pending_item ? h("a", { class: "btn btn-sm", href: `/campaign-items/${found.pending_item}` }, "What was asked") : null,
        found.can_review ? button("Review it", { kind: "btn-primary btn-sm", onclick: () => reviewForm(last, reload) }) : null),
      !last && !found.pending_item ? h("p", { class: "subtle" }, "A privacy impact campaign, under Compliance, asks whoever answers for it.") : null)));
}
