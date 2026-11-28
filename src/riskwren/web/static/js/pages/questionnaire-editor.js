// The editor for a questionnaire's document: sections, questions, their kinds and options, and
// when each is asked. Saving a changed document publishes a new version; earlier versions and
// the answers given to them are untouched. Loaded only when someone opens the Edit tab.

import { button, h, iconButton, uid } from "../core/dom.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { questionnaireForm } from "../components/questionnaire.js";
import { card } from "../components/ui.js";

const TYPES = [["yes_no", "Yes or no"], ["choice", "One of a list"], ["choices", "Any of a list"], ["text", "A line of text"],
  ["long_text", "A paragraph"], ["number", "A number"], ["date", "A date"]];
const PURPOSES = [["attestation", "Attestation"], ["self_assessment", "Self-assessment"], ["completeness", "Completeness check"],
  ["due_diligence", "Due diligence"], ["review", "Review"], ["privacy_impact", "Privacy impact"], ["tiering", "Tiering"], ["other", "Other"]];
const slug = (text, fallback) => (text.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^[^a-z]+/, "").slice(0, 32) || fallback);

/** A rule this editor can show as three choices: one earlier question, compared one way. */
function simple(rule) {
  return rule && typeof rule.field === "string" && ["eq", "ne", "in", "not_in", "contains", "contains_any", "answered", "empty"].includes(rule.op);
}

