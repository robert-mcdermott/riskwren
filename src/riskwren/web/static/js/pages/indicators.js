// Indicators: numbers read on a schedule that warn of risks. Someone reads the number where
// it lives and records it here; RiskWren shows where it stands against its levels.

import { get, patch, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural, titleCase } from "../core/format.js";
import { unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query, setQuery } from "../core/router.js";
import { can } from "../core/session.js";
import { exportButton } from "../components/exchange.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { amount, readingChart, statePill, STATES, trendWord } from "../components/indicator.js";
import { closeOverlay, openOverlay } from "../components/overlay.js";
import { standingPill } from "../components/risk.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";

const FREQUENCIES = [["weekly", "Every week"], ["monthly", "Every month"], ["quarterly", "Every quarter"], ["annually", "Every year"]];
const WORSE = [["up", "Higher is worse"], ["down", "Lower is worse"]];

function form(body, { record = null, unitIndex, onDone }) {
  const name = field("What is measured", { value: record?.name ?? "", required: true, hint: "Such as “Days to remove a leaver's access” or “Servers patched within 30 days”." });
  const unit = select("Unit", unitOptions(unitIndex.tree, { blank: "Choose a unit" }), { value: record?.org_unit_id ?? "" });
  const measure = field("Counted in", { value: record?.measure ?? "", hint: "Such as %, days, or accounts. Leave empty for a plain count." });
  const direction = select("Which way is worse", WORSE, { value: record?.direction ?? "up" });
  const warn = field("Warning level", { type: "number", step: "any", value: record?.warn_at ?? "", hint: "Where it should start to worry people. Optional." });
  const breach = field("Limit", { type: "number", step: "any", value: record?.breach_at ?? "", required: true, hint: "Past this, its owners are told and the risks it warns of are flagged." });
  const frequency = select("Read", FREQUENCIES, { value: record?.frequency ?? "monthly" });
  const source = field("Where the number is read from", { type: "textarea", rows: 2, value: record?.source ?? "", hint: "A report, a console, a query. RiskWren does not fetch it: a person reads it and records it here." });
  const summary = field("Why it matters", { type: "textarea", rows: 2, value: record?.summary ?? "" });
  const retired = record ? checkbox("Retired: no more readings are taken", { checked: record.status === "retired" }) : null;
  const problem = banner();
  const save = button(record ? "Save" : "Add the indicator", { kind: "btn-primary", type: "submit" });
  body.append(h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const values = { name: name.input.value, org_unit_id: Number(unit.input.value) || null, measure: measure.input.value, direction: direction.input.value,
      warn_at: warn.input.value === "" ? null : Number(warn.input.value), breach_at: breach.input.value === "" ? null : Number(breach.input.value),
      frequency: frequency.input.value, source: source.input.value, summary: summary.input.value };
    const done = await submit({ button: save, fields: { name, org_unit_id: unit, measure, direction, warn_at: warn, breach_at: breach, frequency, source, summary }, banner: problem,
      run: () => (record ? patch(`/api/v1/indicators/${record.ref}`, { ...values, version: record.version, status: retired.input.checked ? "retired" : "active" })
        : post("/api/v1/indicators", values)) });
    if (done) {
      closeOverlay();
      onDone(done.data);
    }
  } }, problem, name.node, unit.node, h("div", { class: "grid-2" }, measure.node, direction.node), h("div", { class: "grid-2" }, warn.node, breach.node),
  frequency.node, source.node, summary.node, retired?.node, h("div", {}, save)));
}

