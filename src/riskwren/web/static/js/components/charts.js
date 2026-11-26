// Small charts drawn with the page's own elements. Each is a list or a table underneath, so
// it reads the same without its bars or colors, and every figure is a link to its records.

import { buildUrl } from "../core/api.js";
import { h } from "../core/dom.js";

/** The address of the list that a figure counts, from the filters the server gave with it. */
export function listHref(path, filters = {}) {
  const params = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === true) params[key] = "true";
    else if (value !== false && value != null && value !== "") params[key] = value;
  }
  const url = new URL(buildUrl(path, params), window.location.origin);
  return `${url.pathname}${url.search}`;
}

/** A figure with its name, as a link to the records it counts. */
export function statTile({ value, label, href, tone = "" }) {
  return h("a", { class: `card stat stat-link${tone && value ? ` stat-${tone}` : ""}`, href },
    h("div", { class: "stat-value" }, String(value)), h("div", { class: "stat-label" }, label));
}

/**
 * Horizontal bars. items: [{ label, value, href, part?, partLabel?, badge? }]. `part` is a
 * share of the value drawn darker (for example, how many of them are above appetite).
 */
export function bars(items, { empty = "Nothing to show yet." } = {}) {
  const most = Math.max(1, ...items.map((item) => item.value));
  if (!items.some((item) => item.value)) return h("p", { class: "muted" }, empty);
  return h("ul", { class: "bars" }, items.map((item) => h("li", { class: "bar-row" },
    h("div", { class: "bar-label" }, item.badge ?? item.label),
    h("div", { class: "bar-track", "aria-hidden": "true" },
      h("div", { class: "bar-fill", "data-width": String(Math.round((item.value / most) * 100)) },
        item.part ? h("div", { class: "bar-part", "data-width": String(Math.round((item.part / item.value) * 100)) }) : null)),
    h("div", { class: "bar-value numeric" },
      item.href && item.value ? h("a", { href: item.href }, String(item.value)) : String(item.value),
      item.part ? h("span", { class: "cell-sub" }, ` ${item.part} ${item.partLabel ?? ""}`) : null))));
}

/**
 * One bar cut into parts, with the figures spelled out beneath it, so nothing is said by
 * color alone. parts: [{ label, value, tone }]; tone is ok, info, warn, danger, gap, excepted, or none.
 */
export function segments(parts, { label, legend = true }) {
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  const bar = h("div", { class: "segbar", role: "img", "aria-label": label }, parts.filter((part) => part.value).map((part) => {
    const piece = h("i", { "data-tone": part.tone });
    piece.style.setProperty("flex-grow", String(part.value));
    return piece;
  }));
  if (!legend) return h("div", { class: "segments" }, total ? bar : null);
  return h("div", { class: "segments" }, total ? bar : null,
    h("ul", { class: "seg-legend" }, parts.map((part) => h("li", { "data-empty": String(!part.value) },
      h("i", { "data-tone": part.tone, "aria-hidden": "true" }), h("strong", {}, String(part.value)), ` ${part.label}`))));
}

/** Widths cannot be set inline under the content security policy, so they are applied here. */
export function sizeBars(root) {
  for (const node of root.querySelectorAll("[data-width]")) node.style.setProperty("width", `${node.dataset.width}%`);
  return root;
}
