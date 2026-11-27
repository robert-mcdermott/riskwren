// A risk's bow-tie and its estimate in ranges. Loaded when one of those tabs is opened.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { statePill } from "./control.js";
import { banner, field, section, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { card, emptyState, stat } from "./ui.js";

// --- The bow-tie ---------------------------------------------------------------------------

function column(label, items, render, empty) {
  return h("section", { class: "bowtie-col", "aria-label": label },
    h("h3", { class: "bowtie-head" }, label),
    items.length ? h("ul", { class: "bowtie-list" }, items.map((item) => h("li", { class: "bowtie-item" }, render(item))))
      : h("p", { class: "subtle bowtie-empty" }, empty));
}

const control = (item) => [h("a", { href: `/controls/${item.ref}` }, item.name), " ", statePill(item.state)];

export function bowTieTab(risk, data) {
  const diagram = h("div", { class: "bowtie" },
    column("Causes", data.causes, (text) => text, "No cause is written on the risk."),
    column("Keep it from happening", data.preventive, control, "No control reduces its likelihood."),
    h("div", { class: "bowtie-knot" }, h("div", { class: "eyebrow" }, "The event"), h("strong", {}, data.event)),
    column("Soften what follows", data.mitigating, control, "No control reduces its impact."),
    column("Consequences", data.consequences, (text) => text, "No consequence is written on the risk."));
  const rows = [
    ...data.causes.map((text) => ["Cause", text, null]),
    ...data.preventive.map((item) => ["Keeps it from happening", item, item.reduces]),
    ["Event", data.event, null],
    ...data.mitigating.map((item) => ["Softens what follows", item, item.reduces]),
    ...data.consequences.map((text) => ["Consequence", text, null]),
  ];
  return h("div", { class: "stack-lg" },
    card({ title: "Bow-tie" },
      h("p", { class: "muted" }, "Read left to right: what could cause the event, the controls that keep it from happening, the event, the controls that soften what follows, and the consequences. It is drawn from the risk's own words and the controls on its Controls tab; a cause or consequence written one to a line, or with semicolons, is drawn as several."),
      diagram),
    card({ title: "The same, as a table", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Part"), h("th", { scope: "col" }, "What"), h("th", { scope: "col" }, "Where it stands"))),
      h("tbody", {}, rows.map(([part, what]) => h("tr", {},
        h("td", {}, part),
        h("td", {}, typeof what === "string" ? what : h("a", { href: `/controls/${what.ref}` }, `${what.ref} ${what.name}`)),
        h("td", {}, typeof what === "string" ? "" : statePill(what.state)))))))),
    data.hidden ? h("p", { class: "subtle" }, `And ${data.hidden} more controls you do not have access to.`) : null);
}

// --- In numbers ------------------------------------------------------------------------------

function money(value, currency) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD", maximumFractionDigits: 0 }).format(value);
}

function often(value) {
  if (value >= 1) return `${value} a year`;
  if (value === 0) return "never";
  return `once in ${Math.round(1 / value)} years`;
}

