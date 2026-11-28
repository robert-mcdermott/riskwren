// Reports → Resilience: every process with a business impact analysis, what it needs, and
// what it relies on that cannot deliver it.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { hours } from "../components/resilience.js";
import { card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

export function resiliencePage(main) {
  return show(main, {
    title: "Resilience",
    load: async () => (await get("/api/v1/resilience", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Reports", title: "Resilience",
        lede: "Each process with a business impact analysis: how soon it must be back, how much information it can lose, and what it relies on that cannot deliver that, or whose capability nobody has said. Those with the most shortfalls come first." }),
      h("p", { class: "subtle", role: "status" }, `${data.processes.length} analysed; ${data.without} in use with no analysis yet.`),
      data.processes.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Process"), h("th", { scope: "col" }, "Back within"), h("th", { scope: "col" }, "Loses at most"),
          h("th", { scope: "col" }, "Shortfalls"))),
        h("tbody", {}, data.processes.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/processes/${row.ref}?tab=impact` }, row.name), h("div", { class: "cell-sub" }, `${row.ref} · ${row.criticality}`)),
          h("td", {}, hours(row.recovery_hours)), h("td", {}, hours(row.data_loss_hours)),
          h("td", {}, row.shortfalls.length ? h("ul", { class: "plain-list stack-sm" }, row.shortfalls.map((dep) => h("li", {}, dep.name, h("span", { class: "subtle" }, ` · ${dep.problems[0]}`))))
            : pill(row.dependencies ? "None" : "Relies on nothing yet", row.dependencies ? "ok" : ""))))))))
        : emptyState({ iconName: "process", title: "No process has been analysed", text: "Open a process's Business impact tab to say what it needs." })),
  });
}
