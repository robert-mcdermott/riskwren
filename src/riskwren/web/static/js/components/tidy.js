// What every list shares for keeping things in order: saved views, the filter for what a
// record is missing, and, as a name is typed, what it might already be.

import { get } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { query, setQuery } from "../core/router.js";
import { hrefOf } from "./record.js";

const MISSING = {
  any: "anything expected of them", owner: "an owner who can sign in", hosting: "where they are hosted", held_in: "where they are held",
  data_class: "the class of data they handle", links: "a link to anything else", rating: "a rating",
  controls: "a control that bears on them",
  reading: "a reading", risks: "a risk they warn of", source: "where they are read from",
  published: "a version in force", parent: "what they implement", governs: "a control they direct or a requirement they answer",
};

/** What goes beside a list's search box: what it is cut to, and its saved views. */
export function listTools() {
  const lacking = query().get("missing");
  return [
    lacking ? h("span", { class: "pill pill-warn" }, `Missing ${MISSING[lacking] ?? lacking}`,
      h("button", { type: "button", class: "pill-x", "aria-label": "Show all of them again", onclick: () => setQuery({ missing: null, cursor: null }) }, icon("close", "icon icon-sm"))) : null,
    button("Views", { iconName: "plan", "aria-haspopup": "dialog", onclick: async () => (await import("./views.js")).openViews() }),
  ];
}

/** On a record's page: what it ought to say and does not yet. */
export function missingNote(record) {
  if (!record.missing?.length) return null;
  return h("div", { class: "missing-note" }, icon("info", "icon icon-sm"),
    h("div", {}, h("strong", {}, "Not yet said: "), record.missing.map((each) => each.label).join(", "), ". ",
      h("span", { class: "muted" }, record.missing[0].why)));
}

/**
 * Under a name being typed: records already here that this might be. `unit` is a function
 * giving the unit chosen so far.
 */
export function similarHint(type, input, { unit = () => null, apartFrom = null } = {}) {
  const node = h("div", { class: "similar", "aria-live": "polite" });
  let timer = null;
  let latest = 0;
  const look = async () => {
    const name = input.value.trim();
    const mine = ++latest;
    if (name.length < 4) {
      node.replaceChildren();
      return;
    }
    let found = [];
    try {
      found = (await get("/api/v1/similar", { type, name, unit: unit() || undefined, apart_from: apartFrom || undefined }, { fresh: true })).data;
    } catch {
      found = [];
    }
    if (mine !== latest) return;
    node.replaceChildren(...(found.length ? [h("div", { class: "similar-box" },
      h("div", { class: "label" }, found.length === 1 ? "This may already be here" : "These may already be here"),
      h("ul", { class: "plain-list" }, found.map((each) => h("li", {},
        h("a", { href: hrefOf(each.ref), target: "_blank", rel: "noopener" }, each.name), " ", h("span", { class: "ref" }, each.ref)))),
      h("div", { class: "hint" }, "Opens in a new tab. If it is the same thing, add to that one instead."))] : []));
  };
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(look, 350);
  });
  return node;
}

