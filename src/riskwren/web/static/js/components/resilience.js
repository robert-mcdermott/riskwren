// A process's business impact, and what a system or service can deliver. Loaded when one of
// those tabs is opened.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { TYPES } from "./record.js";
import { banner, field, section, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { alert, card, emptyState, pill } from "./ui.js";

export function hours(value) {
  if (value == null) return "—";
  if (value === 0) return "at once";
  if (value % 24 === 0 && value >= 24) return value === 24 ? "1 day" : `${value / 24} days`;
  return value === 1 ? "1 hour" : `${value} hours`;
}

function impactForm(record, data, onDone) {
  const last = data.analysis;
  openOverlay({ title: "Analyse its business impact", subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const levels = [["", "Not said"], ...Object.entries(data.levels).map(([key, label]) => [key, `${key} · ${label}`])];
      const rows = Object.entries(data.after).map(([key, label]) => {
        const was = last?.impacts.find((row) => row.after === key);
        return { key, input: select(`After ${label}`, levels, { value: was ? String(was.level) : "" }) };
      });
      const recovery = field("Must be back within, in hours", { type: "number", min: 0, step: 1, required: true, value: last?.recovery_hours ?? "", hint: "How soon it must run again: its recovery time." });
      const loss = field("Can lose at most, in hours of information", { type: "number", min: 0, step: 1, required: true, value: last?.data_loss_hours ?? "", hint: "How far back it can afford to go: its recovery point." });
      const minimum = field("The least it needs to run", { type: "textarea", rows: 3, value: last?.minimum ?? "", hint: "People, space, systems, and supplies." });
      const note = field("Note", { type: "textarea", rows: 2 });
      const problem = banner();
      const go = button("Record the analysis", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const impacts = rows.filter((row) => row.input.input.value).map((row) => ({ after: row.key, level: Number(row.input.input.value) }));
        const done = await submit({ button: go, banner: problem, fields: { recovery_hours: recovery, data_loss_hours: loss, minimum, note },
          run: () => post(`/api/v1/processes/${record.ref}/impact`, { impacts, recovery_hours: Number(recovery.input.value), data_loss_hours: Number(loss.input.value),
            minimum: minimum.input.value || null, note: note.input.value || null }) });
        if (!done) return;
        close();
        toast(last ? "Recorded. The earlier analysis is kept." : "Recorded.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("How much its loss hurts", h("p", { class: "subtle" }, "As time goes on, a loss hurts no less."), h("div", { class: "grid-2" }, rows.map((row) => row.input.node))),
        section("What it needs", recovery.node, loss.node, minimum.node), note.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function capabilityForm(kind, record, data, onDone) {
  const last = data.capability;
  openOverlay({ title: "What it can deliver", subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const recovery = field("Back within, in hours", { type: "number", min: 0, step: 1, required: true, value: last?.recovery_hours ?? "" });
      const loss = field("Loses at most, in hours of information", { type: "number", min: 0, step: 1, required: true, value: last?.data_loss_hours ?? "" });
      const basis = field("What that rests on", { type: "textarea", rows: 3, required: true, hint: "A restore tested on a date, a supplier's contract, a design that has not been tried." });
      const problem = banner();
      const go = button("Record it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { recovery_hours: recovery, data_loss_hours: loss, basis },
          run: () => post(`/api/v1/${TYPES[kind].path}/${record.ref}/recovery`, { recovery_hours: Number(recovery.input.value), data_loss_hours: Number(loss.input.value), basis: basis.input.value }) });
        if (!done) return;
        close();
        toast("Recorded.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, recovery.node, loss.node, basis.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

export function impactTab(record, data, reload) {
  const now = data.analysis;
  const act = data.can_analyse ? button(now ? "Analyse again" : "Analyse its business impact", { kind: now ? "" : "btn-primary", onclick: () => impactForm(record, data, reload) }) : null;
  if (!now) {
    return card({}, emptyState({ iconName: "process", title: "No business impact analysis yet",
      text: "Say how much its loss hurts as time goes on, how soon it must be back, how much information it can lose, and the least it needs to run. What it relies on is then checked against that.", action: act }));
  }
  const deps = data.dependencies;
  return h("div", { class: "stack-lg" },
    data.shortfalls ? alert("warn", h("strong", {}, `${data.shortfalls} shortfall${data.shortfalls === 1 ? "" : "s"}. `), "Some of what it relies on cannot deliver what it needs, or nobody has said.")
      : deps.length ? alert("ok", "Everything it relies on can deliver what it needs.") : null,
    card({ title: "What it needs", actions: act },
      h("dl", { class: "dl" },
        h("dt", {}, "Back within"), h("dd", {}, hours(now.recovery_hours)),
        h("dt", {}, "Loses at most"), h("dd", {}, `${hours(now.data_loss_hours)} of information`),
        now.minimum ? [h("dt", {}, "The least it needs"), h("dd", {}, now.minimum)] : null,
        h("dt", {}, "Analysed"), h("dd", {}, `${date(now.analysed_at)} by ${now.analysed_by}`)),
      now.impacts.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("caption", { class: "sr-only" }, "How much its loss hurts as time goes on"),
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "After"), h("th", { scope: "col" }, "Impact"))),
        h("tbody", {}, now.impacts.map((row) => h("tr", {}, h("td", {}, data.after[row.after]), h("td", {}, `${row.level} · ${data.levels[row.level]}`)))))) : null),
    card({ title: "What it relies on", flush: deps.length > 0 }, deps.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Dependency"), h("th", { scope: "col" }, "Back within"), h("th", { scope: "col" }, "Loses at most"), h("th", { scope: "col" }, "Against what it needs"))),
      h("tbody", {}, deps.map((dep) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/${TYPES[dep.type].path}/${dep.ref}?tab=recovery` }, dep.name), h("div", { class: "cell-sub" }, `${TYPES[dep.type].label} · ${dep.ref}`)),
        h("td", {}, dep.capability ? hours(dep.capability.recovery_hours) : h("span", { class: "subtle" }, "Not said")),
        h("td", {}, dep.capability ? hours(dep.capability.data_loss_hours) : h("span", { class: "subtle" }, "Not said")),
        h("td", {}, dep.problems.length ? h("ul", { class: "plain-list stack-sm" }, dep.problems.map((text) => h("li", { class: "warn-text" }, text))) : pill("Enough", "ok")))))))
      : h("p", { class: "muted" }, "It relies on no system or service yet. Link them on its Overview tab.")));
}

export function recoveryTab(kind, record, data, reload) {
  const now = data.capability;
  const act = data.can_record ? button(now ? "Say again" : "Say what it can deliver", { kind: now ? "" : "btn-primary", onclick: () => capabilityForm(kind, record, data, reload) }) : null;
  return h("div", { class: "stack-lg" },
    card({ title: "What it can deliver", actions: act }, now ? h("dl", { class: "dl" },
      h("dt", {}, "Back within"), h("dd", {}, hours(now.recovery_hours)),
      h("dt", {}, "Loses at most"), h("dd", {}, `${hours(now.data_loss_hours)} of information`),
      h("dt", {}, "Rests on"), h("dd", {}, now.basis),
      h("dt", {}, "Said"), h("dd", {}, `${date(now.recorded_at)} by ${now.recorded_by}`))
      : h("p", { class: "muted" }, "Nobody has said yet what it can be restored within. Every process that relies on it counts that as a shortfall.")),
    card({ title: "Processes that rely on it", flush: data.needed_by.length > 0 }, data.needed_by.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Process"), h("th", { scope: "col" }, "Needs it back within"), h("th", { scope: "col" }, "Can lose at most"))),
      h("tbody", {}, data.needed_by.map((p) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/processes/${p.ref}?tab=impact` }, p.name), h("div", { class: "cell-sub" }, p.ref)),
        h("td", {}, p.recovery_hours == null ? h("span", { class: "subtle" }, "Not analysed") : hours(p.recovery_hours)),
        h("td", {}, p.data_loss_hours == null ? "" : hours(p.data_loss_hours)))))))
      : h("p", { class: "muted" }, "No process in use relies on it.")));
}

/** The record page's tab: a process's business impact, or what a system or service delivers. */
export function resilienceTab(type, record, data, reload) {
  return type === "process" ? impactTab(record, data, reload) : recoveryTab(type, record, data, reload);
}
