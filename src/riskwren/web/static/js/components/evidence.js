// Evidence: adding an item, and the card that shows what is attached to a control or scope.

import { get, patch, post, put, upload } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date } from "../core/format.js";
import { options, unitOptions } from "../core/lookups.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { section } from "./form.js";
import { evidenceUnits, freshness, STATES } from "./evidence-state.js";
import { toast } from "./toast.js";
import { card, pill } from "./ui.js";

export const KINDS = [["file", "A file"], ["link", "A link"], ["note", "A note of what was seen"], ["attestation", "An attestation"]];
const KIND_LABELS = { file: "File", link: "Link", note: "Note", attestation: "Attestation" };
const today = () => new Date().toISOString().slice(0, 10);

export { evidenceUnits, freshness };

export const kindLabel = (kind) => KIND_LABELS[kind] ?? kind;
export const stateOptions = (blank) => [["", blank], ...Object.entries(STATES).map(([key, [text]]) => [key, text])];

export function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} bytes`;
  return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Add an evidence item, or change one. With a subject, the new item is attached to it. */
export function editEvidence({ item = null, subject = null, vocab, units, onDone }) {
  openOverlay({
    title: item ? "Edit the evidence" : "Add evidence",
    subtitle: item ? `${item.ref} · ${item.name}` : subject ? `For ${subject.ref} · ${subject.name}` : "Something that shows a control is done.",
    render: (body, footer, close) => {
      const name = field("What it is", { value: item?.name ?? "", required: true, maxlength: 200, hint: item ? null : "For example: Restore test report, first quarter." });
      const kind = item ? null : select("Kind", KINDS, { value: "file" });
      const file = field("File", { type: "file", hint: "PDF, images, Word, Excel, or PowerPoint documents, or plain text such as CSV. Up to 25 MB. It describes the control: never put patient or participant data here." });
      const url = field("Address", { type: "url", value: item?.url ?? "", placeholder: "https://", hint: "Where it is kept, if it lives in another system." });
      const note = field("What was seen", { type: "textarea", rows: 4, value: item?.note ?? "", hint: "What was looked at, by whom, and what it showed." });
      const collected = field("Collected on", { type: "date", value: item?.collected_on ?? today(), max: today() });
      const from = field("Covers from", { type: "date", value: item?.covers_from ?? "" });
      const to = field("to", { type: "date", value: item?.covers_to ?? "" });
      const until = field("Holds until", { type: "date", value: item?.valid_until ?? "", hint: item ? "After this date it stays on the record and stops counting." : "Leave empty for a year after it was collected. After this date it stops counting." });
      const dataClass = select("Data class", options(vocab, "data_classes", { blank: "Not said" }), { value: item?.data_class ?? "",
        hint: "Evidence of the most sensitive class is seen only by those with a role in it." });
      const unit = select("Unit", unitOptions(units.tree, { only: evidenceUnits(), blank: item || subject ? null : "Choose…" }), { value: item?.org_unit_id ?? subject?.org_unit_id ?? "", required: true });
      const restricted = checkbox("Restricted", { checked: item?.restricted ?? false, hint: "Seen only by its owners, its unit's steward and leaders, managers, and auditors." });
      const which = () => item?.kind ?? kind.input.value;
      const arrange = () => {
        file.node.hidden = which() !== "file";
        url.node.hidden = which() !== "link";
        note.node.querySelector("label").textContent = which() === "attestation" ? "What is attested to" : which() === "note" ? "What was seen" : "Note";
      };
      kind?.input.addEventListener("change", arrange);
      arrange();
      const problem = banner();
      const saveButton = button(item ? "Save" : "Add", { kind: "btn-primary" });
      const fields = { name, ...(kind ? { kind } : {}), file, url, note, collected_on: collected, covers_from: from, covers_to: to, valid_until: until, data_class: dataClass, org_unit_id: unit };
      const save = async () => {
        const chosen = file.input.files?.[0];
        if (!item && which() === "file" && !chosen) {
          file.setError("Choose the file.");
          return;
        }
        const values = { name: name.input.value, url: which() === "link" ? url.input.value : null, note: note.input.value || null,
          collected_on: collected.input.value || null, covers_from: from.input.value || null, covers_to: to.input.value || null,
          valid_until: until.input.value || null, data_class: dataClass.input.value || null,
          org_unit_id: unit.input.value ? Number(unit.input.value) : null, restricted: restricted.input.checked };
        const done = await submit({ button: saveButton, fields, banner: problem, run: async () => {
          const saved = item ? await patch(`/api/v1/evidence/${item.ref}`, { version: item.version, ...values })
            : await post("/api/v1/evidence", { ...values, kind: which() });
          const ref = saved.data.ref;
          if (chosen && which() === "file") await upload(`/api/v1/evidence/${ref}/file`, chosen, { name: chosen.name });
          if (!item && subject) await put(`/api/v1/evidence/${ref}/subjects`, { subjects: [subject.ref] });
          return saved;
        } });
        if (!done) return;
        close();
        toast(item ? "Saved." : `${done.data.ref} was added.`);
        onDone?.(done.data);
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem,
      section("What it is", name.node, kind?.node ?? null, file.node, url.node, note.node),
      section("When", h("div", { class: "grid-2" }, collected.node, until.node), h("div", { class: "grid-2" }, from.node, to.node)),
      section("Who may see it", h("div", { class: "grid-2" }, unit.node, dataClass.node), restricted.node)));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** The evidence attached to a control or a scope. Loads itself, and can add to itself. */
export function evidenceCard(subject, ctx) {
  const holder = h("div", {}, h("p", { class: "muted" }, "Loading…"));
  const actions = h("span", {});
  const draw = async () => {
    let found;
    try {
      found = (await get(`/api/v1/evidence-for/${subject.ref}`, undefined, { fresh: true })).data;
    } catch {
      holder.replaceChildren(h("p", { class: "muted" }, "The evidence could not be shown."));
      return;
    }
    actions.replaceChildren(found.can_add ? button("Add evidence", { kind: "btn-sm", iconName: "plus",
      onclick: () => editEvidence({ subject, vocab: ctx.vocab, units: ctx.units, onDone: draw }) }) : "");
    holder.replaceChildren(
      found.items.length ? h("div", {}, found.items.map((item) => h("div", { class: "list-row" },
        h("span", { class: "owed-icon" }, icon(item.kind === "file" ? "file" : item.kind === "link" ? "link" : "evidence")),
        h("div", { class: "grow" }, h("a", { class: "cell-main", href: `/evidence/${item.ref}` }, item.name),
          h("div", { class: "cell-sub" }, `${item.ref} · ${kindLabel(item.kind)} · collected ${date(item.collected_on)} · holds until ${date(item.valid_until)}`)),
        freshness(item.state))))
        : h("p", { class: "muted card-pad" }, found.hidden ? "None that you have access to." : "No evidence is attached yet."),
      found.hidden && found.items.length ? h("p", { class: "subtle card-pad" }, `And ${found.hidden} more that you do not have access to.`) : null);
  };
  draw();
  return card({ title: "Evidence", actions, flush: true }, holder);
}
