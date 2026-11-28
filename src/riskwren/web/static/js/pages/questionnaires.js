// Questionnaires: the documents of questions RiskWren asks, each kept in versions. Anyone can
// read one and try it; those who run the program change them.

import { get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, titleCase } from "../core/format.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { banner, field, select, submit } from "../components/form.js";
import { openOverlay, closeOverlay } from "../components/overlay.js";
import { asAsked, questionnaireForm, ruleInWords } from "../components/questionnaire.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { tabBar } from "./record.js";

const PURPOSES = { attestation: "Attestation", self_assessment: "Self-assessment", completeness: "Completeness check",
  due_diligence: "Due diligence", review: "Review", privacy_impact: "Privacy impact", tiering: "Tiering", other: "Other" };
const TYPES = { yes_no: "Yes or no", choice: "One of a list", choices: "Any of a list", text: "A line of text",
  long_text: "A paragraph", number: "A number", date: "A date" };
const STARTER = { sections: [{ key: "first", title: "First section", questions: [{ key: "question_1", label: "", type: "yes_no", required: true }] }] };

export function questionnaireList(main) {
  return show(main, {
    title: "Questionnaires",
    load: async () => (await get("/api/v1/questionnaires", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Admin", title: "Questionnaires",
        lede: "The questions RiskWren asks people: to attest, to assess their own risks, to check a unit's records. Each is kept in versions, and an answer is always read against the version it was given to.",
        actions: can("configure") ? button("Add a questionnaire", { kind: "btn-primary", iconName: "plus", onclick: () => addOne() }) : null }),
      data.questionnaires.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Questionnaire"), h("th", { scope: "col" }, "For"),
          h("th", { scope: "col" }, "Version"), h("th", { scope: "col" }, "From"))),
        h("tbody", {}, data.questionnaires.map((item) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/questionnaires/${item.key}` }, item.title),
            item.status === "retired" ? [" ", pill("Retired")] : null,
            item.summary ? h("div", { class: "subtle" }, item.summary) : null),
          h("td", {}, PURPOSES[item.purpose] ?? titleCase(item.purpose)),
          h("td", {}, String(item.current_version)),
          h("td", {}, item.origin === "pack" ? "Built in" : "Your own")))))))
        : card({}, emptyState({ iconName: "file", title: "No questionnaires yet", text: "Add one to ask people something by a date." }))),
  });
}

function addOne() {
  openOverlay({ title: "Add a questionnaire", render: (body) => {
    const title = field("Title", { required: true });
    const key = field("Short name", { hint: "Lower-case letters, digits, and hyphens. It is used in addresses and cannot be changed.", required: true });
    title.input.addEventListener("input", () => {
      if (!key.input.dataset.typed) key.input.value = title.input.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
    });
    key.input.addEventListener("input", () => { key.input.dataset.typed = "1"; });
    const purpose = select("What it is for", Object.entries(PURPOSES), { value: "other" });
    const summary = field("What it asks, in a sentence", { type: "textarea", rows: 2 });
    const problem = banner();
    const save = button("Add, then write its questions", { kind: "btn-primary", type: "submit" });
    body.append(h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
      event.preventDefault();
      const starter = structuredClone(STARTER);
      starter.sections[0].questions[0].label = "The first question";
      const done = await submit({ button: save, fields: { title, key, purpose, summary }, banner: problem,
        run: () => post("/api/v1/questionnaires", { title: title.input.value, key: key.input.value, purpose: purpose.input.value,
          summary: summary.input.value || null, document: starter }) });
      if (done) {
        closeOverlay();
        navigate(`/questionnaires/${done.data.key}?tab=edit`);
      }
    } }, problem, title.node, key.node, purpose.node, summary.node, h("div", {}, save)));
  } });
}

function outline(document) {
  return h("div", { class: "stack-lg" }, document.sections.map((section) => h("section", { class: "stack" },
    h("h3", {}, section.title),
    section.show_when ? h("p", { class: "muted" }, `Asked only when ${ruleInWords(section.show_when, document)}.`) : null,
    h("ol", { class: "outline" }, section.questions.map((question) => h("li", {},
      question.label, question.required ? h("span", { class: "subtle" }, " (required)") : null,
      h("span", { class: "rule" }, TYPES[question.type] ?? question.type,
        question.options?.length ? `: ${question.options.map((option) => option.label).join(", ")}` : "",
        question.show_when ? `. Asked only when ${ruleInWords(question.show_when, document)}` : "")))))));
}

function tryIt(item) {
  const result = h("div", { class: "stack", "aria-live": "polite" });
  const form = questionnaireForm(item.document, {}, { onChange: () => result.replaceChildren() });
  const check = button("See how these answers would read", { kind: "btn-primary", onclick: () => {
    const answers = form.answers();
    const keys = new Set(Object.keys(answers));
    const missing = form.missing();
    form.setErrors(missing);
    if (Object.keys(missing).length) return;
    const said = (question, value) => (question.type === "yes_no" ? (value ? "Yes" : "No")
      : question.type === "choice" ? question.options.find((option) => option.key === value)?.label
        : question.type === "choices" ? value.map((each) => question.options.find((option) => option.key === each)?.label) : value);
    const sections = item.document.sections.map((section) => ({ title: section.title,
      questions: section.questions.filter((question) => keys.has(question.key)).map((question) => ({ label: question.label, said: said(question, answers[question.key]) })) }))
      .filter((section) => section.questions.length);
    result.replaceChildren(alert("info", icon("info"), h("div", {}, "Nothing was saved. This is how the answers would be kept and read.")), asAsked(sections));
  } });
  return card({ title: "Try it", footer: h("div", { class: "row" }, check, h("span", { class: "subtle" }, "Questions appear and go as you answer. Nothing here is saved.")) },
    h("div", { class: "stack-lg" }, form.node, result));
}

function versions(item) {
  return card({ title: "Versions", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Version"), h("th", { scope: "col" }, "Published"), h("th", { scope: "col" }, "By"), h("th", { scope: "col" }, "What changed"))),
    h("tbody", {}, item.versions.map((version) => h("tr", {},
      h("td", {}, h("a", { class: "cell-main", href: `/questionnaires/${item.key}?tab=questions&version=${version.number}` }, `Version ${version.number}`),
        version.current ? [" ", pill("In use", "ok")] : null),
      h("td", {}, date(version.published_at)), h("td", {}, version.published_by), h("td", {}, version.note ?? "")))))));
}

export function questionnairePage(main, params) {
  const editable = can("configure");
  const tabs = [["try", "Try it"], ["questions", "Questions"], ["versions", "Versions"], ...(editable ? [["edit", "Edit"]] : [])];
  const wanted = query().get("tab");
  const tab = tabs.some(([key]) => key === wanted) ? wanted : "try";
  const version = Number(query().get("version")) || null;
  return show(main, {
    title: "Questionnaire",
    load: async () => (await get(`/api/v1/questionnaires/${params.key}`, version && tab === "questions" ? { version } : null, { fresh: true })).data,
    view: (item, reload) => h("div", { class: "stack-lg" },
      h("a", { class: "back-link", href: "/questionnaires" }, icon("chevron-left", "icon icon-sm"), "Questionnaires"),
      pageHeader({ eyebrow: `${PURPOSES[item.purpose] ?? "Questionnaire"} · version ${item.current_version}`, title: item.title, lede: item.summary,
        actions: h("div", { class: "row-sm wrap" }, item.status === "retired" ? pill("Retired") : null, pill(item.origin === "pack" ? "Built in" : "Your own"),
          editable ? button(item.status === "retired" ? "Bring it back" : "Retire", { kind: "btn-sm btn-ghost", onclick: async () => {
            const retiring = item.status !== "retired";
            if (retiring && !window.confirm(`Retire ${item.title}? It can no longer be asked in a new review; answers already given are kept.`)) return;
            await patch(`/api/v1/questionnaires/${item.key}`, { status: retiring ? "retired" : "active" });
            toast(retiring ? "It is retired." : "It is in use again.");
            reload();
          } }) : null) }),
      tabBar(tabs, tab),
      tab === "questions" ? card({ title: item.version === item.current_version ? "What it asks" : `What version ${item.version} asked` },
        h("div", { class: "stack-lg" },
          item.version === item.current_version ? null : alert("info", icon("info"), h("div", {}, "This is an earlier version. Answers given to it are read against these questions.")),
          outline(item.document)))
        : tab === "versions" ? versions(item)
          : tab === "edit" ? editTab(item, reload)
            : tryIt(item)),
  });
}

function editTab(item, reload) {
  const holder = h("div", {}, h("p", { class: "muted" }, "Loading the editor…"));
  import("./questionnaire-editor.js").then(({ editor }) => holder.replaceChildren(editor(item, async (changes) => {
    const done = await patch(`/api/v1/questionnaires/${item.key}`, changes);
    toast(done.data.current_version === item.current_version ? "Saved." : `Published as version ${done.data.current_version}.`);
    reload();
  })));
  return holder;
}
