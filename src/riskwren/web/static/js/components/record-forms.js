// The forms that add and edit inventory records. One form, shaped by what each kind of record has.

import { patch, post } from "../core/api.js";
import { button, h, uid } from "../core/dom.js";
import { options, unitOptions } from "../core/lookups.js";
import { navigate } from "../core/router.js";
import { can, session } from "../core/session.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { statusLabel, TYPES } from "./record.js";
import { toast } from "./toast.js";

/**
 * The data class: one choice from an ordered list, each with its meaning and, on request,
 * examples. People pick the right class when they can recognize their own data in it.
 */
export function dataClass(legend, vocab, chosen, hint) {
  const name = uid("data-class");
  let value = chosen ?? "";
  const choice = (key, title, description, examples = []) => h("label", { class: "choice" },
    h("input", { type: "radio", name, value: key, checked: key === value, onchange: () => {
      value = key;
    } }),
    h("div", { class: "grow" },
      h("div", { class: "cell-main" }, title),
      description ? h("div", { class: "cell-sub" }, description) : null,
      examples.length ? h("details", { class: "examples" },
        h("summary", {}, "Examples"),
        h("dl", {}, examples.map(([group, list]) => [h("dt", {}, group), h("dd", {}, list.join(" · "))]))) : null));
  const cards = (vocab.data_classes ?? []).filter((item) => !item.retired || item.key === value)
    .map((item) => choice(item.key, item.label, item.description, Object.entries(item.examples ?? {})));
  return {
    node: h("fieldset", {}, h("legend", {}, legend), hint ? h("p", { class: "hint subtle" }, hint) : null,
      h("div", { class: "stack-sm" }, choice("", "Not said", "It handles no data, or nobody has said yet."), cards)),
    value: () => value || null,
  };
}

export function section(title, ...children) {
  return h("div", { class: "form-section stack" }, h("h3", {}, title), children);
}

/** The units a person may add records to: those they steward or manage, or all of them. */
export function ownUnits() {
  const me = session();
  const scopes = [me.units?.steward, me.units?.manager].filter((scope) => scope !== undefined);
  if (can("edit_all") || scopes.some((scope) => scope === null)) return null;
  return new Set(scopes.flat());
}

// What each kind of record has beyond the name, unit, criticality, and data class they share.
const EXTRA = {
  process: (record) => {
    const purpose = field("Purpose", { type: "textarea", value: record?.purpose ?? "",
      hint: "What it is for, and what would be lost if it stopped." });
    return { nodes: [purpose.node], fields: { purpose }, values: () => ({ purpose: purpose.input.value }) };
  },
  system: (record, vocab) => {
    const hosting = select("Hosting", options(vocab, "hosting", { blank: "Not said" }), { value: record?.hosting ?? "" });
    const lifecycle = select("Lifecycle", options(vocab, "lifecycles"), { value: record?.lifecycle ?? "in_service" });
    const url = field("Address", { type: "url", value: record?.url ?? "", placeholder: "https://" });
    return { nodes: [h("div", { class: "grid-2" }, hosting.node, lifecycle.node), url.node], fields: { hosting, lifecycle, url },
      values: () => ({ hosting: hosting.input.value || null, lifecycle: lifecycle.input.value, url: url.input.value }) };
  },
  third_party: (record) => {
    const website = field("Website", { type: "url", value: record?.website ?? "", placeholder: "https://" });
    const notes = field("Notes", { type: "textarea", value: record?.notes ?? "" });
    return { nodes: [website.node, notes.node], fields: { website, notes },
      values: () => ({ website: website.input.value, notes: notes.input.value }) };
  },
};

EXTRA.information = (record) => {
  const held = field("Where it is held", { type: "textarea", rows: 2, value: record?.held_in ?? "", hint: "The systems and places. Link the systems themselves once it is saved." });
  const shared = field("Who it is shared with", { type: "textarea", rows: 2, value: record?.shared_with ?? "" });
  const agreement = field("Agreement", { value: record?.agreement ?? "", maxlength: 300, hint: "What it is held or shared under: a consent, a data use agreement, an award's terms." });
  return { nodes: [held.node, shared.node, agreement.node], fields: { held_in: held, shared_with: shared, agreement },
    values: () => ({ held_in: held.input.value, shared_with: shared.input.value, agreement: agreement.input.value }) };
};

const NAME_HINTS = {
  information: "What people call it. For example: Cohort survey responses. Never the information itself.",
  process: "What is done, in a few words. For example: Specimen storage and retrieval.",
  system: "What people call it. For example: Freezer monitoring.",
  third_party: "The organization's legal or trading name.",
};

/** Add a record of this type, or edit the one given. */
export function editRecord(type, { record = null, vocab, units, onDone }) {
  const meta = TYPES[type];
  openOverlay({
    title: record ? `Edit ${meta.noun}` : `Add ${meta.article}`,
    subtitle: record ? record.ref : meta.lede,
    render: (body, footer, close) => {
      const name = field("Name", { value: record?.name ?? "", required: true, hint: NAME_HINTS[type] });
      const kind = select("Kind", options(vocab, meta.kinds, { blank: record ? null : "Choose…" }), { value: record?.kind ?? "", required: true });
      const unit = select("Unit", unitOptions(units.tree, { only: ownUnits(), blank: record ? null : "Choose…" }),
        { value: record?.org_unit_id ?? "", required: true, hint: "The unit that answers for it." });
      const summary = field("Summary", { type: "textarea", value: record?.summary ?? "" });
      const critical = select("Criticality", options(vocab, "criticalities"), { value: record?.criticality ?? "moderate",
        hint: "How much the organization depends on it." });
      const data = dataClass("Highest class of data it handles", vocab, record?.data_class, null);
      const restricted = checkbox("Restricted", { checked: record?.restricted ?? false,
        hint: "Known only to its owners, its unit's stewards and leaders, managers, and auditors." });
      const status = record ? select("Status", [["active", statusLabel("active")], ["retired", statusLabel("retired")]], { value: record.status }) : null;
      const extra = EXTRA[type](record, vocab);

      const problem = banner();
      const saveButton = button(record ? "Save" : "Add", { kind: "btn-primary" });
      const fields = { name, kind, org_unit_id: unit, summary, criticality: critical, ...extra.fields, ...(status ? { status } : {}) };
      const values = () => ({
        name: name.input.value, kind: kind.input.value, org_unit_id: unit.input.value ? Number(unit.input.value) : null,
        summary: summary.input.value, criticality: critical.input.value, data_class: data.value(),
        restricted: restricted.input.checked, ...extra.values(), ...(status ? { status: status.input.value } : {}),
      });
      const path = `/api/v1/${meta.path}`;
      const save = async () => {
        const done = await submit({ button: saveButton, fields, banner: problem,
          run: () => (record ? patch(`${path}/${record.ref}`, { version: record.version, ...values() }) : post(path, values())) });
        if (!done) return;
        close();
        if (record) {
          toast("Saved.");
          onDone?.(done.data);
        } else {
          toast(`${done.data.ref} was added.`);
          navigate(`/${meta.path}/${done.data.ref}`);
        }
      };
      const form = h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem,
      section("What it is", name.node, h("div", { class: "grid-2" }, kind.node, unit.node), summary.node, extra.nodes),
      section("What is at stake", critical.node, data.node),
      section("Who may see it", restricted.node, status?.node ?? null));
      saveButton.addEventListener("click", save);
      body.append(form);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
