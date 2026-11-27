// Assessments: the list, and one assessment with the tests planned in it, what each found,
// and whether a second person has confirmed it.

import { listTools } from "../components/tidy.js";
import { del, get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural, relative } from "../core/format.js";
import { units, unitOptions, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { can, session } from "../core/session.js";
import { STATUS, statusPill } from "../components/assessment.js";
import { segments } from "../components/charts.js";
import { statePill } from "../components/control.js";
import { freshness } from "../components/evidence.js";
import { banner, field, select, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { personField } from "../components/people-picker.js";
import { recordChip, TYPES } from "../components/record.js";
import { section } from "../components/record-forms.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { exportButton } from "../components/exchange.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, pager, searchBox, sortHeader } from "./records.js";

const TABS = [["tests", "Tests"], ["about", "About"], ["history", "History"]];
const TEST_STATES = { todo: ["To do", ""], awaiting: ["Awaiting review", "info"], returned: ["Returned", "warn"], counted: ["Counted", "ok"] };
const METHODS = [["examine", "Examine: look at records and settings"], ["interview", "Interview: ask the people who do it"], ["test", "Test: try it and see"]];
const METHOD_WORDS = { examine: "Examine", interview: "Interview", test: "Test" };
const FOUND = [["effective", "Effective"], ["partly", "Partly effective"], ["ineffective", "Ineffective"]];

const testPill = (state) => pill(TEST_STATES[state][0], TEST_STATES[state][1]);
const period = (item) => (item.period_start || item.period_end
  ? [item.period_start ? date(item.period_start) : "the start", item.period_end ? date(item.period_end) : "no end set"].join(" to ") : null);

/** How far an assessment has got: counted, awaiting a second person, and still to do. */
export function progress(item) {
  const todo = item.tests - item.counted - item.awaiting;
  return segments([
    { label: "counted", value: item.counted, tone: "ok" },
    { label: "awaiting review", value: item.awaiting, tone: "info" },
    { label: "to do", value: todo, tone: "none" },
  ], { label: `${item.counted} of ${plural(item.tests, "test")} counted` });
}

// ---- Forms ----

/** Start an assessment of a scope, or change the plan of one that exists. */
export function editAssessment({ assessment = null, scope = null, onDone = null }) {
  openOverlay({
    title: assessment ? "Edit the assessment" : "Start an assessment",
    subtitle: assessment ? `${assessment.ref} · ${assessment.name}` : "A set of tests of the controls a scope does itself.",
    render: async (body, footer, close) => {
      const scopes = assessment || scope ? [] : (await get("/api/v1/scopes", { status: "active", sort: "name", limit: 100 }, { fresh: true })).data;
      if (!assessment && !scope && !scopes.length) {
        body.append(emptyState({ iconName: "scope", title: "No scope to assess", text: "An assessment is of a scope. Add a scope and the controls it uses first." }));
        return;
      }
      const year = new Date().getFullYear();
      const name = field("Name", { value: assessment?.name ?? "", required: true, maxlength: 400, hint: assessment ? null : `For example: Annual security assessment ${year}.` });
      const which = assessment || scope ? null : select("Scope", [["", "Choose…"], ...scopes.map((item) => [item.ref, `${item.name} (${plural(item.controls, "control")})`])], { required: true });
      const against = assessment ? null : select("Against", [["", "Every control the scope does itself"]], { hint: "With a framework, only the controls that answer a requirement of it that applies in the scope." });
      const drawFrameworks = () => {
        const held = scope ? scope.held_to : scopes.find((item) => item.ref === which.input.value)?.frameworks ?? [];
        against.input.replaceChildren(h("option", { value: "" }, "Every control the scope does itself"), ...held.map((item) => h("option", { value: item.key }, item.title)));
      };
      if (against) {
        which?.input.addEventListener("change", drawFrameworks);
        drawFrameworks();
      }
      const from = field("Period from", { type: "date", value: assessment?.period_start ?? "" });
      const to = field("Period to", { type: "date", value: assessment?.period_end ?? "", hint: "Tests that are assigned show as due on this date." });
      const me = session().account;
      const lead = personField("Lead", { value: assessment ? (assessment.lead ? { account_id: assessment.lead.id, name: assessment.lead.name } : null) : { account_id: me.id, name: me.name },
        hint: "Results that wait for review appear on the lead's Home." });
      const approach = field("Approach", { type: "textarea", rows: 3, value: assessment?.approach ?? "", hint: "How it will be carried out, and anything it will not cover." });
      const problem = banner();
      const saveButton = button(assessment ? "Save" : "Start", { kind: "btn-primary" });
      const save = async () => {
        const values = { name: name.input.value, period_start: from.input.value || null, period_end: to.input.value || null, lead_id: lead.value(), approach: approach.input.value };
        const fields = { name, period_start: from, period_end: to, lead_id: lead, approach, ...(which ? { scope: which } : {}), ...(against ? { framework: against } : {}) };
        const done = await submit({ button: saveButton, fields, banner: problem,
          run: () => (assessment ? patch(`/api/v1/assessments/${assessment.ref}`, { version: assessment.version, ...values })
            : post("/api/v1/assessments", { ...values, scope: scope?.ref ?? which.input.value, framework: against.input.value || null })) });
        if (!done) return;
        close();
        toast(assessment ? "Saved." : `${done.data.ref} was started, with ${plural(done.data.tests, "test")} planned.`);
        if (onDone) onDone(done.data);
        else navigate(`/assessments/${done.data.ref}`);
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem,
      section("What is assessed", name.node, which?.node ?? null, against?.node ?? null,
        assessment ? null : h("p", { class: "subtle" }, "A test is planned for each control. What a scope inherits is tested where it is provided, and counts here once it has been.")),
      section("When, and who leads it", h("div", { class: "grid-2" }, from.node, to.node), lead.node, approach.node)));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** How a control is to be tested, and by whom. */
function planTest(test, reload) {
  openOverlay({
    title: "Plan this test",
    subtitle: `${test.control.ref} · ${test.control.name}`,
    render: (body, footer, close) => {
      const method = select("Method", METHODS, { value: test.method });
      const procedure = field("What to do", { type: "textarea", rows: 5, value: test.procedure ?? "", hint: "The steps, and what would show that the control works." });
      const who = personField("Assigned to", { value: test.assigned_to ? { account_id: test.assigned_to.id, name: test.assigned_to.name } : null,
        hint: "It appears on their Home. Nobody tests a control they own." });
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { method, procedure, assigned_to: who }, banner: problem,
          run: () => patch(`/api/v1/tests/${test.id}`, { method: method.input.value, procedure: procedure.input.value, assigned_to: who.value() }) });
        if (done) {
          close();
          toast("Saved.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, h("p", { class: "prose muted" }, test.control.statement), method.node, procedure.node, who.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Record what a test found. It counts once someone else has confirmed it. */
function recordResult(test, reload) {
  const cited = (test.state === "returned" ? test.result?.evidence ?? [] : []).map((item) => ({ ...item }));
  openOverlay({
    title: "Record the result",
    subtitle: `${test.control.ref} · ${test.control.name}`,
    render: (body, footer, close) => {
      const was = test.state === "returned" ? test.result : null;
      const design = select("Design", [["", "Choose…"], ...FOUND], { value: was?.design ?? "", required: true, hint: "Would it reduce the risk, if it operated as described?" });
      const operation = select("Operation", [["", "Choose…"], ...FOUND], { value: was?.operation ?? "", required: true, hint: "Does it operate as described?" });
      const sample = field("What was looked at", { type: "textarea", rows: 2, value: was?.sample ?? "", hint: "The sample, the period, the people asked." });
      const note = field("What was found", { type: "textarea", rows: 4, value: was?.note ?? "", required: true });
      const list = h("div", { class: "stack-sm" });
      const search = h("input", { class: "input", type: "search", placeholder: "Find evidence by name", "aria-label": "Find evidence to cite" });
      const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Evidence found" });
      const evidenceError = h("div", { class: "error", role: "alert", hidden: true });
      const draw = () => {
        list.replaceChildren(...(cited.length ? cited.map((item, index) => h("div", { class: "owner-row" },
          h("div", { class: "grow" }, recordChip({ ...item, type: "evidence" }, { link: false })),
          button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${item.name}`, onclick: () => {
            cited.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "None cited. A requirement is verified only while evidence for the control still counts.")]));
      };
      let latest = 0;
      let timer = null;
      const look = async () => {
        const mine = ++latest;
        const words = search.value.trim();
        if (words.length < 2) {
          results.replaceChildren();
          return;
        }
        const page = await get("/api/v1/evidence", { q: words, sort: "name", limit: 6, status: "active" }, { fresh: true });
        if (mine !== latest) return;
        const offered = page.data.filter((item) => !cited.some((c) => c.ref === item.ref));
        results.replaceChildren(...(offered.length ? offered.map((item) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
          cited.push(item);
          search.value = "";
          results.replaceChildren();
          draw();
        } }, icon("evidence"), h("span", {}, h("span", { class: "cell-main" }, item.name), h("span", { class: "cell-sub" }, ` ${item.ref}`))))
          : [h("div", { class: "subtle pick-none" }, "Nothing matches. Add it under Evidence first.")]));
      };
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(look, 180);
      });
      draw();
      const problem = banner();
      const save = button("Record the result", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        evidenceError.hidden = true;
        const fields = { design, operation, sample, note, evidence: { input: search, setError: (message) => {
          evidenceError.hidden = !message;
          evidenceError.textContent = message ?? "";
        } } };
        const done = await submit({ button: save, fields, banner: problem,
          run: () => post(`/api/v1/tests/${test.id}/results`, { design: design.input.value, operation: operation.input.value, sample: sample.input.value || null,
            note: note.input.value, evidence: cited.map((item) => item.ref) }) });
        if (done) {
          close();
          toast("Recorded. It counts once someone else has confirmed it.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        was?.review_note ? alert("warn", icon("alert"), h("div", {}, `Returned by ${was.reviewed_by}: ${was.review_note}`)) : null,
        section("The test", test.procedure ? prose(test.procedure) : h("p", { class: "prose muted" }, test.control.statement)),
        section("What it found", h("div", { class: "grid-2" }, design.node, operation.node),
          h("p", { class: "subtle" }, "The control is as strong as the weaker of the two."), sample.node, note.node),
        section("Evidence", list, h("div", { class: "field" }, h("div", { class: "label" }, "Cite evidence"), search, results, evidenceError))));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function resultBody(result) {
  return h("div", { class: "stack" },
    h("dl", { class: "dl" }, h("dt", {}, "Design"), h("dd", {}, statePill(result.design)), h("dt", {}, "Operation"), h("dd", {}, statePill(result.operation)),
      result.sample ? [h("dt", {}, "Looked at"), h("dd", {}, result.sample)] : null),
    prose(result.note),
    result.evidence.length ? h("div", { class: "stack-sm" }, result.evidence.map((item) => h("div", { class: "row-sm wrap" }, recordChip({ ...item, type: "evidence" }), freshness(item.state)))) : null,
    h("p", { class: "subtle" }, `Recorded by ${result.tested_by} on ${date(result.tested_at)}.`,
      result.review ? ` ${result.review === "confirmed" ? "Confirmed" : "Returned"} by ${result.reviewed_by} on ${date(result.reviewed_at)}${result.review_note ? `: ${result.review_note}` : "."}` : ""));
}

/** A second person confirms a result, and it counts; or returns it, saying what to look at again. */
function reviewResult(test, reload) {
  openOverlay({
    title: "Review this result",
    subtitle: `${test.control.ref} · ${test.control.name}`,
    render: (body, footer, close) => {
      const note = field("Note", { type: "textarea", rows: 3, hint: "Needed to return it: say what needs another look." });
      const problem = banner();
      const confirm = button("Confirm it", { kind: "btn-primary" });
      const back = button("Return it");
      const send = (agree, pressed) => async () => {
        const done = await submit({ button: pressed, fields: { note }, banner: problem,
          run: () => post(`/api/v1/results/${test.result.id}/review`, { confirm: agree, note: note.input.value || null }) });
        if (done) {
          close();
          toast(agree ? "Confirmed. The control's rating is now this result." : "Returned to be looked at again.");
          reload();
        }
      };
      confirm.addEventListener("click", send(true, confirm));
      back.addEventListener("click", send(false, back));
      body.append(h("div", { class: "stack-lg" }, problem, section("What was found", resultBody(test.result)),
        h("p", { class: "subtle" }, "Once confirmed, this becomes the control's rating. It then shows in every scope that relies on the control and every risk the control reduces."),
        note.node));
      footer.replaceChildren(h("div", { class: "row" }, confirm, back, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function showResult(test) {
  openOverlay({ title: "What the test found", subtitle: `${test.control.ref} · ${test.control.name}`, render: (body) => {
    body.append(h("div", { class: "stack-lg" }, test.procedure ? section("The test", prose(test.procedure)) : null, section("What was found", resultBody(test.result)),
      test.results > 1 ? h("p", { class: "subtle" }, `Recorded ${test.results} times; the earlier ones are in the history.`) : null));
  } });
}

/** A control the scope does itself that this assessment does not test yet. */
function addTest(assessment, reload) {
  openOverlay({
    title: "Add a control",
    subtitle: `Controls that ${assessment.scope.name} does itself.`,
    render: async (body, footer, close) => {
      const held = (await get(`/api/v1/scopes/${assessment.scope.ref}/controls`, null, { fresh: true })).data.controls;
      const planned = new Set(assessment.tests_list.map((test) => test.control.ref));
      const offered = held.filter((item) => item.inheritance === "none" && item.status !== "not_applicable" && !planned.has(item.control.ref));
      if (!offered.length) {
        body.append(emptyState({ iconName: "control", title: "Nothing to add", text: "Every control this scope does itself is already in the assessment. What it inherits is tested where it is provided." }));
        return;
      }
      const which = select("Control", offered.map((item) => [item.control.ref, `${item.control.name} · ${item.control.ref}`]));
      const problem = banner();
      const save = button("Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { control: which }, banner: problem, run: () => post(`/api/v1/assessments/${assessment.ref}/tests`, { control: which.input.value }) });
        if (done) {
          close();
          toast("Added.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, which.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

// ---- One assessment ----

function testsTab(assessment, reload) {
  const tests = assessment.tests_list;
  const add = assessment.can_run ? button("Add a control", { kind: "btn-sm", iconName: "plus", onclick: () => addTest(assessment, reload) }) : null;
  if (!tests.length) {
    return card({}, emptyState({ iconName: "control", title: "No tests planned",
      text: "This scope has no control of its own to test yet. Add the controls it uses on the scope, then add them here.", action: add }));
  }
  return h("div", { class: "stack-lg" },
    card({ title: "Progress" }, progress(assessment),
      assessment.failing ? h("p", { class: "muted" }, `${plural(assessment.failing, "control")} found not to work as described. Each shows as failing wherever it is relied on.`) : null),
    card({ title: plural(tests.length, "test"), actions: add, flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Control"), h("th", { scope: "col" }, "How"), h("th", { scope: "col" }, "Where it stands"), h("th", { scope: "col" }, "Found"),
        h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Actions")))),
      h("tbody", {}, tests.map((test) => {
        const result = test.result;
        return h("tr", {},
          h("td", {}, test.control.open ? h("a", { class: "cell-main", href: `/controls/${test.control.ref}` }, test.control.name) : h("span", { class: "cell-main" }, test.control.name),
            h("div", { class: "cell-sub" }, test.control.ref, test.can.owns ? " · yours, so someone else tests it" : "")),
          h("td", {}, METHOD_WORDS[test.method] ?? test.method,
            h("div", { class: "cell-sub" }, test.assigned_to ? test.assigned_to.name : "Nobody assigned")),
          h("td", {}, testPill(test.state),
            test.state === "returned" && result?.review_note ? h("div", { class: "cell-sub" }, result.review_note) : null),
          h("td", {}, result && test.state !== "returned" ? [statePill(result.outcome), h("div", { class: "cell-sub" }, `${result.tested_by}, ${date(result.tested_at)}`),
            test.issue ? h("div", { class: "cell-sub" }, "Issue ", h("a", { href: `/issues/${test.issue.ref}` }, test.issue.ref)) : null] : h("span", { class: "subtle" }, "Nothing yet")),
          h("td", { class: "nowrap" }, h("div", { class: "row-sm" },
            test.can.review ? button("Review", { kind: "btn-sm btn-primary", "aria-label": `Review the result for ${test.control.name}`, onclick: () => reviewResult(test, reload) }) : null,
            test.can.record ? button(test.state === "todo" ? "Record result" : "Record again", { kind: test.state === "todo" || test.state === "returned" ? "btn-sm btn-primary" : "btn-sm",
              "aria-label": `Record the result for ${test.control.name}`, onclick: () => recordResult(test, reload) }) : null,
            result ? button("See", { kind: "btn-sm btn-ghost", "aria-label": `See what was found for ${test.control.name}`, onclick: () => showResult(test) }) : null,
            test.can.plan && test.state !== "counted" ? button("Plan", { kind: "btn-sm btn-ghost", "aria-label": `Plan the test of ${test.control.name}`, onclick: () => planTest(test, reload) }) : null,
            test.can.plan && !result ? button("Remove", { kind: "btn-sm btn-ghost", "aria-label": `Remove ${test.control.name}`, onclick: () => confirmAction({
              title: `Take ${test.control.name} out of this assessment?`, text: "The control stays as it is. It can be added again.", confirmLabel: "Remove", danger: true,
              run: async () => {
                await del(`/api/v1/tests/${test.id}`);
                toast("Removed.");
                reload();
              } }) }) : null)));
      }))))));
}

function about(assessment, ctx) {
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      card({ title: "Approach" }, assessment.approach ? prose(assessment.approach) : h("p", { class: "muted" }, "Not written down yet.")),
      card({ title: "How a result comes to count" }, h("ol", { class: "prose steps" },
        h("li", {}, "Someone who does not own the control records what they found."),
        h("li", {}, "A second person, who also does not own it, confirms the result or returns it."),
        h("li", {}, "Once confirmed it becomes the control's rating: in every scope that relies on the control, and for every risk it reduces.")))),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Scope", assessment.scope ? h("a", { href: `/scopes/${assessment.scope.ref}` }, assessment.scope.name) : null],
        ["Against", assessment.framework ? h("a", { href: `/frameworks/${assessment.framework.key}` }, assessment.framework.title) : "Every control the scope does itself"],
        ["Period", period(assessment)],
        ["Lead", assessment.lead?.name],
        ["Unit", ctx.units.byId.get(assessment.org_unit_id)?.name],
        ["Completed", assessment.completed_at ? date(assessment.completed_at) : null],
      ])),
      ownersCard(assessment, ctx)));
}

function finish(assessment, reload) {
  const left = assessment.tests - assessment.counted;
  if (left) {
    toast(`${left} of its ${plural(assessment.tests, "test")} ${left === 1 ? "does" : "do"} not count yet. Finish them, or take them out.`);
    return;
  }
  confirmAction({ title: "Complete this assessment?", text: "Nothing more can be recorded in it. What it found stays on each control until a later test or the passing of time replaces it.", confirmLabel: "Complete",
    run: async () => {
      await post(`/api/v1/assessments/${assessment.ref}/completion`, {});
      toast("Completed.");
      reload();
    } });
}

export function assessmentPage(main, params) {
  const wanted = query().get("tab");
  const tab = TABS.some(([key]) => key === wanted) ? wanted : "tests";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/assessments/${params.ref}`;
      const [assessment, unitIndex, vocab, extra] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { assessment: { ...assessment.data, type: "assessment" }, units: unitIndex, vocab, extra: extra?.data ?? [] };
    },
    view: (data, reload) => {
      const assessment = data.assessment;
      document.title = `${assessment.name} · ${assessment.ref}`;
      const ctx = { units: data.units, vocab: data.vocab, reload };
      const actions = assessment.can_run ? h("div", { class: "row wrap" },
        button("Edit", { iconName: "edit", onclick: () => editAssessment({ assessment, onDone: reload }) }),
        button("Complete", { kind: "btn-primary", onclick: () => finish(assessment, reload) }),
        button("Cancel it", { kind: "btn-ghost", onclick: () => confirmAction({ title: "Cancel this assessment?",
          text: "Results already confirmed still count. Nothing more can be recorded in it.", confirmLabel: "Cancel the assessment", danger: true,
          run: async () => {
            await post(`/api/v1/assessments/${assessment.ref}/cancellation`, {});
            toast("Cancelled.");
            reload();
          } }) })) : null;
      return h("div", { class: "stack" },
        recordHeader(assessment, { badges: [statusPill(assessment.status), assessment.scope ? recordChip({ ...assessment.scope, type: "scope" }) : null], actions }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : tab === "about" ? about(assessment, ctx) : testsTab(assessment, reload));
    },
  });
}

// ---- The list ----

function assessmentRows(rows) {
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, sortHeader("Assessment", "name"), h("th", { scope: "col" }, "Scope"),
      h("th", { scope: "col" }, "Lead"), sortHeader("Period to", "period_end"), h("th", { scope: "col" }, "Tests"), sortHeader("Status", "status"))),
    h("tbody", {}, rows.map((r) => h("tr", {},
      h("td", {}, h("a", { class: "cell-main", href: `/assessments/${r.ref}` }, r.name),
        h("div", { class: "cell-sub" }, [r.ref, r.framework?.title].filter(Boolean).join(" · "))),
      h("td", {}, r.scope ? h("a", { href: `/scopes/${r.scope.ref}` }, r.scope.name) : ""),
      h("td", {}, r.lead?.name ?? h("span", { class: "subtle" }, "Nobody")),
      h("td", { class: "nowrap muted" }, r.period_end ? date(r.period_end) : ""),
      h("td", {}, r.tests ? [`${r.counted} of ${r.tests} counted`, h("div", { class: "cell-sub" }, [r.awaiting ? `${r.awaiting} awaiting review` : null, r.failing ? `${r.failing} failing` : null].filter(Boolean).join(" · "))]
        : h("span", { class: "subtle" }, "None planned")),
      h("td", {}, statusPill(r.status), h("div", { class: "cell-sub" }, `Updated ${relative(r.updated_at)}`)))))));
}

export function assessmentList(main) {
  const meta = TYPES.assessment;
  return show(main, {
    title: "Assessments",
    load: async () => {
      const [page, unitIndex] = await Promise.all([get("/api/v1/assessments", Object.fromEntries(query()), { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data) => {
      const rows = data.page.data;
      const mayAdd = can("assess");
      const add = () => editAssessment({});
      const search = searchBox("Search assessments");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search), listTools(),
        filterSelect("status", [["", "Any status"], ...Object.entries(STATUS).map(([key, [text]]) => [key, text])], "Status"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"), mineToggle());
      const body = rows.length ? assessmentRows(rows)
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "assessment", title: "No assessments yet", text: meta.lede, action: mayAdd ? button("Start an assessment", { kind: "btn-primary", onclick: add }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Compliance", title: "Assessments", lede: meta.lede, actions: [mayAdd ? button("Start an assessment", { kind: "btn-primary", iconName: "plus", onclick: add }) : null, exportButton("assessments")] }),
        bar,
        card({ title: plural(data.page.meta.total, "assessment"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