export function indicatorList(main) {
  const state = query().get("state");
  const filters = Object.fromEntries(["state", "unit", "risk", "status"].map((key) => [key, query().get(key)]).filter(([, value]) => value));
  return show(main, {
    title: "Indicators",
    load: async () => {
      const [found, unitIndex] = await Promise.all([get("/api/v1/indicators", { ...filters, limit: 200, sort: "state" }, { fresh: true }), units()]);
      return { rows: found.data, total: found.meta?.total ?? found.data.length, units: unitIndex };
    },
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Risks", title: "Indicators",
        lede: "Numbers read on a schedule that warn of a risk before it happens. Each has a level to worry at and a limit. Past the limit, its owners are told and the risks it warns of are flagged.",
        actions: h("div", { class: "row-sm wrap" }, exportButton("indicators", filters),
          can("steward") ? button("Add an indicator", { kind: "btn-primary", iconName: "plus",
            onclick: () => openOverlay({ title: "Add an indicator", render: (body) => form(body, { unitIndex: data.units, onDone: (made) => navigate(`/indicators/${made.ref}`) }) }) }) : null) }),
      h("div", { class: "segmented", role: "group", "aria-label": "Narrow by where each stands" },
        [[null, "All"], ["breach", "Past the limit"], ["warn", "Warning"], ["ok", "Within limits"], ["no_reading", "No reading"]].map(([key, text]) =>
          h("button", { type: "button", "aria-pressed": String((state ?? null) === key), onclick: () => setQuery({ state: key }, { replace: false }) }, text))),
      data.rows.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Indicator"), h("th", { scope: "col" }, "Stands at"), h("th", { scope: "col" }, "Limit"),
          h("th", { scope: "col" }, "Where it stands"), h("th", { scope: "col" }, "Next reading"), h("th", { scope: "col" }, "Warns of"))),
        h("tbody", {}, data.rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/indicators/${row.ref}` }, row.name),
            h("div", { class: "cell-sub" }, h("span", { class: "mono" }, row.ref), ` · ${data.units.byId.get(row.org_unit_id)?.name ?? ""}`)),
          h("td", {}, row.last_value == null ? h("span", { class: "subtle" }, "Not read") : [amount(row, row.last_value), h("div", { class: "cell-sub" }, date(row.last_read_on))]),
          h("td", {}, `${row.direction === "up" ? "At most" : "At least"} ${amount(row, row.breach_at)}`),
          h("td", {}, row.status === "retired" ? pill("Retired") : statePill(row.state)),
          h("td", {}, row.next_due ? h("span", { class: row.reading_overdue ? "text-danger" : null }, date(row.next_due), row.reading_overdue ? " (overdue)" : "") : ""),
          h("td", {}, row.risks ? plural(row.risks, "risk") : h("span", { class: "subtle" }, "Nothing yet"))))))))
        : card({}, emptyState({ iconName: "chart", title: state ? "None stand there" : "No indicators yet",
          text: state ? "Choose All to see every indicator." : "Add one for a number you already watch, and link it to the risks it warns of." }))),
  });
}

function recordReading(indicator, reload) {
  const value = field(`It stands at${indicator.measure ? ` (${indicator.measure})` : ""}`, { type: "number", step: "any", required: true });
  const day = field("Read on", { type: "date", value: new Date().toISOString().slice(0, 10), hint: "A second reading for the same day corrects the first." });
  const note = field("A note", { hint: "What explains it, if anything does." });
  const problem = banner();
  const save = button("Record the reading", { kind: "btn-primary", type: "submit" });
  return card({ title: "Record a reading" }, h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const done = await submit({ button: save, fields: { value, read_on: day, note }, banner: problem,
      run: () => post(`/api/v1/indicators/${indicator.ref}/readings`, { value: value.input.value === "" ? null : Number(value.input.value), read_on: day.input.value || null, note: note.input.value || null }) });
    if (done) {
      toast(done.data.state === "breach" ? "Recorded. It is past its limit, and those who answer for it have been told." : "Recorded.");
      reload();
    }
  } }, problem, h("div", { class: "grid-2" }, value.node, day.node), note.node, h("div", {}, save)));
}

function linkRisks(indicator, reload) {
  openOverlay({ title: "The risks it warns of", render: (body) => {
    const chosen = new Map(indicator.risks.map((risk) => [risk.ref, risk.name]));
    const search = field("Find a risk", { type: "search", hint: "By name or reference." });
    const found = h("div", { class: "stack-sm", "aria-live": "polite" });
    const list = h("ul", { class: "stack-sm plain-list" });
    const draw = () => list.replaceChildren(...(chosen.size ? [...chosen].map(([ref, name]) => h("li", { class: "row-sm" },
      h("span", { class: "grow" }, name, " ", h("span", { class: "mono subtle" }, ref)),
      button("Remove", { kind: "btn-sm btn-ghost", "aria-label": `Remove ${name}`, onclick: () => { chosen.delete(ref); draw(); } })))
      : [h("li", { class: "muted" }, "None yet.")]));
    let timer = null;
    search.input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const words = search.input.value.trim();
        if (!words) return found.replaceChildren();
        const rows = (await get("/api/v1/risks", { q: words, limit: 8 })).data.filter((risk) => !chosen.has(risk.ref));
        found.replaceChildren(...(rows.length ? rows.map((risk) => button(`Add ${risk.name} (${risk.ref})`, { kind: "btn-sm", onclick: () => { chosen.set(risk.ref, risk.name); draw(); found.replaceChildren(); search.input.value = ""; } }))
          : [h("p", { class: "muted" }, "No risk you may see matches.")]));
      }, 200);
    });
    const problem = banner();
    const save = button("Save", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/indicators/${indicator.ref}/risks`, { risks: [...chosen.keys()] }) });
      if (done) {
        closeOverlay();
        reload();
      }
    });
    draw();
    body.append(h("div", { class: "stack" }, problem, h("p", { class: "muted" }, "When this indicator passes its limit, the owners of these risks are told and each risk is flagged for another look."),
      list, search.node, found, h("div", {}, save)));
  } });
}

