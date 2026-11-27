// Third parties → Coverage: every place information is shared with a third party and no
// agreement of a kind the program requires covers it, with the rules that say so.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { stopLine } from "../components/stops.js";
import { alert, card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

export function coveragePage(main) {
  return show(main, {
    title: "Coverage",
    load: async () => (await get("/api/v1/coverage", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Third parties", title: "Coverage",
        lede: "Where information is shared with a third party, directly or through one of its services, and no agreement of a kind the program requires is with that third party and covers it." }),
      data.stops.length ? card({ title: plural(data.stops.length, "stop") }, h("ul", { class: "plain-list stack-lg" }, data.stops.map(stopLine)))
        : emptyState({ iconName: "check", title: "Everything shared is covered",
          text: "Every piece of information the rules name, shared with a third party you can see, is covered by an agreement of a kind they require." }),
      card({ title: "The rules" },
        h("p", { class: "muted" }, "Each says which kinds of agreement information needs when it is shared. They are part of the program, and travel with it when it is exported."),
        h("ul", { class: "plain-list stack" }, data.rules.map((rule) => h("li", {}, rule.reason)))),
      alert("info", h("div", {}, "Information is shared with a third party when it is linked as shared with it, or one of its services handles it. An agreement covers it when it is with that third party, in force, and covers the information, the service, or a scope that holds the information."))),
  });
}
