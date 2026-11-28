// The incidents that bear on a risk or a control: those that realized it, or in which it
// failed or held, with what they cost. Only those the person may see.

import { h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { card, pill } from "./ui.js";

const ROLE = { realized: ["Realized it", "danger"], failed: ["It failed", "danger"], held: ["It held", "ok"] };

function money(totals) {
  return Object.entries(totals).map(([currency, amount]) =>
    new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount)).join(" + ");
}

export function incidentsCard(found) {
  if (!found?.items.length) return null;
  const cost = money(found.loss_totals);
  return card({ title: "Incidents" }, h("div", { class: "stack" },
    h("p", { class: "muted" }, `${plural(found.last_year, "report", "reports")} (incidents, near misses, and concerns) in the last year${cost ? `, costing ${cost} in all` : ""}.`),
    h("ul", { class: "plain-list stack-sm" }, found.items.map((item) => h("li", {},
      h("a", { class: "cell-main", href: `/incidents/${item.ref}` }, item.name),
      h("div", { class: "row-sm wrap" }, pill(...ROLE[item.role]), h("span", { class: "cell-sub" }, [item.ref, item.kind === "near_miss" ? "near miss" : item.kind,
        date(item.reported_at), money(item.loss_totals)].filter(Boolean).join(" · "))))))));
}
