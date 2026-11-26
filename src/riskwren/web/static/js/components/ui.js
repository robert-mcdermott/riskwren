// Small pieces used on every page.

import { button, h, icon } from "../core/dom.js";
import { initials, titleCase } from "../core/format.js";

export function pageHeader({ eyebrow = null, title, lede = null, actions = null }) {
  return h("header", { class: "page-header" },
    h("div", { class: "grow" },
      eyebrow ? h("div", { class: "eyebrow" }, eyebrow) : null,
      h("h1", { tabindex: "-1" }, title),
      lede ? h("p", { class: "lede" }, lede) : null),
    actions ? h("div", { class: "row wrap" }, actions) : null);
}

export function card({ title = null, actions = null, footer = null, flush = false }, ...children) {
  return h("section", { class: "card" },
    title ? h("div", { class: "card-header" }, h("h2", { class: "grow" }, title), actions) : null,
    h("div", { class: flush ? "" : "card-body" }, children),
    footer ? h("div", { class: "card-footer" }, footer) : null);
}

export function emptyState({ iconName = "info", title, text = null, action = null }) {
  return h("div", { class: "empty" },
    icon(iconName, "empty-icon"), h("h2", {}, title), text ? h("p", {}, text) : null, action);
}

export function errorState(error, retry) {
  return emptyState({
    iconName: "alert",
    title: error?.status === 403 ? "You do not have access to this" : "Something went wrong",
    text: error?.detail || error?.message || "The page could not be loaded.",
    action: retry && error?.status !== 403 ? button("Try again", { onclick: retry }) : null,
  });
}

export function skeletonPage() {
  return h("div", { "aria-busy": "true", "aria-label": "Loading" },
    h("div", { class: "skeleton skeleton-title" }),
    h("div", { class: "skeleton skeleton-line" }),
    h("div", { class: "skeleton skeleton-line" }),
    h("div", { class: "skeleton skeleton-block" }));
}

export function avatar(name, large = false) {
  return h("span", { class: `avatar${large ? " avatar-lg" : ""}`, "aria-hidden": "true" }, initials(name));
}

const TONES = { active: "ok", invited: "info", disabled: "", closed: "" };

/** A word in a pill, colored by what it means. tone: ok, warn, danger, info, accent, or none. */
export function pill(text, tone = "") {
  return h("span", { class: `pill${tone ? ` pill-${tone}` : ""}` }, text);
}

export function statusPill(status) {
  return pill(titleCase(status), TONES[status] ?? "");
}

/** Where the rating at `position` of `count` sits on the five-step ramp: the ends stay at the ends. */
export function rampLevel(position, count) {
  if (!position) return 0;
  return count <= 1 ? 5 : Math.round(1 + ((position - 1) * 4) / (count - 1));
}

/** A rating: its own hue, a bar glyph, and its name. Never the standing colors. Level 0 is "not rated". */
export function ratingBadge(level, name) {
  return h("span", { class: "rating", "data-level": level },
    h("span", { class: "rating-bars", "aria-hidden": "true" }, h("i"), h("i"), h("i"), h("i"), h("i")),
    name ?? "Not rated");
}

export function stat(value, label) {
  return h("div", { class: "card stat" }, h("div", { class: "stat-value" }, value), h("div", { class: "stat-label" }, label));
}

export function alert(tone, ...children) {
  return h("div", { class: `alert alert-${tone}` }, children);
}
