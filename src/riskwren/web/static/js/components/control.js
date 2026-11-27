// How a control and what is known of it are shown, and the forms that add, edit, and rate one.

import { similarHint } from "./tidy.js";
import { get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date } from "../core/format.js";
import { options, unitOptions } from "../core/lookups.js";
import { navigate } from "../core/router.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { section } from "./form.js";
import { ownUnits } from "../core/session.js";
import { levelPicker } from "./risk.js";
import { toast } from "./toast.js";
import { pill } from "./ui.js";

// What is known about a control: a word, a mark, and a tone. Unknown is never shown as fine.
export const STATES = {
  effective: ["Effective", "ok", "●"],
  partly: ["Partly effective", "warn", "◐"],
  ineffective: ["Ineffective", "danger", "✕"],
  not_assessed: ["Not assessed", "", "○"],
  stale: ["Rating out of date", "warn", "↻"],
};

export function statePill(state) {
  const [text, tone, mark] = STATES[state] ?? [state, "", "○"];
  const node = pill("", tone);
  node.append(h("span", { "aria-hidden": "true" }, mark), text);
  return node;
}

export function stateOptions(blank) {
  return [["", blank], ...["effective", "partly", "ineffective", "not_assessed"].map((key) => [key, STATES[key][0]])];
}

export const REDUCES = [["likelihood", "Likelihood"], ["impact", "Impact"], ["both", "Both"]];
export const RELIANCE = [["primary", "Primary: the risk relies on it"], ["supporting", "Supporting: it helps"]];

export function reducesLabel(key) {
  return { likelihood: "Reduces likelihood", impact: "Reduces impact", both: "Reduces both" }[key] ?? key;
}

/** Add a control, or edit the one given. A new one can be started from the library of common controls. */
export function editControl({ record = null, vocab, units, from = null, unitId = null, onDone = null }) {
  openOverlay({
    title: record ? "Edit control" : "Add a control",
    subtitle: record ? record.ref : "Something the organization does to reduce a risk, described once.",
    render: (body, footer, close) => {
      const name = field("Title", { value: record?.name ?? from?.title ?? "", required: true, hint: "A few words. For example: Backups tested by restoring." });
      const statement = field("Statement", { type: "textarea", value: record?.statement ?? from?.statement ?? "", required: true,
        hint: "One sentence: who does what, and how often." });
      const objective = field("Objective", { type: "textarea", value: record?.objective ?? "", hint: "Optional. What it is meant to prevent, detect, or put right." });
      const kind = select("Kind", options(vocab, "control_kinds", { blank: record || from ? null : "Choose…" }), { value: record?.kind ?? from?.kind ?? "", required: true });
      const nature = select("Nature", options(vocab, "control_natures", { blank: "Not said" }), { value: record?.nature ?? from?.nature ?? "" });
      const frequency = select("How often", options(vocab, "control_frequencies", { blank: "Not said" }), { value: record?.frequency ?? from?.frequency ?? "" });
      const unit = select("Unit", unitOptions(units.tree, { only: ownUnits(), blank: record || unitId ? null : "Choose…" }),
        { value: record?.org_unit_id ?? unitId ?? "", required: true, hint: "The unit that operates it." });
      const key = checkbox("Key control", { checked: record?.is_key ?? false, hint: "One that a serious risk depends on above all others." });
      const restricted = checkbox("Restricted", { checked: record?.restricted ?? false });
      const status = record ? select("Status", [["active", "Active"], ["retired", "Retired"]], { value: record.status }) : null;
      let libraryKey = from?.key ?? null;

      const found = h("div", { class: "pick-results", role: "listbox", "aria-label": "Library controls found" });
      const search = h("input", { class: "input", type: "search", placeholder: "Search the library: backup, access, training…", "aria-label": "Search the control library" });
      let latest = 0;
      const look = async () => {
        const mine = ++latest;
        const words = search.value.trim();
        if (words.length < 2) {
          found.replaceChildren();
          return;
        }
        const entries = (await get("/api/v1/control-library", { q: words })).data.slice(0, 6);
        if (mine !== latest) return;
        found.replaceChildren(...(entries.length ? entries.map((entry) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
          name.input.value = entry.title;
          statement.input.value = entry.statement;
          kind.input.value = entry.kind;
          nature.input.value = entry.nature ?? "";
          frequency.input.value = entry.frequency ?? "";
          libraryKey = entry.key;
          search.value = "";
          found.replaceChildren();
          name.input.focus();
        } }, icon("control"), h("span", {}, h("span", { class: "cell-main" }, entry.title), h("div", { class: "cell-sub" }, entry.statement))))
          : [h("div", { class: "subtle pick-none" }, "Nothing in the library matches. Write it below.")]));
      };
      let timer = null;
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(look, 180);
      });

      const problem = banner();
      const saveButton = button(record ? "Save" : "Add", { kind: "btn-primary" });
      const fields = { name, statement, objective, kind, nature, frequency, org_unit_id: unit, ...(status ? { status } : {}) };
      const values = () => ({
        name: name.input.value, statement: statement.input.value, objective: objective.input.value,
        kind: kind.input.value, nature: nature.input.value || null, frequency: frequency.input.value || null,
        org_unit_id: unit.input.value ? Number(unit.input.value) : null, is_key: key.input.checked, restricted: restricted.input.checked,
        ...(status ? { status: status.input.value } : { library_key: libraryKey }),
      });
      const save = async () => {
        const done = await submit({ button: saveButton, fields, banner: problem,
          run: () => (record ? patch(`/api/v1/controls/${record.ref}`, { version: record.version, ...values() }) : post("/api/v1/controls", values())) });
        if (!done) return;
        close();
        if (record || !onDone) toast(record ? "Saved." : `${done.data.ref} was added.`);
        if (onDone) onDone(done.data);
        else if (!record) navigate(`/controls/${done.data.ref}`);
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (submitted) => {
        submitted.preventDefault();
        save();
      } }, problem,
      record || from ? null : section("Start from the library", h("div", { class: "field" }, search, found),
        h("p", { class: "hint subtle" }, "Optional. Common controls in plain words, to make your own.")),
      section("What is done", name.node, similarHint("control", name.input, { unit: () => unit.input.value, apartFrom: record?.ref }), statement.node, objective.node),
      section("How", h("div", { class: "grid-2" }, kind.node, nature.node), h("div", { class: "grid-2" }, frequency.node, unit.node), key.node),
      section("Who may see it", restricted.node, status?.node ?? null)));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

