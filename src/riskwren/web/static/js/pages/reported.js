// Compliance → From other systems: what other systems have reported of controls, waiting for
// an assessor to confirm or set aside.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { reportedRows } from "../components/reported.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

export function reportedPage(main) {
  return show(main, {
    title: "From other systems",
    load: async () => (await get("/api/v1/reported", null, { fresh: true })).data,
    view: (list, reload) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Compliance", title: "From other systems",
        lede: "Checks and evidence that scanners and other systems have reported onto controls you assess. Each counts once you confirm it: a failure raises an issue, and evidence is filed with the control." }),
      list.length ? card({ title: `${list.length} waiting`, flush: true }, reportedRows(list, reload))
        : emptyState({ title: "Nothing is waiting", text: "When another system reports a check or a piece of evidence onto a control you assess, it is here until it is confirmed or set aside." })),
  });
}