export function editor(item, save) {
  const draft = structuredClone(item.document);
  const taken = () => new Set(draft.sections.flatMap((section) => [section.key, ...section.questions.map((question) => question.key)]));
  const fresh = (text, fallback) => {
    const used = taken();
    const base = slug(text, fallback);
    let key = base;
    for (let n = 2; used.has(key); n += 1) key = `${base}_${n}`;
    return key;
  };
  const title = field("Title", { value: item.title, required: true });
  const purpose = select("What it is for", PURPOSES, { value: item.purpose });
  const summary = field("What it asks, in a sentence", { type: "textarea", rows: 2, value: item.summary ?? "" });
  const note = field("What changed", { hint: "Kept with the new version, for whoever reads the history." });
  const problem = banner();
  const body = h("div", { class: "stack-lg" });
  const preview = h("div", {});

  const before = (section, question) => {
    const found = [];
    for (const each of draft.sections) {
      for (const other of each.questions) {
        if (other === question) return found;
        found.push(other);
      }
      if (each === section && !question) return found;
    }
    return found;
  };

  function ruleEditor(holder, section, question) {
    const earlier = before(section, question).filter((other) => other.type !== "text" && other.type !== "long_text" && other.type !== "date");
    const rule = holder.show_when;
    if (rule && !simple(rule)) {
      return h("p", { class: "subtle" }, "Asked by a rule with several parts, which is kept as it is. ",
        button("Ask it always instead", { kind: "btn-sm btn-ghost", onclick: () => { delete holder.show_when; draw(); } }));
    }
    const which = h("select", { class: "select", "aria-label": "Asked when" },
      h("option", { value: "" }, "Always asked"),
      earlier.map((other) => h("option", { value: other.key, selected: rule?.field === `answers.${other.key}` }, `When “${other.label.slice(0, 50)}”`)));
    const row = h("div", { class: "editor-rule" }, which);
    const chosen = earlier.find((other) => rule?.field === `answers.${other.key}`);
    if (chosen) {
      const many = chosen.type === "choices";
      const ops = chosen.type === "number" ? [["answered", "is answered"], ["empty", "is not answered"]]
        : many ? [["contains_any", "includes any of"], ["answered", "is answered"], ["empty", "is not answered"]]
          : [["in", "is"], ["not_in", "is not"], ["answered", "is answered"], ["empty", "is not answered"]];
      const current = rule.op === "eq" ? "in" : rule.op === "ne" ? "not_in" : rule.op === "contains" ? "contains_any" : rule.op;
      const op = h("select", { class: "select", "aria-label": "How it compares" }, ops.map(([key, text]) => h("option", { value: key, selected: key === current }, text)));
      const values = chosen.type === "yes_no" ? [[true, "Yes"], [false, "No"]] : (chosen.options ?? []).map((option) => [option.key, option.label]);
      const held = Array.isArray(rule.value) ? rule.value : rule.value === undefined ? [] : [rule.value];
      const boxes = values.map(([key, text]) => {
        const id = uid("value");
        const input = h("input", { type: "checkbox", id, checked: held.includes(key) });
        input.answer = key;
        input.addEventListener("change", () => { holder.show_when = { field: rule.field, op: op.value, value: boxes.filter((box) => box.input.checked).map((box) => box.input.answer) }; refresh(); });
        return { input, node: h("div", { class: "check" }, input, h("label", { for: id }, text)) };
      });
      op.addEventListener("change", () => {
        holder.show_when = ["answered", "empty"].includes(op.value) ? { field: rule.field, op: op.value }
          : { field: rule.field, op: op.value, value: boxes.filter((box) => box.input.checked).map((box) => box.input.answer) };
        draw();
      });
      row.append(op, ["answered", "empty"].includes(current) ? h("span", {}) : h("div", { class: "stack-sm" }, boxes.map((box) => box.node)));
    }
    which.addEventListener("change", () => {
      const other = earlier.find((each) => each.key === which.value);
      if (!other) delete holder.show_when;
      else holder.show_when = other.type === "number" ? { field: `answers.${other.key}`, op: "answered" }
        : { field: `answers.${other.key}`, op: other.type === "choices" ? "contains_any" : "in", value: other.type === "yes_no" ? [true] : [] };
      draw();
    });
    return row;
  }

  function questionEditor(section, question, index) {
    const label = field("The question", { value: question.label, required: true });
    label.input.addEventListener("input", () => { question.label = label.input.value; refresh(); });
    const kind = select("Answered with", TYPES, { value: question.type });
    kind.input.addEventListener("change", () => {
      question.type = kind.input.value;
      if (["choice", "choices"].includes(question.type)) question.options ??= [{ key: "first", label: "First option" }, { key: "second", label: "Second option" }];
      else delete question.options;
      draw();
    });
    const required = checkbox("Must be answered", { checked: Boolean(question.required) });
    required.input.addEventListener("change", () => { question.required = required.input.checked; refresh(); });
    const help = field("A hint beneath it", { value: question.help ?? "" });
    help.input.addEventListener("input", () => { if (help.input.value.trim()) question.help = help.input.value; else delete question.help; refresh(); });
    let options = null;
    if (question.options) {
      options = field("Options, one on each line", { type: "textarea", rows: Math.max(3, question.options.length), value: question.options.map((option) => option.label).join("\n") });
      options.input.addEventListener("change", () => {
        const lines = options.input.value.split("\n").map((line) => line.trim()).filter(Boolean);
        const used = new Set();
        // An option keeps its key when its words are edited in place, so earlier rules still hold.
        question.options = lines.map((text, at) => {
          const kept = question.options[at]?.label === text ? question.options[at].key : question.options.find((option) => option.label === text)?.key;
          let key = kept && !used.has(kept) ? kept : question.options[at] && !used.has(question.options[at].key) && lines.length === question.options.length ? question.options[at].key : slug(text, `option_${at + 1}`);
          for (let n = 2; used.has(key); n += 1) key = `${slug(text, "option")}_${n}`;
          used.add(key);
          return { key, label: text };
        });
        refresh();
      });
    }
    const move = (by) => () => {
      const to = index + by;
      if (to < 0 || to >= section.questions.length) return;
      section.questions.splice(to, 0, section.questions.splice(index, 1)[0]);
      draw();
    };
    return h("div", { class: "editor-question stack" },
      h("div", { class: "editor-question-head" }, h("strong", {}, `Question ${index + 1}`),
        h("div", { class: "row-sm" }, iconButton("chevron-up", `Move question ${index + 1} up`, { onclick: move(-1), disabled: index === 0 }),
          iconButton("chevron-down", `Move question ${index + 1} down`, { onclick: move(1), disabled: index === section.questions.length - 1 }),
          iconButton("trash", `Remove question ${index + 1}`, { onclick: () => { section.questions.splice(index, 1); draw(); }, disabled: section.questions.length === 1 }))),
      h("div", { class: "editor-grid" }, label.node, kind.node),
      options?.node, help.node, required.node,
      h("div", { class: "field" }, h("span", { class: "label" }, "When it is asked"), ruleEditor(question, section, question)));
  }

  function refresh() {
    preview.replaceChildren(questionnaireForm(draft).node);
  }

  function draw() {
    body.replaceChildren(...draft.sections.map((section, at) => {
      const name = field("Section title", { value: section.title, required: true });
      name.input.addEventListener("input", () => { section.title = name.input.value; refresh(); });
      return card({ title: `Section ${at + 1}`, actions: draft.sections.length > 1
        ? button("Remove section", { kind: "btn-sm btn-ghost", onclick: () => { draft.sections.splice(at, 1); draw(); } }) : null,
      footer: button("Add a question", { iconName: "plus", onclick: () => {
        section.questions.push({ key: fresh("question", "question"), label: "A new question", type: "yes_no", required: true });
        draw();
      } }) },
      h("div", { class: "stack" }, name.node,
        at > 0 ? h("div", { class: "field" }, h("span", { class: "label" }, "When the section is asked"), ruleEditor(section, section, null)) : null,
        section.questions.map((question, index) => questionEditor(section, question, index))));
    }));
    refresh();
  }

  const publish = button("Save", { kind: "btn-primary" });
  publish.addEventListener("click", async () => {
    // A question written here gets a key from its words the first time it is saved.
    for (const section of draft.sections) {
      for (const question of section.questions) {
        if (/^question(_\d+)?$/.test(question.key) && question.label.trim() && !item.document.sections.some((s) => s.questions.some((q) => q.key === question.key))) {
          const renamed = fresh(question.label, question.key);
          for (const other of draft.sections) {
            for (const holder of [other, ...other.questions]) {
              if (holder.show_when?.field === `answers.${question.key}`) holder.show_when.field = `answers.${renamed}`;
            }
          }
          question.key = renamed;
        }
      }
    }
    await submit({ button: publish, fields: { title, purpose }, banner: problem,
      run: () => save({ title: title.input.value, purpose: purpose.input.value, summary: summary.input.value, document: draft, note: note.input.value || null }) });
  });

  draw();
  return h("div", { class: "stack-lg" },
    card({ title: "About it" }, h("div", { class: "stack" }, title.node, purpose.node, summary.node)),
    body,
    h("div", {}, button("Add a section", { iconName: "plus", onclick: () => {
      draft.sections.push({ key: fresh("section", "section"), title: "A new section", questions: [{ key: fresh("question", "question"), label: "A new question", type: "yes_no", required: true }] });
      draw();
    } })),
    card({ title: "As it will be asked" }, preview),
    card({ title: "Save", footer: h("div", { class: "row" }, publish, h("span", { class: "subtle" }, "If the questions have changed, this publishes a new version. Answers already given keep the version they were given to.")) },
      h("div", { class: "stack" }, problem, note.node)));
}