const LEVELS = [
  { level: 3, key: "effective", label: "Effective" },
  { level: 2, key: "partly", label: "Partly" },
  { level: 1, key: "ineffective", label: "Ineffective" },
];
const DESIGN = { 3: "It would reduce the risk, if it operated as described.", 2: "It would reduce the risk somewhat, with gaps.", 1: "As described, it would not reduce the risk." };
const OPERATION = { 3: "It operates as described.", 2: "It operates, but not always or not everywhere.", 1: "It does not operate as described." };

/** Record what is known about whether a control works. A rating is never edited, only superseded. */
export function rateControl({ control, onDone }) {
  openOverlay({
    title: "Rate this control",
    subtitle: `${control.ref} · ${control.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const level = (key) => LEVELS.find((item) => item.key === key)?.level ?? null;
      const picker = (legend, hint, definitions, was) => levelPicker({ legend, hint, allowNone: true, value: level(was),
        levels: LEVELS.map((item) => ({ ...item, definition: definitions[item.level] })) });
      const design = picker("Design", "Would it reduce the risk, if it operated as described?", DESIGN, control.design);
      const operation = picker("Operation", "Does it operate as described?", OPERATION, control.operation);
      const note = field("What this rests on", { type: "textarea", required: true,
        hint: "What was looked at, or what is known. A rating with nothing behind it is only an opinion." });
      const key = (value) => LEVELS.find((item) => item.level === value)?.key ?? "not_assessed";
      const save = button("Record the rating", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { note },
          run: () => post(`/api/v1/controls/${control.ref}/ratings`, { design: key(design.value()), operation: key(operation.value()), note: note.input.value }) });
        if (done) {
          close();
          toast("The rating was recorded.");
          onDone?.(done.data);
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, h("p", { class: "prose muted" }, control.statement),
        section("How well it works", design.node, operation.node,
          h("p", { class: "subtle" }, "The control is as strong as the weaker of the two. One left at None is shown as not assessed, and counts for nothing.")),
        section("The basis", note.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function ratedLine(rating) {
  if (!rating) return h("p", { class: "muted" }, "Nobody has rated this control yet. Until someone does, it counts for nothing when a residual rating is suggested.");
  return h("div", { class: "stack-sm" },
    h("dl", { class: "dl" }, h("dt", {}, "Design"), h("dd", {}, statePill(rating.design)), h("dt", {}, "Operation"), h("dd", {}, statePill(rating.operation))),
    h("p", { class: "prose" }, rating.note),
    h("p", { class: "subtle" }, rating.basis === "test" ? `Tested by ${rating.rated_by} on ${date(rating.rated_at)}, and confirmed by a second person.`
      : `Rated by ${rating.rated_by} on ${date(rating.rated_at)}, on their ${rating.basis}.`));
}
