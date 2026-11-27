// Tiering a third party: the questions, what the inventory suggests and from which records,
// the tier the program's rules give as the answers change, and the person's own judgment.
// The server works the tier out again when it is recorded; its answer is the one kept.

import { get, post } from "../core/api.js";
import { evaluate } from "../core/conditions.js";
import { button, h } from "../core/dom.js";
import { relative } from "../core/format.js";
import { banner, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { asAsked, questionnaireForm } from "./questionnaire.js";
import { recordChip } from "./record.js";
import { toast } from "./toast.js";
import { alert, card } from "./ui.js";

const NOTHING_HOLDS = "None of the rules of a higher tier holds.";

/** The tier the rules give, and the reasons of it that hold: the server's rule, repeated. */
export function tierFor(tiers, answers, facts) {
  const context = { answers, facts };
  for (const tier of tiers.slice(0, -1)) {
    const held = (tier.rules ?? []).filter((rule) => rule.when && evaluate(rule.when, context)).map((rule) => rule.reason);
    if (held.length) return { tier, reasons: held };
  }
  return { tier: tiers[tiers.length - 1], reasons: [NOTHING_HOLDS] };
}

// The records a fact comes from. The third party itself is "its own record", not a chip.
function chips(found, self) {
  if (!found || (!found.records.length && !found.hidden)) return null;
  const others = found.records.filter((record) => record.ref !== self);
  const own = others.length < found.records.length;
  return h("span", { class: "row-sm wrap" }, own ? h("span", { class: "subtle" }, "its own record") : null,
    others.map((record) => recordChip(record)),
    found.hidden ? h("span", { class: "subtle" }, `and ${found.hidden} you do not have access to`) : null);
}

/** What the inventory says about it, with the records each fact comes from. */
function fromInventory(view, vocab, self) {
  const f = view.facts;
  const words = (name, key) => vocab?.[name]?.find((item) => item.key === key)?.label ?? key;
  const rows = [
    f.data_class ? ["Most sensitive information", h("div", { class: "stack-sm" }, words("data_classes", f.data_class), chips(view.from.data_class, self))] : null,
    f.information.length ? ["Information it holds or handles", chips(view.from.information, self)] : null,
    f.criticality ? ["Most critical work that relies on it", h("div", { class: "stack-sm" }, words("criticalities", f.criticality), chips(view.from.criticality, self))] : null,
    f.systems.length ? ["Systems it reaches", chips(view.from.systems, self)] : null,
  ].filter(Boolean);
  if (!rows.length) return h("p", { class: "muted" }, "The inventory says nothing yet about what it holds, reaches, or supports. Link its services to the systems they reach and the information they handle, and it will.");
  return h("dl", { class: "dl" }, rows.map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]));
}

export async function openTiering(record, { onDone, view = null }) {
  const [data, vocab] = await Promise.all([
    view ? { data: view } : get(`/api/v1/third-parties/${record.ref}/tiering`, null, { fresh: true }),
    get("/api/v1/vocabularies"),
  ]);
  const info = data.data;
  const latest = info.tierings.find((each) => each.current);
  // The inventory's suggestions where it has any; otherwise what was said last time.
  const initial = { ...(latest?.answers ?? {}), ...info.suggested_answers };
  openOverlay({
    title: latest ? "Tier it again" : "Tier it",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const outcome = h("div", { "aria-live": "polite" });
      const choice = select("Tier to record", [["", "As the rules give"], ...info.tiers.map((tier) => [tier.key, tier.label])], { value: "" });
      const rationale = field("Why it should be different", { type: "textarea", rows: 3, hint: "Needed when the tier you record is not the one the rules give." });
      let form = null;
      const redraw = () => {
        if (!form) return; // the form draws itself once before it is kept here
        const given = tierFor(info.tiers, form.answers(), info.facts);
        const chosen = choice.input.value;
        rationale.node.hidden = !chosen || chosen === given.tier.key;
        outcome.replaceChildren(alert("info", h("div", { class: "stack-sm" },
          h("div", { class: "cell-main" }, `The rules give ${given.tier.label}`),
          given.tier.description ? h("div", { class: "subtle" }, given.tier.description) : null,
          h("ul", { class: "plain-list stack-sm" }, given.reasons.map((reason) => h("li", {}, reason))))));
      };
      form = questionnaireForm(info.document, initial, { onChange: () => redraw() });
      choice.input.addEventListener("change", redraw);
      redraw();
      const saveButton = button("Record the tier", { kind: "btn-primary" });
      const save = async () => {
        const missing = form.missing();
        form.setErrors(missing);
        if (Object.keys(missing).length) return;
        const done = await submit({ button: saveButton, banner: problem, fields: { tier: choice, rationale },
          run: () => post(`/api/v1/third-parties/${record.ref}/tiering`, {
            answers: form.answers(), tier: choice.input.value || null, rationale: rationale.input.value || null }) });
        if (!done) return;
        close();
        const kept = done.data.tierings[0];
        toast(`${record.name} is ${kept.tier_label}.`);
        onDone?.();
      };
      body.append(h("div", { class: "stack-lg" }, problem,
        card({ title: "From the inventory" }, fromInventory(info, vocab.data, record.ref),
          h("p", { class: "subtle" }, "Answers the inventory suggests are filled in. Change any that are wrong, and correct the inventory too.")),
        form.node, outcome, choice.node, rationale.node));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** The tierings so far: the one in force with its answers, and the earlier ones. */
export function tieringDetail(view, { record, onTier }) {
  const [current, ...earlier] = view.tierings;
  const said = (row) => (row.tier === row.suggested ? `${row.tier_label}, as the rules give` : `${row.tier_label}, where the rules give ${row.suggested_label}`);
  return h("div", { class: "stack-lg" },
    card({ title: said(current), actions: record.can_tier ? button("Tier it again", { kind: "btn-sm", iconName: "edit", onclick: onTier }) : null },
      h("p", { class: "subtle" }, `By ${current.by}, ${relative(current.at)}.`),
      current.tier === current.suggested
        ? h("ul", { class: "plain-list stack-sm" }, current.reasons.map((reason) => h("li", {}, reason)))
        : h("div", { class: "stack-sm" }, h("div", { class: "cell-main" }, "Why it differs"), h("p", {}, current.rationale),
          h("div", { class: "cell-main" }, `Why the rules give ${current.suggested_label}`),
          h("ul", { class: "plain-list stack-sm" }, current.reasons.map((reason) => h("li", {}, reason))))),
    card({ title: "The answers" }, asAsked(current.as_asked)),
    earlier.length ? card({ title: "Earlier tierings" }, h("ul", { class: "plain-list stack" }, earlier.map((row) => h("li", {},
      h("details", {}, h("summary", {}, `${said(row)} · ${row.by}, ${relative(row.at)}`),
        row.rationale ? h("p", {}, row.rationale) : null, asAsked(row.as_asked)))))) : null);
}
