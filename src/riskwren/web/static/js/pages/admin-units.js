// Admin → Units: the organization's hierarchy.

import { UNIT } from "../components/record.js";
import { get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural, titleCase } from "../core/format.js";
import { banner, field, select, submit } from "../components/form.js";
import { openImport } from "../components/importer.js";
import { openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { card, emptyState, pageHeader, statusPill } from "../components/ui.js";
import { show } from "./page.js";

const KINDS = ["organization", "division", "department", "center", "core", "lab", "office"];

function editUnit({ unit = null, parent = null, units, reload }) {
  const isNew = !unit;
  const isRoot = isNew ? !units.length : unit.parent_id == null;
  openOverlay({
    title: isNew ? (isRoot ? "Add your organization" : "Add a unit") : unit.name,
    subtitle: isNew && parent ? `Within ${parent.name}` : null,
    render: (body, footer, close) => {
      const name = field("Name", { value: unit?.name ?? "", required: true });
      const kind = select("Kind", KINDS.map((k) => [k, titleCase(k)]),
        { value: unit?.kind ?? (isRoot ? "organization" : "lab") });
      const code = field("Code", { value: unit?.code ?? "",
        hint: "A short, permanent code, such as HALE. Imports and single sign-on match units by it." });
      const others = units.filter((u) => u.id !== unit?.id);
      const parentField = isRoot ? null : select("Within", others.map((u) => [u.id, u.name]),
        { value: unit?.parent_id ?? parent?.id ?? others[0]?.id });
      const status = isNew ? null : select("Status", [["active", "Active"], ["closed", "Closed"]],
        { value: unit.status, hint: "A closed unit keeps its records and history, and can no longer be chosen." });
      const problem = banner();
      const save = button(isNew ? "Add" : "Save", { kind: "btn-primary", type: "submit" });
      const form = h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
        event.preventDefault();
        const values = { name: name.input.value, kind: kind.input.value, code: code.input.value || null };
        if (parentField) values.parent_id = Number(parentField.input.value);
        if (status) values.status = status.input.value;
        const done = await submit({ button: save, fields: { name, kind, code }, banner: problem,
          run: () => (isNew ? post("/api/v1/units", values) : patch(`/api/v1/units/${unit.id}`, values)) });
        if (done) {
          close();
          toast(isNew ? `${values.name} was added.` : "The unit was saved.");
          reload();
        }
      } }, problem, name.node, kind.node, parentField?.node, code.node, status?.node);
      body.append(form);
      save.addEventListener("click", () => form.requestSubmit());
      save.type = "button";
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function node(unit, context) {
  return h("li", {},
    h("div", { class: "tree-node" },
      icon(unit.children.length ? "units" : "dot", "icon icon-sm"),
      h("div", { class: "grow" },
        h("span", { class: "cell-main" }, unit.name), " ",
        h("span", { class: "subtle" }, [titleCase(unit.kind), unit.code].filter(Boolean).join(" · "))),
      unit.status === "closed" ? statusPill("closed") : null,
      button("Add within", { kind: "btn-ghost btn-sm", iconName: "plus", onclick: () => editUnit({ parent: unit, ...context }) }),
      button("Edit", { kind: "btn-ghost btn-sm", iconName: "edit", onclick: () => editUnit({ unit, ...context }) })),
    unit.children.length ? h("ul", {}, unit.children.map((child) => node(child, context))) : null);
}

export function adminUnits(main) {
  return show(main, {
    title: UNIT.plural,
    load: async () => (await get("/api/v1/units", null, { fresh: true })).data,
    view: (data, reload) => {
      const context = { units: data.units, reload };
      const importer = () => openImport({
        kind: "units", title: "Import units",
        intro: "Units are matched by code, so importing again updates them.",
        sample: "code,name,kind,parent_code\nNMI,Northmere Institute,organization,\nIMM,Immunology,division,NMI\nHALE,Hale Lab,lab,IMM",
        onDone: reload,
      });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: UNIT.plural,
          lede: "Every record belongs to a unit. A steward of a unit also looks after every unit within it.",
          actions: [button("Import", { iconName: "upload", onclick: importer }),
            button("Add a unit", { kind: "btn-primary", iconName: "plus", onclick: () => editUnit(context) })] }),
        data.units.length
          ? card({ title: plural(data.units.length, "unit"), flush: true }, h("ul", { class: "tree card-body" }, data.tree.map((root) => node(root, context))))
          : card({}, emptyState({ iconName: "units", title: "Describe your organization",
            text: "Start with the organization itself, then add its divisions, departments, and labs. Or import them all from a spreadsheet.",
            action: h("div", { class: "row" },
              button("Add your organization", { kind: "btn-primary", onclick: () => editUnit(context) }),
              button("Import", { iconName: "upload", onclick: importer })) })));
    },
  });
}