function estimateForm(risk, last, onDone) {
  openOverlay({ title: "Estimate in ranges", subtitle: `${risk.ref} · ${risk.name}`,
    render: (body, footer, close) => {
      const take = (key, part, hint) => field(`${part[0].toUpperCase()}${part.slice(1)}`, { type: "number", min: 0, step: "any", required: true, value: last?.[key]?.[part] ?? "", hint });
      const fields = {
        frequency_low: take("frequency", "low", "Times a year: 0.1 is once a decade"), frequency_likely: take("frequency", "likely"), frequency_high: take("frequency", "high"),
        loss_low: take("loss", "low", "Each time, in whole units of the currency"), loss_likely: take("loss", "likely"), loss_high: take("loss", "high"),
        currency: field("Currency", { value: last?.currency ?? "USD", maxlength: 3 }),
        assumptions: field("What the numbers assume", { type: "textarea", rows: 3, required: true, value: last?.assumptions ?? "", hint: "Where they came from: incidents here or at peers, quotes, the cost of a week without the system." }),
      };
      const problem = banner();
      const save = button("Record the estimate", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const values = Object.fromEntries(Object.entries(fields).map(([key, each]) => [key, key === "currency" || key === "assumptions" ? each.input.value : Number(each.input.value)]));
        const done = await submit({ button: save, banner: problem, fields, run: () => post(`/api/v1/risks/${risk.ref}/estimate`, values) });
        if (!done) return;
        close();
        toast("Recorded. The earlier estimate is kept.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("How often", h("div", { class: "grid-3" }, fields.frequency_low.node, fields.frequency_likely.node, fields.frequency_high.node)),
        section("What it costs each time", h("div", { class: "grid-3" }, fields.loss_low.node, fields.loss_likely.node, fields.loss_high.node), fields.currency.node),
        section("Why", fields.assumptions.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

/** What a simulation came to: figures, the chance of exceeding each loss, and its assumptions. */
export function simulationView(found, currency) {
  const p = found.percentiles;
  return h("div", { class: "stack" },
    h("div", { class: "grid-3" },
      stat(money(found.mean, currency), "Average loss a year"),
      stat(money(p["90"], currency), "Exceeded one year in ten"),
      stat(`${Math.round(found.any_loss * 100)}%`, "Chance of any loss in a year")),
    found.exceedance.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("caption", { class: "sr-only" }, "The chance that a year's loss is more than each figure"),
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "A year's loss above"), h("th", { scope: "col", class: "numeric" }, "Chance"))),
      h("tbody", {}, found.exceedance.map((point) => h("tr", {},
        h("td", {}, money(point.loss, currency)),
        h("td", { class: "numeric" }, `${(point.chance * 100).toFixed(1)}%`)))))) : null,
    h("p", { class: "subtle" }, `In ${found.years.toLocaleString()} simulated years: half lost no more than ${money(p["50"], currency)}, one in twenty more than ${money(p["95"], currency)}, one in a hundred more than ${money(p["99"], currency)}, and the worst ${money(found.worst, currency)}. The ranges' own expectation is ${money(found.expected, currency)} a year.`),
    h("details", {}, h("summary", {}, "What the simulation assumes"), h("ul", {}, found.assumptions.map((line) => h("li", {}, line)))));
}

export function estimateTab(risk, data, reload) {
  const now = data.estimate;
  const act = data.can_estimate ? button(now ? "Estimate anew" : "Estimate in ranges", { kind: now ? "" : "btn-primary", onclick: () => estimateForm(risk, now, reload) }) : null;
  if (!now) {
    return card({}, emptyState({ iconName: "chart", title: "No estimate in ranges",
      text: "Put numbers to the risk: how often a year, and what each time costs, each as a low, likely, and high value. A simulation then says what a year's loss is likely to be. It does not replace the rating.", action: act }));
  }
  return h("div", { class: "stack-lg" },
    card({ title: "The estimate", actions: act },
      h("dl", { class: "dl" },
        h("dt", {}, "How often"), h("dd", {}, `${often(now.frequency.low)} to ${often(now.frequency.high)}; likely ${often(now.frequency.likely)}`),
        h("dt", {}, "Each time"), h("dd", {}, `${money(now.loss.low, now.currency)} to ${money(now.loss.high, now.currency)}; likely ${money(now.loss.likely, now.currency)}`),
        h("dt", {}, "Assumes"), h("dd", {}, now.assumptions),
        h("dt", {}, "Estimated"), h("dd", {}, `${date(now.estimated_at)} by ${now.estimated_by}`))),
    card({ title: "What a year's loss is likely to be" }, simulationView(data.simulation, now.currency)),
    data.earlier.length ? card({ title: "Earlier estimates", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "When"), h("th", { scope: "col" }, "How often, likely"), h("th", { scope: "col" }, "Each time, likely"), h("th", { scope: "col" }, "By"))),
      h("tbody", {}, data.earlier.map((row) => h("tr", {},
        h("td", {}, date(row.estimated_at)), h("td", {}, often(row.frequency.likely)), h("td", {}, money(row.loss.likely, row.currency)), h("td", {}, row.estimated_by))))))) : null);
}
