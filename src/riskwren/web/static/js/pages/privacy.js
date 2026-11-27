// Compliance → Privacy impact: every process and system whose data class needs a privacy
// impact assessment, and where each stands.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date } from "../core/format.js";
import { units } from "../core/lookups.js";
import { privacyState } from "../components/privacy.js";
import { card, emptyState, pageHeader, stat } from "../components/ui.js";
import { show } from "./page.js";

export function privacyPage(main) {
  return show(main, {
    title: "Privacy impact",
    load: async () => {
      const [data, unitIndex] = await Promise.all([get("/api/v1/privacy", null, { fresh: true }), units()]);
      return { ...data.data, units: unitIndex };
    },
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Compliance", title: "Privacy impact",
        lede: `Every process and system that handles ${data.classes.join(" or ")} information needs a privacy impact assessment, answered by whoever answers for it, reviewed by those who assess for its unit, and done again every ${data.months} months.`,
        actions: data.can_start ? h("a", { class: "btn btn-primary", href: "/campaigns" }, "Start a campaign") : null }),
      h("div", { class: "grid-3" },
        stat(String(data.counts.never + data.counts.due), "Never assessed, or due again"),
        stat(String(data.counts.to_review), "Answered, to review"),
        stat(String(data.counts.current), "Reviewed and current")),
      card({ title: "Processes and systems", flush: true }, data.rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Record"), h("th", { scope: "col" }, "Where it stands"), h("th", { scope: "col" }, "Last answered"), h("th", { scope: "col" }, "Due again"))),
        h("tbody", {}, data.rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/${row.type === "process" ? "processes" : "systems"}/${row.ref}?tab=privacy` }, row.name),
            h("div", { class: "cell-sub" }, [row.ref, data.units.byId.get(row.org_unit_id)?.name].filter(Boolean).join(" · "))),
          h("td", {}, privacyState(row.state), row.last?.concerns.length ? h("div", { class: "cell-sub" }, `${row.last.concerns.length} concerns`) : null),
          h("td", {}, row.last ? date(row.last.answered_at) : h("span", { class: "subtle" }, "Never")),
          h("td", {}, row.due_on ? date(row.due_on) : "—"))))))
        : emptyState({ iconName: "check", title: "Nothing needs one", text: "No process or system in use handles a class of data that needs a privacy impact assessment." }))),
  });
}
