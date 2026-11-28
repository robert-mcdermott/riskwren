// An incident's breach assessment: whether it must be notified, the clock from discovery,
// what each rule requires and by when, and each notification made.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime } from "../core/format.js";
import { label } from "../core/lookups.js";
import { banner, checkbox, field, section, select, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pill } from "../components/ui.js";
import { prose } from "./record.js";

const CONCLUSION = { undecided: ["Not yet decided", "warn"], notify: ["It must be notified", "danger"], no_notification: ["It need not be notified", "ok"] };
const LEVEL = { low: ["Low", "ok"], moderate: ["Moderate", "warn"], high: ["High", "danger"] };
const conclusionPill = (key) => pill(...(CONCLUSION[key] ?? [key, ""]));

function pad(number) {
  return String(number).padStart(2, "0");
}

/** One named rule (a state's law, a contract) as a row of fields. */
function namedRow(kind, item, rows, draw) {
  const name = field(kind === "state" ? "State" : "Contract or agreement", { value: item.name ?? "", maxlength: 60 });
  const days = field("Days allowed", { type: "number", min: 1, max: 365, value: item.days ?? "" });
  const hours = kind === "contract" ? field("Or hours", { type: "number", min: 1, max: 2000, value: item.hours ?? "" }) : null;
  const remove = button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${item.name || kind}`, onclick: () => {
    rows.splice(rows.indexOf(entry), 1);
    draw();
  } });
  const entry = { kind, node: h("div", { class: "row wrap" }, name.node, days.node, hours?.node, remove),
    value: () => ({ key: kind, name: name.input.value, days: days.input.value ? Number(days.input.value) : null, hours: hours?.input.value ? Number(hours.input.value) : null }) };
  return entry;
}

function assessForm(record, view, vocab, reload) {
  const prev = view.assessment;
  const choices = view.choices;
  openOverlay({ title: prev ? "Assess it again" : "Assess whether it must be notified",
    subtitle: "Each assessment is kept. A new one takes the place of the last, and the clock runs from when it was discovered.",
    render: (body, footer, close) => {
      const found = prev ? new Date(prev.discovered_at) : new Date();
      const day = field("Discovered on", { type: "date", required: true, max: new Date().toISOString().slice(0, 10),
        value: `${found.getFullYear()}-${pad(found.getMonth() + 1)}-${pad(found.getDate())}`,
        hint: "When it was known, or would have been known with reasonable care, to anyone working for the organization." });
      const at = field("At", { type: "time", value: `${pad(found.getHours())}:${pad(found.getMinutes())}` });
      const had = new Set(prev?.information ?? []);
      const kinds = (vocab.protected_information ?? []).filter((item) => !item.retired).map((item) => ({ key: item.key,
        box: checkbox(item.label, { checked: had.has(item.key), hint: item.description }) }));
      const people = field("About how many people it concerns", { type: "number", min: 0, value: prev?.people ?? "" });
      const most = field("The most of them living in any one state", { type: "number", min: 0, value: prev?.most_in_one_state ?? "",
        hint: "More than 500 in one state brings in the media, under HIPAA." });
      const secured = checkbox("It was secured", { checked: prev?.secured ?? false,
        hint: "Encrypted, or destroyed, so as to be unusable, unreadable, or indecipherable to anyone not allowed to see it." });
      const exception = select("An exception that applies", [["", "None"], ...choices.exceptions.map((each) => [each.key, each.label])], { value: prev?.exception ?? "" });
      const factors = choices.factors.map((factor) => ({ key: factor.key,
        level: select(factor.label, [["", "Not yet weighed"], ...choices.levels.map((key) => [key, LEVEL[key][0]])], { value: prev?.factors?.[factor.key]?.level ?? "", hint: factor.help }),
        note: field(`Why, for ${factor.label.toLowerCase()}`, { type: "textarea", rows: 2, value: prev?.factors?.[factor.key]?.note ?? "" }) }));
      const fixed = choices.regimes.filter((regime) => !regime.named).map((regime) => ({ key: regime.key,
        box: checkbox(`${regime.label}${regime.cite ? ` (${regime.cite})` : ""}`, { hint: regime.note,
          checked: prev ? prev.regimes.some((each) => each.key === regime.key) : regime.suggested_for.some((kind) => had.has(kind)) }) }));
      // On a first assessment, the rules that apply to the kinds of information ticked are
      // ticked with them, until the handler changes a rule's box themselves.
      if (!prev) {
        const touched = new Set();
        const suggest = () => {
          const chosen = new Set(kinds.filter((each) => each.box.input.checked).map((each) => each.key));
          for (const rule of fixed) {
            const regime = choices.regimes.find((each) => each.key === rule.key);
            if (!touched.has(rule.key)) rule.box.input.checked = regime.suggested_for.some((kind) => chosen.has(kind));
          }
        };
        for (const rule of fixed) rule.box.input.addEventListener("change", () => touched.add(rule.key));
        for (const kind of kinds) kind.box.input.addEventListener("change", suggest);
      }
      const named = [];
      const namedList = h("div", { class: "stack-sm" });
      const drawNamed = () => namedList.replaceChildren(...named.map((each) => each.node));
      for (const item of prev?.regimes ?? []) if (["state", "contract"].includes(item.key)) named.push(namedRow(item.key, item, named, drawNamed));
      drawNamed();
      const addState = button("Add a state's law", { kind: "btn-sm", onclick: () => {
        named.push(namedRow("state", {}, named, drawNamed));
        drawNamed();
      } });
      const addContract = button("Add a contract", { kind: "btn-sm", onclick: () => {
        named.push(namedRow("contract", {}, named, drawNamed));
        drawNamed();
      } });
      const conclusion = select("Conclusion", Object.entries(CONCLUSION).map(([key, [text]]) => [key, text]), { value: prev?.conclusion ?? "undecided" });
      const rationale = field("Why", { type: "textarea", rows: 4, value: prev?.rationale ?? "",
        hint: "Needed to conclude. It is what a regulator will ask about: the factors, and what they come to." });
      const problem = banner();
      const save = button("Save the assessment", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const moment = new Date(`${day.input.value}T${at.input.value || "09:00"}`);
        const values = {
          discovered_at: day.input.value && !Number.isNaN(moment.getTime()) ? moment.toISOString() : "",
          information: kinds.filter((each) => each.box.input.checked).map((each) => each.key),
          people: people.input.value === "" ? null : Number(people.input.value),
          most_in_one_state: most.input.value === "" ? null : Number(most.input.value),
          secured: secured.input.checked, exception: exception.input.value || null,
          factors: Object.fromEntries(factors.map((each) => [each.key, { level: each.level.input.value || null, note: each.note.input.value || null }])),
          regimes: [...fixed.filter((each) => each.box.input.checked).map((each) => ({ key: each.key })), ...named.map((each) => each.value())],
          conclusion: conclusion.input.value, rationale: rationale.input.value || null,
        };
        const done = await submit({ button: save, banner: problem,
          fields: { discovered_at: day, people, most_in_one_state: most, exception, conclusion, rationale },
          run: () => post(`/api/v1/incidents/${record.ref}/breach`, values) });
        if (!done) return;
        close();
        toast("Saved. The clock runs from when it was discovered.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("When and what", h("div", { class: "row wrap" }, day.node, at.node), h("fieldset", { class: "stack-sm" },
          h("legend", { class: "label" }, "The protected information involved"), kinds.map((each) => each.box.node)),
        h("div", { class: "grid-2" }, people.node, most.node)),
        section("Is it a breach?", secured.node, exception.node, ...factors.flatMap((each) => [each.level.node, each.note.node])),
        section("The rules that apply", fixed.map((each) => each.box.node), namedList, h("div", { class: "row wrap" }, addState, addContract),
          h("p", { class: "subtle" }, "States' laws differ in what they cover and how long they allow: check each one that applies.")),
        section("What follows", conclusion.node, rationale.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function notificationForm(record, view, reload) {
  openOverlay({ title: "Record a notification", subtitle: "One that has been made: to whom, under which rule, and when.",
    render: (body, footer, close) => {
      const seen = new Set();
      const options = view.obligations.filter((duty) => {
        const key = `${duty.regime}|${duty.duty}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }).map((duty) => [`${duty.regime}|${duty.duty}`, `${duty.regime_label}: ${duty.to}`]);
      const which = select("Under which rule, to whom", options, { required: true });
      const recipient = field("Who was notified", { required: true, maxlength: 200, hint: "Such as “The Secretary, through the breach portal” or “412 patients, by first-class mail”." });
      const sentOn = field("Sent on", { type: "date", required: true, max: new Date().toISOString().slice(0, 10), value: new Date().toISOString().slice(0, 10) });
      const count = field("How many people were told", { type: "number", min: 0 });
      const method = field("How", { maxlength: 200, hint: "Mail, email, the regulator's portal, a press release." });
      const reference = field("Its reference", { maxlength: 200, hint: "A case or submission number, if one was given." });
      const note = field("Anything else", { type: "textarea", rows: 3 });
      const problem = banner();
      const save = button("Record it", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const [regime, duty] = which.input.value.split("|");
        const done = await submit({ button: save, banner: problem, fields: { regime: which, recipient, sent_on: sentOn, count, method, reference },
          run: () => post(`/api/v1/incidents/${record.ref}/notifications`, { regime, duty, recipient: recipient.input.value, sent_on: sentOn.input.value,
            count: count.input.value === "" ? null : Number(count.input.value), method: method.input.value || null, reference: reference.input.value || null, note: note.input.value || null }) });
        if (!done) return;
        close();
        toast("Recorded.");
        reload();
      });
      body.append(h("div", { class: "stack" }, problem, which.node, recipient.node, h("div", { class: "grid-2" }, sentOn.node, count.node), method.node, reference.node, note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function dueCell(duty) {
  if (duty.done) return h("span", {}, pill("Done", "ok"), " ", h("span", { class: "subtle" }, date(duty.done_on)));
  if (!duty.due_at) return h("span", { class: "subtle" }, "As its rule says");
  const when = duty.within?.endsWith("hours") ? dateTime(duty.due_at) : date(duty.due_at);
  return h("span", {}, duty.overdue ? pill("Overdue", "danger") : null, duty.overdue ? " " : null, `By ${when}`);
}

export function breachTab(record, view, vocab, reload) {
  const assessment = view.assessment;
  const can = view.can_assess;
  if (!assessment) {
    return emptyState({ iconName: "alert", title: "Not assessed",
      text: "Whether it must be notified, and to whom, is worked out from when it was discovered, what was involved, and four factors. Assess it as soon as protected information may be involved: the clock runs from discovery.",
      action: can ? button("Assess it", { kind: "btn-primary", onclick: () => assessForm(record, view, vocab, reload) }) : null });
  }
  const regimes = view.choices.regimes;
  const factorRows = view.choices.factors.map((factor) => {
    const given = assessment.factors[factor.key];
    return h("tr", {}, h("th", { scope: "row" }, factor.label),
      h("td", {}, given ? pill(...LEVEL[given.level]) : h("span", { class: "subtle" }, "Not weighed")),
      h("td", {}, given?.note ?? ""));
  });
  const exception = view.choices.exceptions.find((each) => each.key === assessment.exception);
  return h("div", { class: "stack-lg" },
    card({ title: "What is due", actions: can ? button("Record a notification", { kind: "btn-sm", onclick: () => notificationForm(record, view, reload), disabled: !view.obligations.length }) : null, flush: view.obligations.length > 0 },
      view.obligations.length ? [
        assessment.conclusion === "undecided" ? h("p", { class: "card-body subtle" }, "Not yet decided: this is what would be due if it is a breach. The clock is running.") : null,
        h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("caption", { class: "sr-only" }, "Notifications due"),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "To"), h("th", { scope: "col" }, "Rule"), h("th", { scope: "col" }, "Within"), h("th", { scope: "col" }, "Due"))),
          h("tbody", {}, view.obligations.map((duty) => h("tr", {},
            h("td", {}, h("div", { class: "cell-main" }, duty.to), h("div", { class: "cell-sub" }, duty.regime_label)),
            h("td", {}, duty.rule), h("td", {}, duty.within ?? "—"), h("td", {}, dueCell(duty)))))))]
        : h("p", { class: "muted" }, assessment.conclusion === "no_notification" ? "Nothing: it was concluded that it need not be notified." : "Nothing: no rule that applies is named.")),
    card({ title: "The assessment", actions: can ? button("Assess it again", { kind: "btn-sm", onclick: () => assessForm(record, view, vocab, reload) }) : null },
      h("div", { class: "stack" },
        h("div", { class: "row wrap" }, conclusionPill(assessment.conclusion), h("span", { class: "subtle" }, `By ${assessment.assessed_by}, ${dateTime(assessment.assessed_at)}`)),
        view.suggestion ? alert("info", h("strong", {}, "What the factors point to. "), view.suggestion.text) : null,
        assessment.rationale ? prose(assessment.rationale) : null,
        h("dl", { class: "dl" },
          h("dt", {}, "Discovered"), h("dd", {}, dateTime(assessment.discovered_at)),
          h("dt", {}, "Protected information"), h("dd", {}, assessment.information.map((key) => label(vocab, "protected_information", key)).join(", ") || "None named"),
          h("dt", {}, "People it concerns"), h("dd", {}, assessment.people == null ? "Not known" : String(assessment.people)),
          assessment.most_in_one_state != null ? [h("dt", {}, "Most in one state"), h("dd", {}, String(assessment.most_in_one_state))] : null,
          h("dt", {}, "Secured"), h("dd", {}, assessment.secured ? "Yes" : "No"),
          h("dt", {}, "Exception"), h("dd", {}, exception?.label ?? "None"),
          h("dt", {}, "Rules"), h("dd", {}, assessment.regimes.map((item) => {
            const regime = regimes.find((each) => each.key === item.key);
            return item.name ? `${regime?.label ?? item.key}: ${item.name} (${item.hours ? `${item.hours} hours` : `${item.days} days`})` : regime?.label ?? item.key;
          }).join("; ") || "None")),
        h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("caption", {}, "The four factors"),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Factor"), h("th", { scope: "col" }, "Level"), h("th", { scope: "col" }, "Why"))),
          h("tbody", {}, factorRows))))),
    view.notifications.length ? card({ title: "Notifications made", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("caption", { class: "sr-only" }, "Notifications made"),
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Who"), h("th", { scope: "col" }, "Under"), h("th", { scope: "col" }, "Sent"), h("th", { scope: "col" }, "How"))),
      h("tbody", {}, view.notifications.map((row) => h("tr", {},
        h("td", {}, h("div", { class: "cell-main" }, row.recipient), row.count != null ? h("div", { class: "cell-sub" }, `${row.count} people`) : null),
        h("td", {}, row.regime_label), h("td", {}, date(row.sent_on), h("div", { class: "cell-sub" }, `Recorded by ${row.recorded_by}`)),
        h("td", {}, row.method ?? "", row.reference ? h("div", { class: "cell-sub mono" }, row.reference) : null))))))) : null,
    view.earlier.length ? card({ title: "Earlier assessments" }, h("ul", { class: "plain-list stack-sm" }, view.earlier.map((row) =>
      h("li", {}, conclusionPill(row.conclusion), " ", h("span", { class: "subtle" }, `${row.assessed_by}, ${dateTime(row.assessed_at)}`))))) : null);
}
