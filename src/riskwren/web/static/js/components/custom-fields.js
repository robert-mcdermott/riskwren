// Fields of the organization's own: asked for in a record's form, and shown on its page.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date } from "../core/format.js";
import { field, select } from "./form.js";
import { card } from "./ui.js";

function input(definition, value) {
  const hint = definition.help || null;
  const label = definition.required ? definition.label : `${definition.label} (optional)`;
  if (definition.kind === "choice") {
    return select(label, [["", definition.required ? "Choose…" : "None"], ...definition.choices.map((choice) => [choice, choice])],
      { value: value ?? "", hint, required: definition.required || undefined });
  }
  const type = definition.kind === "number" ? "number" : definition.kind === "date" ? "date" : "text";
  return field(label, { type, value: value ?? "", hint, maxlength: type === "text" ? 400 : undefined,
    step: type === "number" ? "any" : undefined, required: definition.required || undefined });
}

/**
 * The organization's own fields for a kind of record, as form fields. ``current`` is the
 * record's ``custom`` list when editing one; a new record asks the program for its fields.
 * Returns a node to place, the fields by error name, and the values to send.
 */
export function customFields(type, current = null) {
  const holder = h("div", { class: "stack" });
  const inputs = new Map();
  const fields = {};
  const draw = (definitions) => {
    holder.replaceChildren(...definitions.map((definition) => {
      const made = input(definition, definition.value);
      inputs.set(definition.key, { definition, made });
      fields[`custom.${definition.key}`] = made;
      return made.node;
    }));
  };
  if (current) draw(current);
  else get("/api/v1/program/fields").then((answer) => draw(answer.data.fields[type] ?? [])).catch(() => {});
  return {
    node: holder,
    fields,
    values: () => (inputs.size ? { custom: Object.fromEntries([...inputs].map(([key, { definition, made }]) => {
      const raw = made.input.value.trim();
      return [key, raw === "" ? null : definition.kind === "number" ? Number(raw) : raw];
    })) } : {}),
  };
}

/** A record's own fields and their values, for its page; nothing when the program has none. */
export function customCard(custom) {
  if (!custom?.length) return null;
  const shown = (item) => (item.value == null || item.value === "" ? h("span", { class: "subtle" }, "Not given")
    : item.kind === "date" ? date(item.value) : String(item.value));
  return card({ title: "More about it" }, h("dl", { class: "dl" },
    custom.flatMap((item) => [h("dt", {}, item.label), h("dd", {}, shown(item))])));
}
