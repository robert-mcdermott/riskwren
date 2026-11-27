// The fields of a report of an incident, a near miss, or a concern: shared by the form for
// those signed in and the page that needs no name.

import { h } from "../core/dom.js";
import { unitOptions } from "../core/lookups.js";
import { field, select } from "./form.js";

export const KIND = {
  incident: ["Incident", "Something went wrong: information, a system, or people were affected"],
  near_miss: ["Near miss", "Something nearly went wrong, and was caught in time"],
  concern: ["Concern", "Something that worries you and may need looking into"],
};

/** The fields of a report, shared by the signed-in form and the page that needs no name. */
export function reportFields({ unitIndex = null, unitValue = "" } = {}) {
  const kind = select("What is it?", Object.entries(KIND).map(([key, [text]]) => [key, text]), { value: "incident",
    hint: Object.values(KIND).map(([text, meaning]) => `${text}: ${meaning.toLowerCase()}.`).join(" ") });
  const name = field("In a line, what happened", { required: true, maxlength: 200, hint: "Such as “Laptop left on the train” or “Email asking for my password”." });
  const summary = field("What happened", { type: "textarea", rows: 5, required: true, hint: "What you saw or did, and anything you have done since. Leave out passwords and patient details." });
  const occurred = field("When it happened", { type: "date", max: new Date().toISOString().slice(0, 10), hint: "Leave it empty if you do not know." });
  const location = field("Where", { maxlength: 200, hint: "A room, a building, a system, or a website." });
  const unit = unitIndex ? select("The unit it happened in", unitOptions(unitIndex.tree, { blank: "Not sure" }), { value: unitValue }) : null;
  const values = () => ({ kind: kind.input.value, name: name.input.value, summary: summary.input.value,
    occurred_on: occurred.input.value || null, location: location.input.value || null,
    ...(unit ? { org_unit_id: unit.input.value ? Number(unit.input.value) : null } : {}) });
  const fields = { kind, name, summary, occurred_on: occurred, location, ...(unit ? { org_unit_id: unit } : {}) };
  return { nodes: [kind.node, name.node, summary.node, h("div", { class: "grid-2" }, occurred.node, location.node), unit?.node], values, fields };
}
