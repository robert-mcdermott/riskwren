// Reports → Continuity plans: every plan in use, what each restores, whom to call, its
// exercises and their findings, and a copy that prints, or downloads as one file, for when
// the systems are down. A plan's words, versions, and approval are its document's.

import { get, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { options, units, vocabularies } from "../core/lookups.js";
import { session } from "../core/session.js";
import { documentText } from "../components/document.js";
import { banner, field, section, select, submit } from "../components/form.js";
import { recordPicker, severityPill } from "../components/issue.js";
import { openOverlay } from "../components/overlay.js";
import { personField } from "../components/people-picker.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const RESULT = { met: "ok", partly: "warn", not_met: "danger" };
const hours = (value) => (value == null ? "Not analysed" : plural(value, "hour"));

function due(row) {
  return h("span", {}, row.exercise_overdue ? pill("Overdue", "danger") : null, row.exercise_overdue ? " " : null, date(row.next_exercise_on));
}

export function continuityList(main) {
  return show(main, {
    title: "Continuity plans",
    load: async () => {
      const [data, unitIndex] = await Promise.all([get("/api/v1/continuity", null, { fresh: true }), units()]);
      return { ...data.data, units: unitIndex };
    },
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Reports", title: "Continuity plans",
        lede: "What to do to keep each critical process going, or to bring it back: written, approved, and reviewed as documents are, exercised, and kept to hand for when the systems are down.",
        actions: data.can_add ? h("a", { class: "btn btn-primary", href: "/documents" }, "Write a plan") : null }),
      card({ title: plural(data.plans.length, "plan"), flush: data.plans.length > 0 }, data.plans.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Plan"), h("th", { scope: "col" }, "Restores"), h("th", { scope: "col" }, "In force"),
          h("th", { scope: "col" }, "Last exercised"), h("th", { scope: "col" }, "Next exercise"))),
        h("tbody", {}, data.plans.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/continuity/${row.ref}` }, row.name),
            h("div", { class: "cell-sub" }, [row.ref, data.units.byId.get(row.org_unit_id)?.name].filter(Boolean).join(" · "))),
          h("td", {}, plural(row.processes, "process", "processes")),
          h("td", {}, row.version ? `Version ${row.version}` : h("span", { class: "subtle" }, "Not yet published")),
          h("td", {}, row.last_exercised ? date(row.last_exercised) : h("span", { class: "subtle" }, "Never")),
          h("td", {}, due(row)))))))
        : emptyState({ iconName: "document", title: "No continuity plans yet", text: "A plan is written as a document of the kind Continuity plan, then said to restore the processes it covers." })),
      card({ title: "Processes no plan restores" }, data.uncovered.length
        ? h("ul", { class: "plain-list stack-sm" }, data.uncovered.map((item) => h("li", {}, recordChip(item), h("span", { class: "subtle" }, ` must be back within ${hours(item.recovery_hours)}`))))
        : h("p", { class: "muted" }, "Every process with a business impact analysis is restored by a plan."))),
  });
}

function coversForm(plan, reload) {
  openOverlay({ title: "What it restores", subtitle: "The processes this plan keeps going, or brings back.", render: (body, footer, close) => {
    const chosen = plan.covers.map((each) => ({ ...each, type: "process" }));
    const picker = recordPicker({ types: ["process"], chosen, label: "Add a process", placeholder: "Search processes", empty: "None yet." });
    const problem = banner();
    const save = button("Save", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/continuity/${plan.ref}/covers`, { processes: chosen.map((each) => each.ref) }) });
      if (!done) return;
      close();
      toast("Saved.");
      reload();
    });
    body.append(h("div", { class: "stack" }, problem, picker));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function exerciseForm(plan, reload) {
  openOverlay({ title: "Record an exercise", subtitle: "What was tried, what happened, and whether the recovery objectives were met.", render: (body, footer, close) => {
    const kind = select("Kind of exercise", Object.entries(plan.choices.kinds), { value: "tabletop" });
    const held = field("Held on", { type: "date", required: true, max: new Date().toISOString().slice(0, 10) });
    const scenario = field("What was tried", { type: "textarea", rows: 3, required: true, hint: "The scenario the plan was put to." });
    const participants = field("Who took part", { type: "textarea", rows: 2 });
    const outcome = field("What happened", { type: "textarea", rows: 4, required: true });
    const result = select("Its recovery objectives", Object.entries(plan.choices.results), { value: "met" });
    const achieved = field("How long recovery took, in hours", { type: "number", min: 0, hint: "Where it was timed." });
    const problem = banner();
    const save = button("Record it", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { kind, held_on: held, scenario, participants, outcome, result, achieved_hours: achieved },
        run: () => post(`/api/v1/continuity/${plan.ref}/exercises`, { kind: kind.input.value, held_on: held.input.value, scenario: scenario.input.value,
          participants: participants.input.value || null, outcome: outcome.input.value, result: result.input.value,
          achieved_hours: achieved.input.value === "" ? null : Number(achieved.input.value) }) });
      if (!done) return;
      close();
      toast("Recorded.");
      reload();
    });
    body.append(h("div", { class: "stack" }, problem, h("div", { class: "grid-2" }, kind.node, held.node), scenario.node, participants.node, outcome.node, h("div", { class: "grid-2" }, result.node, achieved.node)));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function findingForm(plan, exercise, vocab, reload) {
  openOverlay({ title: "Raise a finding", subtitle: "Something the exercise showed must be put right: an issue, with the exercise as its source.", render: (body, footer, close) => {
    const name = field("What is wrong", { required: true, maxlength: 200 });
    const summary = field("What the exercise showed", { type: "textarea", rows: 3 });
    const severity = select("Severity", options(vocab, "issue_severities", { blank: "Choose…" }), { required: true });
    const me = session()?.account;
    const owner = personField("Who puts it right", { value: me ? { account_id: me.id, name: me.name } : null });
    const problem = banner();
    const save = button("Raise it", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { name, summary, severity, owner_id: owner },
        run: () => post(`/api/v1/continuity/${plan.ref}/exercises/${exercise.id}/issues`, { name: name.input.value, summary: summary.input.value || null,
          severity: severity.input.value || null, owner_id: owner.value() }) });
      if (!done) return;
      close();
      toast("Raised.");
      reload();
    });
    body.append(h("div", { class: "stack" }, problem, name.node, summary.node, severity.node, owner.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function words(version) {
  if (!version) return alert("warn", "No version is published yet. Publish one from its document; until then there is nothing to print.");
  if (version.form === "link") return h("p", {}, "The plan's words are kept at ", h("a", { href: version.url, rel: "noopener noreferrer", target: "_blank" }, version.url), ".");
  if (version.form === "file") return h("p", {}, `The plan's words are in the file ${version.file_name}, on its document.`);
  return documentText(version.body, { shift: 1, withContents: false });
}

export function continuityPlan(main, params) {
  return show(main, {
    title: params.ref,
    load: async () => {
      const [plan, vocab] = await Promise.all([get(`/api/v1/continuity/${params.ref}`, null, { fresh: true }), vocabularies()]);
      return { plan: plan.data, vocab };
    },
    view: (data, reload) => {
      const plan = data.plan;
      document.title = `${plan.name} · ${plan.ref}`;
      const can = plan.can;
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: "/continuity" }, icon("chevron-left", "icon icon-sm"), "Continuity plans"),
        pageHeader({ eyebrow: `Continuity plan · ${plan.ref}${plan.version ? ` · version ${plan.version.number}` : ""}`, title: plan.name, lede: plan.summary,
          actions: h("div", { class: "row wrap no-print" },
            plan.version ? button("Print", { iconName: "file", onclick: () => window.print() }) : null,
            plan.version ? h("a", { class: "btn", href: `/api/v1/continuity/${plan.ref}/offline`, download: "" }, "Download for offline use") : null,
            h("a", { class: "btn btn-ghost", href: `/documents/${plan.ref}` }, "Its document")) }),
        plan.version ? h("p", { class: "subtle" }, `Keep a printed or downloaded copy where it can be reached when the systems are down. Exercised every ${plan.exercise_months} months; next by ${date(plan.next_exercise_on)}.`) : null,
        card({ title: "The plan" }, words(plan.version)),
        card({ title: "What it restores, soonest first", actions: can.change ? button("Change", { kind: "btn-sm no-print", onclick: () => coversForm(plan, reload) }) : null, flush: plan.covers.length > 0 },
          plan.covers.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Process"), h("th", { scope: "col" }, "Back within"), h("th", { scope: "col" }, "Can lose"), h("th", { scope: "col" }, "What it relies on"))),
            h("tbody", {}, plan.covers.map((item) => h("tr", {},
              h("td", {}, h("a", { class: "cell-main", href: `/processes/${item.ref}?tab=impact` }, item.name), item.minimum ? h("div", { class: "cell-sub" }, `Needs at least: ${item.minimum}`) : null),
              h("td", {}, hours(item.recovery_hours)), h("td", {}, hours(item.data_loss_hours)),
              h("td", {}, item.dependencies.length ? h("ul", { class: "plain-list" }, item.dependencies.map((dep) => h("li", {},
                h("span", { class: "cell-main" }, dep.name), " ", dep.problems.length ? pill("Short", "danger") : pill("In time", "ok"),
                dep.problems.length ? h("div", { class: "cell-sub" }, dep.problems.join(" ")) : null))) : h("span", { class: "subtle" }, "Nothing recorded")))))))
            : h("p", { class: "muted" }, "No process is named yet. Say which processes this plan restores.")),
        card({ title: "Whom to call", flush: plan.contacts.length > 0 }, plan.contacts.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Name"), h("th", { scope: "col" }, "Email"), h("th", { scope: "col" }, "For"))),
          h("tbody", {}, plan.contacts.map((person) => h("tr", {},
            h("td", {}, h("div", { class: "cell-main" }, person.name), person.title ? h("div", { class: "cell-sub" }, person.title) : null),
            h("td", {}, person.email), h("td", {}, person.for.join(", ")))))))
          : h("p", { class: "muted" }, "Nobody is named.")),
        card({ title: "Exercises", actions: can.exercise ? button("Record an exercise", { kind: "btn-sm no-print", onclick: () => exerciseForm(plan, reload) }) : null },
          plan.exercises.length ? h("ol", { class: "plain-list stack messages" }, plan.exercises.map((exercise) => h("li", { class: "stack-sm" },
            h("div", { class: "row wrap" }, h("span", { class: "cell-main" }, `${exercise.kind_label}, ${date(exercise.held_on)}`), pill(exercise.result_label, RESULT[exercise.result]),
              h("span", { class: "subtle" }, [exercise.version ? `version ${exercise.version}` : null, exercise.achieved_hours != null ? `recovered in ${plural(exercise.achieved_hours, "hour")}` : null].filter(Boolean).join(" · "))),
            h("p", {}, h("strong", {}, "Tried: "), exercise.scenario),
            h("p", {}, h("strong", {}, "What happened: "), exercise.outcome),
            exercise.participants ? h("p", { class: "subtle" }, `Took part: ${exercise.participants}`) : null,
            exercise.findings.length ? h("ul", { class: "plain-list stack-sm" }, exercise.findings.map((issue) => h("li", { class: "row wrap" },
              h("a", { href: `/issues/${issue.ref}` }, `${issue.ref} ${issue.name}`), severityPill(issue.severity)))) : null,
            can.exercise ? h("div", { class: "no-print" }, button("Raise a finding", { kind: "btn-ghost btn-sm", onclick: () => findingForm(plan, exercise, data.vocab, reload) })) : null)))
            : h("p", { class: "muted" }, `Not exercised yet. Try it out, on a table or for real, by ${date(plan.next_exercise_on)}.`)));
    },
  });
}
