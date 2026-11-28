// Drafts: what an assistant or another system has proposed, waiting for a person to open it in
// the ordinary form, change what they like, and save it, or to set it aside.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { dateTime } from "../core/format.js";
import { program as loadProgram, units, vocabularies } from "../core/lookups.js";
import { editControl } from "../components/control.js";
import { banner, field, submit } from "../components/form.js";
import { closeOverlay, openOverlay } from "../components/overlay.js";
import { editRisk } from "../components/risk-forms.js";
import { toast } from "../components/toast.js";
import { card, emptyState, pageHeader, pill } from "../components/ui.js";
import { editIssue } from "./issues.js";
import { show } from "./page.js";

const KINDS = { risk: "A risk", issue: "An issue", control: "A control" };

function setAside(draft, reload) {
  openOverlay({
    title: "Set the draft aside",
    subtitle: `${KINDS[draft.kind]}: ${draft.values.name}`,
    render: (body, footer) => {
      const note = field("Why it is set aside", { type: "textarea", rows: 3, required: true });
      const problem = banner();
      const go = button("Set aside", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { note },
          run: () => post(`/api/v1/drafts/${draft.id}/set-aside`, { note: note.input.value || null }) });
        if (!done) return;
        closeOverlay();
        toast("The draft was set aside. Nothing was made.");
        reload();
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", { class: "muted" }, "It stays on record, with why. No record is made of it."), note.node));
      footer.hidden = false;
      footer.append(go, button("Cancel", { kind: "btn-ghost", onclick: closeOverlay }));
    },
  });
}

function open(draft, data, reload) {
  if (draft.kind === "risk") editRisk({ draft, program: data.program, units: data.units, onDone: reload });
  else if (draft.kind === "control") editControl({ draft, vocab: data.vocab, units: data.units });
  else editIssue({ draft, vocab: data.vocab, units: data.units });
}

function said(draft) {
  const values = draft.values;
  const parts = draft.kind === "risk" ? [values.cause, values.event, values.consequence]
    : draft.kind === "control" ? [values.statement] : [values.summary];
  return parts.filter(Boolean).join(" · ");
}

function row(draft, data, reload) {
  const decide = draft.can.use
    ? h("div", { class: "row-sm" },
      button("Open", { kind: "btn-sm", "aria-label": `Open the draft ${draft.values.name}`, onclick: () => open(draft, data, reload) }),
      button("Set aside", { kind: "btn-ghost btn-sm", "aria-label": `Set aside the draft ${draft.values.name}`, onclick: () => setAside(draft, reload) }))
    : h("span", { class: "subtle" }, "Waiting for someone who may make it");
  return h("tr", {},
    h("td", {},
      h("div", { class: "row-sm" }, pill(KINDS[draft.kind] ?? draft.kind), h("span", { class: "cell-main" }, draft.values.name)),
      said(draft) ? h("div", { class: "cell-sub" }, said(draft)) : null,
      draft.why ? h("div", { class: "cell-sub" }, `Rests on: ${draft.why}`) : null),
    h("td", {}, draft.source, draft.org_unit ? h("div", { class: "cell-sub" }, draft.org_unit.name) : null),
    h("td", {}, dateTime(draft.made_at)),
    h("td", { class: "nowrap" }, decide));
}

function table(data, reload) {
  const head = h("thead", {}, h("tr", {}, ["Draft", "From", "When", ""].map((text) => h("th", { scope: "col" }, text || h("span", { class: "sr-only" }, "Decide")))));
  return h("div", { class: "table-wrap" }, h("table", { class: "table" }, head, h("tbody", {}, data.list.map((draft) => row(draft, data, reload)))));
}

export function draftsPage(main) {
  return show(main, {
    title: "Drafts",
    load: async () => {
      const [list, program, vocab, unitIndex] = await Promise.all([
        get("/api/v1/drafts", null, { fresh: true }), loadProgram(), vocabularies(), units()]);
      return { list: list.data, program, vocab, units: unitIndex };
    },
    view: (data, reload) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Work", title: "Drafts",
        lede: "Risks, issues, and controls that an assistant or another system has drafted. Nothing is made until you open one, change what you like, and save it in the ordinary form." }),
      data.list.length ? card({ title: `${data.list.length} waiting`, flush: true }, table(data, reload))
        : emptyState({ title: "No drafts are waiting", text: "When an assistant or another system drafts a risk, an issue, or a control, it waits here for someone who may make it." })),
  });
}
