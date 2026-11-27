// A questionnaire as a form that reacts as it is filled in, and answers set out as they were
// asked. The server decides what counts; this shows and hides with the same rules.

import { h, uid } from "../core/dom.js";
import { showing } from "../core/questionnaire.js";

function control(question, value, changed) {
  const name = uid("q");
  if (question.type === "yes_no" || question.type === "choice") {
    const options = question.type === "yes_no" ? [[true, "Yes"], [false, "No"]] : question.options.map((option) => [option.key, option.label]);
    const inputs = options.map(([key, text]) => {
      const id = uid("opt");
      const input = h("input", { type: "radio", name, id, checked: value === key, onchange: changed });
      input.answer = key;
      return { input, node: h("div", { class: "check" }, input, h("label", { for: id }, text)) };
    });
    return { nodes: inputs.map((each) => each.node), group: true, read: () => inputs.find((each) => each.input.checked)?.input.answer ?? null };
  }
  if (question.type === "choices") {
    const inputs = question.options.map((option) => {
      const id = uid("opt");
      const input = h("input", { type: "checkbox", id, checked: (value ?? []).includes(option.key), onchange: changed });
      return { key: option.key, input, node: h("div", { class: "check" }, input, h("label", { for: id }, option.label)) };
    });
    return { nodes: inputs.map((each) => each.node), group: true, read: () => inputs.filter((each) => each.input.checked).map((each) => each.key) };
  }
  if (question.type === "long_text") {
    const input = h("textarea", { class: "textarea", rows: 3, oninput: changed }, value ?? "");
    return { nodes: [input], input, read: () => input.value.trim() || null };
  }
  const type = { number: "number", date: "date" }[question.type] ?? "text";
  const input = h("input", { class: "input", type, value: value ?? "", oninput: changed, ...(type === "number" ? { step: "any", inputmode: "decimal" } : {}) });
  return { nodes: [input], input, read: () => (input.value === "" ? null : type === "number" ? Number(input.value) : input.value.trim()) };
}

/**
 * A form for a document. Returns { node, answers(), setErrors(errors) }. Questions and whole
 * sections appear and go as earlier answers change; what is hidden is not sent.
 */
export function questionnaireForm(document, initial = {}, { onChange = null } = {}) {
  const parts = new Map();
  const sections = [];
  const sync = () => {
    const raw = Object.fromEntries([...parts].map(([key, part]) => [key, part.read()]));
    const { keys } = showing(document, raw);
    const shown = new Set(keys);
    for (const [key, part] of parts) part.node.hidden = !shown.has(key);
    for (const section of sections) section.node.hidden = !section.keys.some((key) => shown.has(key));
    onChange?.();
  };
  const node = h("div", { class: "stack-lg questionnaire" }, document.sections.map((section) => {
    const fields = section.questions.map((question) => {
      const id = uid("question");
      const made = control(question, initial[question.key], sync);
      const error = h("div", { class: "error", id: `${id}-error`, role: "alert", hidden: true });
      const label = [question.label, question.required ? h("span", { class: "subtle" }, " (required)") : null];
      const help = question.help ? h("div", { class: "hint", id: `${id}-hint` }, question.help) : null;
      let fieldNode;
      if (made.group) {
        fieldNode = h("fieldset", { class: "field", "aria-describedby": help ? `${id}-hint` : null },
          h("legend", { class: "label" }, label), help, h("div", { class: "stack-sm" }, made.nodes), error);
      } else {
        made.input.id = id;
        if (help) made.input.setAttribute("aria-describedby", `${id}-hint`);
        fieldNode = h("div", { class: "field" }, h("label", { for: id }, label), help, made.nodes, error);
      }
      parts.set(question.key, { node: fieldNode, read: made.read, error, input: made.input ?? fieldNode });
      return fieldNode;
    });
    const sectionNode = h("section", { class: "stack" }, h("h3", {}, section.title),
      section.help ? h("p", { class: "muted" }, section.help) : null, fields);
    sections.push({ node: sectionNode, keys: section.questions.map((question) => question.key) });
    return sectionNode;
  }));
  sync();
  return {
    node,
    answers: () => showing(document, Object.fromEntries([...parts].map(([key, part]) => [key, part.read()]))).kept,
    /** Required questions that are showing and not answered, as { key: what to say }. */
    missing: () => {
      const { keys, kept } = showing(document, Object.fromEntries([...parts].map(([key, part]) => [key, part.read()])));
      const required = new Set(document.sections.flatMap((section) => section.questions).filter((question) => question.required).map((question) => question.key));
      return Object.fromEntries(keys.filter((key) => required.has(key) && !(key in kept)).map((key) => [key, "Answer this question."]));
    },
    setErrors: (errors) => {
      let first = null;
      for (const [key, part] of parts) {
        const message = errors[key] ?? null;
        part.error.hidden = !message;
        part.error.textContent = message ?? "";
        if (message && !first) first = part;
      }
      first?.node.scrollIntoView({ block: "center" });
      (first?.input.querySelector?.("input") ?? first?.input)?.focus?.();
    },
  };
}

/** Answers as they were asked: each question that showed, with its own words. */
export function asAsked(sections) {
  return h("div", { class: "stack-lg" }, sections.map((section) => h("section", { class: "stack-sm" },
    h("h3", {}, section.title),
    h("dl", { class: "statement" }, section.questions.map((question) => [
      h("dt", {}, question.label),
      h("dd", {}, question.said == null || question.said === "" || (Array.isArray(question.said) && !question.said.length)
        ? h("span", { class: "subtle" }, "Not answered") : Array.isArray(question.said) ? question.said.join(", ") : String(question.said)),
    ])))));
}

const OPS = { eq: "is", ne: "is not", in: "is one of", not_in: "is none of", contains: "includes", contains_any: "includes any of",
  contains_all: "includes all of", gt: "is more than", gte: "is at least", lt: "is less than", lte: "is at most", answered: "is answered", empty: "is not answered" };

/** A rule in words, for whoever reads the questionnaire: "“Does it operate?” is one of Partly, No". */
export function ruleInWords(condition, document) {
  if (!condition || !Object.keys(condition).length) return "";
  const questions = new Map(document.sections.flatMap((section) => section.questions).map((question) => [question.key, question]));
  const say = (rule) => {
    if (rule.all) return rule.all.map(say).join(", and ");
    if (rule.any) return `either ${rule.any.map(say).join(", or ")}`;
    if (rule.not) return `not (${say(rule.not)})`;
    const question = questions.get(rule.field.replace(/^answers\./, ""));
    const labels = new Map((question?.options ?? []).map((option) => [option.key, option.label]));
    const word = (value) => (value === true ? "Yes" : value === false ? "No" : labels.get(value) ?? String(value));
    const value = rule.value === undefined ? "" : ` ${Array.isArray(rule.value) ? rule.value.map(word).join(", ") : word(rule.value)}`;
    return `“${question?.label ?? rule.field}” ${OPS[rule.op] ?? rule.op}${value}`;
  };
  return say(condition);
}
