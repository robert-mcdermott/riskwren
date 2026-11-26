// Tiny DOM helpers. Data is only ever inserted as text nodes, never parsed as markup.

import { icon } from "./icons.js";

/**
 * Create an element. attrs: class, data-*, aria-*, on<Event> handlers, and any other
 * attribute. Children may be nodes, strings, numbers, arrays, or null.
 */
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "style") {
      throw new Error("Inline styles are not allowed; use classes or CSS variables.");
    } else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, String(value));
  }
  append(node, children);
  return node;
}

export function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function replace(target, ...children) {
  target.replaceChildren();
  append(target, children);
  return target;
}

export function iconButton(name, label, attrs = {}) {
  return h("button", { type: "button", class: "icon-button", "aria-label": label, title: label, ...attrs },
    icon(name));
}

/** A button with an optional icon before its words. */
export function button(label, { kind = "", iconName = null, ...attrs } = {}) {
  return h("button", { type: "button", class: `btn ${kind}`.trim(), ...attrs },
    iconName ? icon(iconName, "icon icon-sm") : null, label);
}

let counter = 0;
export function uid(prefix = "id") {
  counter += 1;
  return `${prefix}-${counter}`;
}

export { icon };
