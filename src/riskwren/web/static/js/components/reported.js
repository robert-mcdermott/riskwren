// What other systems report of a control: shown at once, as its source's, and counted only
// once a person who assesses the control, and does not own it, confirms it.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { dateTime } from "../core/format.js";
import { can } from "../core/session.js";
import { banner, field, select, submit } from "./form.js";
import { closeOverlay, openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { card, pill } from "./ui.js";

const OUTCOMES = { passed: ["Passed", "ok"], partial: ["Partly", "warn"], failed: ["Failed", "danger"] };
const STATES = { reported: ["Waiting for a person", "info"], confirmed: ["Confirmed", "ok"], set_aside: ["Set aside", ""] };

export function outcomePill(row) {
  if (row.kind === "evidence") return pill("Evidence");
  const [word, tone] = OUTCOMES[row.outcome] ?? [row.outcome, ""];
  return pill(word, tone);
}

function decide(row, mode, onDone) {
  openOverlay({
    title: mode === "confirm" ? "Confirm what was reported" : "Set it aside",
    subtitle: `${row.source}: ${row.title}`,
    render: (body, footer) => {
      const failure = row.kind === "result" && row.outcome !== "passed";
      const severity = failure && mode === "confirm" ? select("Severity of the issue it raises",
        [["critical", "Critical"], ["high", "High"], ["moderate", "Moderate"], ["low", "Low"]],
        { value: row.outcome === "failed" ? "high" : "moderate" }) : null;
      const note = field(mode === "confirm" ? "Note (optional)" : "Why it is set aside", { type: "textarea", rows: 3 });
      const problem = banner();
      const go = button(mode === "confirm" ? "Confirm" : "Set aside", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { note, ...(severity ? { severity } : {}) },
          run: () => post(`/api/v1/reported/${row.id}/${mode === "confirm" ? "confirm" : "set-aside"}`,
            { note: note.input.value || null, ...(severity ? { severity: severity.input.value } : {}) }) });
        if (!done) return;
        closeOverlay();
        toast(done.data.issue ? `${done.data.issue.ref} was raised.` : done.data.evidence ? `${done.data.evidence.ref} was filed.` : "Done.");
        onDone();
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", { class: "muted" }, mode === "confirm"
          ? (failure ? "Confirming it raises an issue on the control, as a person's finding would." : row.kind === "evidence" ? "Confirming it files the evidence with the control, counting for a year unless it says otherwise." : "Confirming it keeps it on record as checked.")
          : "Setting it aside keeps it on record, with why, and changes nothing else."),
        severity?.node ?? null, note.node));
      footer.hidden = false;
      footer.append(go, button("Cancel", { kind: "btn-ghost", onclick: closeOverlay }));
    },
  });
}

function rows(list, { withControl = false, reload }) {
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, [withControl ? "Control" : null, "What was reported", "From", "When", "Where it stands", ""].filter((text) => text !== null)
      .map((text) => h("th", { scope: "col" }, text || h("span", { class: "sr-only" }, "Decide"))))),
    h("tbody", {}, list.map((row) => h("tr", {},
      withControl ? h("td", {}, h("a", { href: `/controls/${row.control.ref}`, class: "cell-main" }, row.control.name), h("div", { class: "cell-sub" }, row.control.ref)) : null,
      h("td", {}, h("div", { class: "row-sm" }, outcomePill(row), h("span", { class: "cell-main" }, row.title)),
        row.detail ? h("div", { class: "cell-sub" }, row.detail) : null,
        row.url ? h("div", { class: "cell-sub" }, h("a", { href: row.url, target: "_blank", rel: "noopener noreferrer" }, "Where to see it")) : null),
      h("td", {}, row.source, row.scope ? h("div", { class: "cell-sub" }, `in ${row.scope.ref}`) : null),
      h("td", {}, dateTime(row.observed_at)),
      h("td", {}, pill(...(STATES[row.status] ?? [row.status, ""])),
        row.issue ? h("div", { class: "cell-sub" }, h("a", { href: `/issues/${row.issue.ref}` }, row.issue.ref)) : null,
        row.evidence ? h("div", { class: "cell-sub" }, h("a", { href: `/evidence/${row.evidence.ref}` }, row.evidence.ref)) : null,
        row.decided_by ? h("div", { class: "cell-sub" }, `${row.decided_by}${row.decision_note ? `: ${row.decision_note}` : ""}`) : null),
      h("td", { class: "nowrap" }, row.status === "reported" && can("assess")
        ? h("div", { class: "row-sm" },
          button("Confirm", { kind: "btn-sm", "aria-label": `Confirm ${row.title}`, onclick: () => decide(row, "confirm", reload) }),
          button("Set aside", { kind: "btn-ghost btn-sm", "aria-label": `Set aside ${row.title}`, onclick: () => decide(row, "set_aside", reload) }))
        : null))))));
}

/** The card on a control's page, filled in when it has loaded; nothing when nothing was said. */
export function reportedCard(ref) {
  const holder = h("div");
  const load = async () => {
    const list = (await get(`/api/v1/controls/${ref}/reported`, null, { fresh: true })).data;
    holder.replaceChildren(list.length ? card({ title: "Reported by other systems", flush: true },
      h("div", { class: "card-pad" }, h("p", { class: "muted" }, "What other systems say of this control. It counts for nothing until someone who assesses the control, and does not own it, confirms it.")),
      rows(list, { reload: load })) : "");
  };
  load().catch(() => {});
  return holder;
}

export function reportedRows(list, reload) {
  return rows(list, { withControl: true, reload });
}
