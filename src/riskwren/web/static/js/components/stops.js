// A stop: information shared with a third party that needs an agreement no agreement meets.
// Shown at the top of every record involved, and gathered on Third parties → Coverage.

import { h, icon } from "../core/dom.js";
import { recordChip } from "./record.js";

/** One stop, in a sentence, with the records it joins. */
export function stopLine(stop) {
  return h("li", { class: "stack-sm" },
    h("div", { class: "row-sm wrap" }, recordChip(stop.information), h("span", {}, "is shared with"), recordChip(stop.third_party),
      stop.service ? [h("span", {}, "through"), recordChip(stop.service)] : null),
    h("ul", { class: "plain-list stack-sm" }, stop.needs.map((need) => h("li", {},
      `It needs ${need.kinds_words} with ${stop.third_party.name} that covers it, and none does. ${need.reason}`))),
    stop.agreements.length ? h("div", { class: "subtle" }, "With them already, and not meeting it: ",
      stop.agreements.map((each, index) => [index ? ", " : "", h("a", { href: `/agreements/${each.ref}` }, `${each.ref} ${each.name}`)])) : null);
}

export function stopsBanner(stops) {
  return h("div", { class: "alert alert-danger stop", role: "note" }, icon("alert"),
    h("div", { class: "grow stack-sm" }, h("strong", {}, stops.length === 1 ? "Stop: no agreement covers what is shared" : `Stop: ${stops.length} things shared that no agreement covers`),
      h("ul", { class: "plain-list stack" }, stops.map(stopLine))));
}
