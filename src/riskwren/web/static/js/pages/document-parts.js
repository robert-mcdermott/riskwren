// The parts of a document's page that only some visits need: what it governs, who has
// acknowledged it, and who it applies to. Fetched when a tab or a button wants them, so the
// page itself stays small.

import { del, get, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { unitOptions } from "../core/lookups.js";
import { navigate } from "../core/router.js";
import { can } from "../core/session.js";
import { segments } from "../components/charts.js";
import { statePill } from "../components/control.js";
import { picker, requirementLine } from "../components/crosswalk.js";
import { ROLE_NAMES } from "../components/document.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pill } from "../components/ui.js";

export function audienceForm(record, unitIndex, reload) {
  openOverlay({ title: "Who it applies to", subtitle: "Those it applies to find it in their library, and are asked to acknowledge it when it asks.",
    render: (body, footer, close) => {
      const everyone = checkbox("Everyone", { checked: record.audience.everyone, hint: "Everyone who can sign in." });
      const chosenUnits = new Set(record.audience.units.map((unit) => unit.id));
      const unitBoxes = [];
      const walk = (nodes, depth) => nodes.flatMap((node) => {
        const box = checkbox(node.name, { checked: chosenUnits.has(node.id), value: String(node.id) });
        box.node.dataset.depth = String(Math.min(depth, 4));
        unitBoxes.push(box);
        return [box.node, ...walk(node.children ?? [], depth + 1)];
      });
      const unitsNode = h("fieldset", { class: "stack-sm" }, h("legend", {}, "Those who work in these units, and the units beneath them"),
        h("div", { class: "stack-sm unit-checks" }, walk(unitIndex.tree, 0)));
      const roleBoxes = Object.entries(ROLE_NAMES).map(([key, text]) => checkbox(text, { checked: record.audience.roles.includes(key), value: key }));
      const rolesNode = h("fieldset", { class: "stack-sm" }, h("legend", {}, "And those who hold these roles, wherever they hold them"),
        h("div", { class: "stack-sm" }, roleBoxes.map((box) => box.node)));
      const sync = () => { unitsNode.hidden = everyone.input.checked; rolesNode.hidden = everyone.input.checked; };
      everyone.input.addEventListener("change", sync);
      sync();
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/documents/${record.ref}/audience`, {
          everyone: everyone.input.checked,
          units: unitBoxes.filter((box) => box.input.checked).map((box) => Number(box.input.value)),
          roles: roleBoxes.filter((box) => box.input.checked).map((box) => box.input.value) }) });
        if (!done) return;
        close();
        toast("Saved.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, everyone.node, unitsNode, rolesNode));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function askForAcknowledgment(record, unitIndex) {
  openOverlay({ title: "Ask for acknowledgment", subtitle: "A campaign asks those who have not yet said they read it, by a date, with reminders and a count by unit.",
    render: (body, footer, close) => {
      const name = field("Name", { value: `${record.name}, version ${record.acknowledgments.required.number}`, required: true });
      const due = field("Due", { type: "date", required: true });
      const unit = select("Only those in", unitOptions(unitIndex.tree, { blank: "Everyone it applies to" }));
      const problem = banner();
      const go = button("Start, and tell those asked", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, fields: { name, due_on: due, org_unit_id: unit }, banner: problem,
          run: () => post("/api/v1/campaigns", { kind: "acknowledgment", document: record.ref, name: name.input.value, due_on: due.input.value,
            org_unit_id: unit.input.value ? Number(unit.input.value) : null }) });
        if (!done) return;
        close();
        toast(`${done.data.ref} is started.`);
        navigate(`/campaigns/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack" }, problem, name.node, due.node, unit.node,
        h("p", { class: "muted" }, "Those who have already acknowledged the version they must are counted as done from the start.")));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function acknowledgmentsTab(record, data) {
  const found = data.standing;
  const required = found.required;
  const said = (row) => row.acknowledged ? `Version ${row.version}, ${date(row.at)}`
    : row.version ? pill(`Only version ${row.version}`, "warn") : pill("Not yet", "warn");
  return h("div", { class: "stack-lg" },
    card({ title: "Who has acknowledged it", actions: can("assess") && required ? button("Ask for acknowledgment", { kind: "btn-sm", onclick: () => askForAcknowledgment(record, data.units) }) : null },
      h("div", { class: "stack" },
        h("p", {}, required ? `Everyone it applies to is asked to have acknowledged version ${required.number} or later.` : "Nothing is published yet."),
        segments([{ label: "have", value: found.acknowledged, tone: "ok" }, { label: "have not yet", value: found.outstanding, tone: "gap" }],
          { label: `${found.acknowledged} of ${found.people} have acknowledged it` }))),
    found.by_unit.length ? card({ title: "By unit", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Unit"), h("th", { scope: "col", class: "numeric" }, "People"), h("th", { scope: "col", class: "numeric" }, "Have acknowledged"))),
      h("tbody", {}, found.by_unit.map((row) => h("tr", {}, h("td", {}, row.unit.name), h("td", { class: "numeric" }, String(row.people)),
        h("td", { class: "numeric" }, `${row.acknowledged} (${row.share}%)`))))))) : null,
    card({ title: plural(found.people, "person", "people"), flush: true }, found.rows.length
      ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Person"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Acknowledged"))),
        h("tbody", {}, found.rows.slice(0, 500).map((row) => h("tr", {}, h("td", {}, row.name), h("td", {}, row.unit), h("td", {}, said(row)))))))
      : emptyState({ iconName: "people", title: "It applies to no one", text: "Change who it applies to." })));
}

