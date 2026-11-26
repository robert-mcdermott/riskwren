// Crosswalks: mapping a control to the requirements it helps to satisfy, from either end.

import { get, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { banner, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { pill } from "./ui.js";

const COVERAGE = [["partial", "In part: other controls are needed too"], ["full", "In full: this control answers it"]];

export function coveragePill(coverage) {
  return coverage === "full" ? pill("In full", "ok") : pill("In part");
}

/** A search box over one list, and what was chosen from it. onPick(item) is told. */
function picker({ label, placeholder, find, draw, onPick }) {
  const found = h("div", { class: "pick-results", role: "listbox", "aria-label": `${label} found` });
  const chosen = h("div", { class: "picked", hidden: true });
  const search = field(label, { type: "search", placeholder });
  let latest = 0;
  let timer = null;
  const look = async () => {
    const mine = ++latest;
    const words = search.input.value.trim();
    if (words.length < 2) {
      found.replaceChildren();
      return;
    }
    let items = [];
    try {
      items = await find(words);
    } catch {
      items = [];
    }
    if (mine !== latest) return;
    found.replaceChildren(...(items.length ? items.map((item) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
      chosen.replaceChildren(icon("check", "icon icon-sm"), h("span", { class: "grow" }, draw(item)));
      chosen.hidden = false;
      search.input.value = "";
      found.replaceChildren();
      onPick(item);
    } }, h("span", { class: "grow" }, draw(item)))) : [h("div", { class: "subtle pick-none" }, "Nothing matches.")]));
  };
  search.input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(look, 180);
  });
  const reset = () => {
    chosen.hidden = true;
    found.replaceChildren();
    search.input.value = "";
  };
  return { node: h("div", { class: "stack-sm" }, search.node, found, chosen), search, reset };
}

const requirementLine = (item) => [h("span", { class: "requirement-code" }, item.code), " ", item.title || item.excerpt || ""];

/**
 * Map one control to one requirement. Start from the control (choose the requirement) or
 * from the requirement (choose the control); whichever is given is fixed.
 */
export function mapCrosswalk({ control = null, framework = null, requirement = null, existing = null, onDone }) {
  openOverlay({
    title: existing ? "Change how it is mapped" : control ? "Map to a requirement" : "Map a control",
    subtitle: control ? `${control.ref} · ${control.name}` : `${requirement.code} · ${framework.title}`,
    render: async (body, footer, close) => {
      let chosenControl = control;
      let chosenFramework = framework?.key ?? existing?.framework ?? null;
      let chosenCode = requirement?.code ?? existing?.code ?? null;
      const parts = [];
      const problem = banner();
      if (!control) {
        const pick = picker({ label: "Control", placeholder: "Search controls by name or reference",
          find: async (words) => (await get("/api/v1/controls", { q: words, status: "active", limit: 8 })).data,
          draw: (item) => [h("span", { class: "cell-main" }, item.name), h("span", { class: "subtle" }, ` ${item.ref}`)],
          onPick: (item) => {
            chosenControl = item;
          } });
        parts.push(pick.node);
      } else if (!existing) {
        const frameworks = (await get("/api/v1/frameworks")).data;
        if (!frameworks.length) {
          body.append(h("p", { class: "muted" }, "No frameworks are loaded yet."));
          return;
        }
        chosenFramework = frameworks[0].key;
        const pick = picker({ label: "Requirement", placeholder: "Search by code or words: AC-2, backup, training",
          find: async (words) => (await get(`/api/v1/frameworks/${encodeURIComponent(chosenFramework)}/requirements`, { q: words, limit: 8 })).data.filter((item) => item.is_citable),
          draw: requirementLine,
          onPick: (item) => {
            chosenCode = item.code;
          } });
        const source = select("Framework", frameworks.map((item) => [item.key, item.title]), { value: chosenFramework });
        source.input.addEventListener("change", () => {
          chosenFramework = source.input.value;
          chosenCode = null;
          pick.reset();
        });
        parts.push(source.node, pick.node);
      }
      const coverage = select("How far it answers the requirement", COVERAGE, { value: existing?.coverage ?? "partial" });
      const note = field("Note", { value: existing?.note ?? "", maxlength: 300, hint: "Optional. Which part it answers, or what else is needed." });
      const saveButton = button(existing ? "Save" : "Map", { kind: "btn-primary" });
      const save = async () => {
        if (!chosenControl || !chosenCode) {
          problem.textContent = control ? "Choose a requirement first." : "Choose a control first.";
          problem.hidden = false;
          return;
        }
        const done = await submit({ button: saveButton, fields: { coverage, note }, banner: problem,
          run: () => put(`/api/v1/controls/${chosenControl.ref}/requirements`, { framework: chosenFramework, code: chosenCode, coverage: coverage.input.value, note: note.input.value || null }) });
        if (!done) return;
        close();
        toast(existing ? "Saved." : `${chosenControl.ref} is mapped to ${chosenCode}.`);
        onDone?.();
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem, ...parts, coverage.node, note.node));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
