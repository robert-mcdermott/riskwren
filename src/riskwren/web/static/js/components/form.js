// Form fields that carry their own label, hint, and error, and a form that reports the
// server's field errors next to the fields they belong to.

import { h, uid } from "../core/dom.js";

/** A labelled input. Returns { node, input, setError }. */
export function field(label, { hint = null, type = "text", value = "", control = null, ...attrs } = {}) {
  const id = uid("field");
  const hintId = hint ? `${id}-hint` : null;
  const errorNode = h("div", { class: "error", id: `${id}-error`, role: "alert", hidden: true });
  const input = control ?? (type === "textarea"
    ? h("textarea", { class: "textarea", ...attrs }, value)
    : h("input", { class: "input", type, value, ...attrs }));
  input.id = id;
  if (hintId) input.setAttribute("aria-describedby", hintId);
  const node = h("div", { class: "field" },
    h("label", { for: id }, label),
    input,
    hint ? h("div", { class: "hint", id: hintId }, hint) : null,
    errorNode);
  const setError = (message) => {
    errorNode.hidden = !message;
    errorNode.textContent = message ?? "";
    if (message) {
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", [hintId, errorNode.id].filter(Boolean).join(" "));
    } else {
      input.removeAttribute("aria-invalid");
      if (hintId) input.setAttribute("aria-describedby", hintId);
      else input.removeAttribute("aria-describedby");
    }
  };
  return { node, input, setError };
}

export function select(label, options, { value = "", hint = null, ...attrs } = {}) {
  const control = h("select", { class: "select", ...attrs },
    options.map(([key, text]) => h("option", { value: key, selected: String(key) === String(value) }, text)));
  return field(label, { hint, control });
}

export function checkbox(label, { checked = false, hint = null, ...attrs } = {}) {
  const id = uid("check");
  const input = h("input", { type: "checkbox", id, checked, ...attrs });
  const node = h("div", { class: "check" }, input,
    h("div", {}, h("label", { for: id }, label), hint ? h("div", { class: "hint subtle" }, hint) : null));
  return { node, input };
}

/**
 * Run a save. While it runs the button is disabled. Field errors from the server are shown
 * on their fields (fields: { name: fieldObject }); anything else is shown in the banner.
 */
export async function submit({ button, fields = {}, banner = null, run }) {
  for (const f of Object.values(fields)) f.setError(null);
  if (banner) banner.hidden = true;
  button.disabled = true;
  try {
    return await run();
  } catch (error) {
    const perField = error.fields ?? {};
    let placed = false;
    for (const [name, message] of Object.entries(perField)) {
      if (fields[name]) {
        fields[name].setError(message);
        placed = true;
      }
    }
    const firstBad = Object.entries(perField).find(([name]) => fields[name]);
    if (firstBad) fields[firstBad[0]].input.focus();
    if (banner && (!placed || !Object.keys(perField).length)) {
      const extra = Object.entries(perField).filter(([name]) => !fields[name]).map(([, message]) => message);
      banner.textContent = [error.detail || "That did not work.", ...extra].join(" ");
      banner.hidden = false;
    }
    return undefined;
  } finally {
    button.disabled = false;
  }
}

export function banner() {
  return h("div", { class: "alert alert-danger", role: "alert", hidden: true });
}