function addControl(record, reload) {
  openOverlay({ title: "Add a control it directs", subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      let chosen = null;
      const pick = picker({ label: "Control", placeholder: "Search controls by name or reference",
        find: async (words) => (await get("/api/v1/controls", { q: words, status: "active", limit: 8 })).data,
        draw: (item) => [h("span", { class: "cell-main" }, item.name), h("span", { class: "subtle" }, ` ${item.ref}`)],
        onPick: (item) => { chosen = item; } });
      const note = field("Note", { maxlength: 300, hint: "Optional. Which part of the document it carries out." });
      const problem = banner();
      const save = button("Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        if (!chosen) {
          problem.textContent = "Choose a control first.";
          problem.hidden = false;
          return;
        }
        const done = await submit({ button: save, fields: { control: pick.search, note }, banner: problem,
          run: () => put(`/api/v1/documents/${record.ref}/controls`, { control: chosen.ref, note: note.input.value || null }) });
        if (!done) return;
        close();
        toast(`It directs ${chosen.ref}.`);
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, pick.node, note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function addRequirement(record, reload) {
  openOverlay({ title: "Add a requirement it answers", subtitle: `${record.ref} · ${record.name}`,
    render: async (body, footer, close) => {
      const sources = (await get("/api/v1/frameworks")).data.filter((item) => item.status === "active");
      if (!sources.length) {
        body.append(h("p", { class: "muted" }, "No frameworks are loaded yet."));
        return;
      }
      let framework = sources[0].key;
      let code = null;
      const pick = picker({ label: "Requirement", placeholder: "Search by code or words: 5.1, AC-1, policy",
        find: async (words) => (await get(`/api/v1/frameworks/${encodeURIComponent(framework)}/requirements`, { q: words, limit: 8 })).data.filter((item) => item.is_citable),
        draw: requirementLine,
        onPick: (item) => { code = item.code; } });
      const source = select("Framework", sources.map((item) => [item.key, item.title]), { value: framework });
      source.input.addEventListener("change", () => {
        framework = source.input.value;
        code = null;
        pick.reset();
      });
      const note = field("Note", { maxlength: 300, hint: "Optional. Which section answers it." });
      const problem = banner();
      const save = button("Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        if (!code) {
          problem.textContent = "Choose a requirement first.";
          problem.hidden = false;
          return;
        }
        const done = await submit({ button: save, fields: { code: pick.search, note }, banner: problem,
          run: () => put(`/api/v1/documents/${record.ref}/requirements`, { framework, code, note: note.input.value || null }) });
        if (!done) return;
        close();
        toast(`It answers ${code}.`);
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, source.node, pick.node, note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function governsTab(record, found, reload) {
  const remove = (path, what) => () => confirmAction({ title: `Take ${what} off?`, text: "The document no longer says it governs it. The history keeps that it did.",
    confirmLabel: "Take it off", run: async () => { await del(path); toast("Taken off."); reload(); } });
  const controls = card({ title: found.controls.length ? `Controls it directs (${found.controls.length})` : "Controls it directs",
    flush: found.controls.length > 0,
    actions: found.can_edit ? button("Add a control", { kind: "btn-sm", iconName: "plus", onclick: () => addControl(record, reload) }) : null },
  found.controls.length ? h("ul", { class: "plain-list rows" }, found.controls.map((row) => h("li", { class: "row wrap" },
    h("div", { class: "grow" }, h("a", { class: "cell-main", href: `/controls/${row.control.ref}` }, row.control.name),
      h("div", { class: "cell-sub" }, [row.control.ref, row.control.status === "retired" ? "retired" : null, row.note].filter(Boolean).join(" · "))),
    statePill(row.control.state),
    found.can_edit ? button("Take off", { kind: "btn-ghost btn-sm", "aria-label": `Take ${row.control.ref} off`, onclick: remove(`/api/v1/documents/${record.ref}/controls/${row.id}`, row.control.ref) }) : null)))
    : h("p", { class: "muted" }, "None yet. A control it directs is how what the document requires is done: name the controls that carry it out."),
  found.hidden ? h("p", { class: "subtle card-pad" }, `And ${found.hidden} more that you do not have access to.`) : null);
  const requirements = card({ title: found.requirements ? `Requirements it answers (${found.requirements})` : "Requirements it answers",
    actions: found.can_edit ? button("Add a requirement", { kind: "btn-sm", iconName: "plus", onclick: () => addRequirement(record, reload) }) : null },
  found.frameworks.length ? h("div", { class: "stack" }, found.frameworks.map((group) => h("div", { class: "stack-sm" },
    h("h3", { class: "label" }, group.title),
    h("ul", { class: "plain-list stack-sm" }, group.requirements.map((row) => h("li", { class: "row" },
      h("div", { class: "grow" }, h("a", { href: `/frameworks/${group.key}?r=${encodeURIComponent(row.code)}` }, h("span", { class: "requirement-code" }, row.code), " ", row.title || row.excerpt || ""),
        row.note ? h("div", { class: "cell-sub" }, row.note) : null),
      found.can_edit ? button("Take off", { kind: "btn-ghost btn-sm", "aria-label": `Take ${row.code} off`, onclick: remove(`/api/v1/documents/${record.ref}/requirements/${row.id}`, row.code) }) : null))))))
    : h("p", { class: "muted" }, "None yet. Name the requirements this document is where the organization says it meets them. They show it once it is in force."));
  return h("div", { class: "stack-lg" },
    record.published ? null : alert("info", icon("info"), h("div", {}, "Requirements show this document once a version of it is published.")),
    controls, requirements);
}