const TABS = [["overview", "Overview"], ["history", "History"]];

export function indicatorPage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/indicators/${params.ref}`;
      const [indicator, unitIndex, vocab, extra] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { indicator: indicator.data, units: unitIndex, vocab, extra: extra?.data ?? [] };
    },
    view: (data, reload) => {
      const indicator = data.indicator;
      document.title = `${indicator.name} · ${indicator.ref}`;
      const ctx = { units: data.units, vocab: data.vocab, reload };
      const edit = indicator.can.edit ? button("Edit", { iconName: "edit", onclick: () => openOverlay({ title: "Edit the indicator",
        render: (body) => form(body, { record: indicator, unitIndex: data.units, onDone: reload }) }) }) : null;
      const readings = [...indicator.readings].reverse();
      const overview = h("div", { class: "split" },
        h("div", { class: "stack-lg" },
          indicator.state === "breach" ? alert("danger", icon("alert"), h("div", {}, h("strong", {}, `${STATES.breach[0]}. `),
            `It stands at ${amount(indicator, indicator.last_value)}, against a limit of ${amount(indicator, indicator.breach_at)}.`)) : null,
          indicator.reading_overdue ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, "A reading is overdue. "), `The next was due ${date(indicator.next_due)}. An indicator nobody reads warns of nothing.`)) : null,
          card({ title: "Readings", actions: indicator.readings.length > 1 ? h("span", { class: "muted" }, trendWord(indicator.trend)) : null },
            h("div", { class: "stack" }, readingChart(indicator, indicator.readings),
              indicator.readings.length ? h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
                h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Read on"), h("th", { scope: "col" }, "Stood at"), h("th", { scope: "col" }, "Against its levels"), h("th", { scope: "col" }, "By"), h("th", { scope: "col" }, "Note"))),
                h("tbody", {}, readings.slice(0, 12).map((reading) => h("tr", {}, h("td", {}, date(reading.read_on)), h("td", {}, amount(indicator, reading.value)),
                  h("td", {}, statePill(reading.state)), h("td", {}, reading.by), h("td", {}, reading.note ?? "")))))) : null)),
          indicator.can_read ? recordReading(indicator, reload) : null,
          card({ title: "The risks it warns of", flush: indicator.risks.length > 0,
            actions: indicator.can.edit ? button("Change", { kind: "btn-sm", onclick: () => linkRisks(indicator, reload) }) : null },
          indicator.risks.length ? h("ul", { class: "rows" }, indicator.risks.map((risk) => h("li", { class: "row" },
            h("a", { class: "grow cell-main", href: `/risks/${risk.ref}` }, risk.name, " ", h("span", { class: "mono subtle" }, risk.ref)), standingPill(risk.standing))))
            : h("p", { class: "muted" }, "Not linked to a risk yet. An indicator earns its place by warning of something."))),
        h("div", { class: "stack-lg" },
          card({ title: "At a glance" }, facts([
            ["Stands at", indicator.last_value == null ? "Not read yet" : `${amount(indicator, indicator.last_value)}, read ${date(indicator.last_read_on)}`],
            ["Warning level", indicator.warn_at == null ? null : amount(indicator, indicator.warn_at)],
            ["Limit", `${indicator.direction === "up" ? "At most" : "At least"} ${amount(indicator, indicator.breach_at)}`],
            ["Read", titleCase(indicator.frequency)],
            ["Next reading", indicator.next_due ? date(indicator.next_due) : null],
            ["Read from", prose(indicator.source)],
            ["Unit", data.units.byId.get(indicator.org_unit_id)?.name],
          ])),
          indicator.summary ? card({ title: "Why it matters" }, prose(indicator.summary)) : null,
          ownersCard(indicator, ctx)));
      return h("div", { class: "stack" },
        recordHeader(indicator, { badges: [indicator.status === "retired" ? pill("Retired") : statePill(indicator.state)], actions: edit }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : overview);
    },
  });
}
