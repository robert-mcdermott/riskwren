// How a risk's rating, standing, and reasoning are shown everywhere.
// Rating says how much is at stake; standing says whether the risk is in order. Two signals,
// never one color.

import { button, h, icon } from "../core/dom.js";
import { date, dateTime } from "../core/format.js";
import { pill, ratingBadge } from "./ui.js";

/** A rating as a badge, by its key under the method in force. */
export function rating(program, key) {
  const found = program.method.ratings.find((item) => item.key === key);
  return found ? ratingBadge(found.ramp_level, found.label) : ratingBadge(0);
}

export function ratingOptions(program, blank) {
  return [["", blank], ...program.method.ratings.map((item) => [item.key, item.label])];
}

// Standing: a word, a mark, and a tone. Never a color alone.
export const STANDING = {
  within: ["Within appetite", "ok", "●"],
  accepted: ["Accepted", "ok", "◐"],
  treated: ["Being treated", "info", "◔"],
  needs_decision: ["Needs a decision", "danger", "!"],
  not_assessed: ["Not assessed", "", "○"],
  closed: ["Closed", "", "✕"],
};

export function standingPill(standing) {
  const [text, tone, mark] = STANDING[standing] ?? [standing, "", "○"];
  const node = pill("", tone);
  node.append(h("span", { "aria-hidden": "true" }, mark), text);
  return node;
}

export function standingOptions(blank) {
  return [["", blank], ...Object.entries(STANDING).map(([key, [text]]) => [key, text])];
}

/** What needs attention about a risk whatever its standing. */
export function flags(risk) {
  const out = [];
  if (risk.review_overdue) out.push(h("span", { class: "pill pill-warn" }, icon("alert", "icon icon-sm"), "Review overdue"));
  if (risk.residual_in_doubt) {
    out.push(h("span", { class: "pill pill-warn", title: risk.residual_doubt_reason ?? "" }, icon("alert", "icon icon-sm"), "Residual may be out of date"));
  }
  return out;
}

const KINDS = [["inherent", "Inherent", "Before controls"], ["residual", "Residual", "As things are"], ["target", "Target", "Where it should be"]];

/**
 * The journey: inherent, residual, and target side by side, each opening its reasoning.
 * onOpen(kind) is called when one is chosen.
 */
export function journey(program, risk, { onOpen = null } = {}) {
  const steps = KINDS.map(([kind, title, hint], index) => {
    const value = risk.ratings[kind];
    const body = [
      h("div", { class: "journey-title" }, title),
      rating(program, value.rating),
      h("div", { class: "cell-sub" }, value.rating ? `Likelihood ${value.likelihood} · Impact ${value.impact}` : hint),
    ];
    const step = onOpen && value.rating
      ? h("button", { type: "button", class: "journey-step", "aria-label": `${title} rating: show the reasoning`, onclick: () => onOpen(kind) }, body)
      : h("div", { class: "journey-step" }, body);
    return [index ? h("span", { class: "journey-arrow", "aria-hidden": "true" }, "→") : null, step];
  });
  return h("div", { class: "journey" }, steps);
}

const STATES = { effective: "Effective", partly: "Partly effective", ineffective: "Ineffective", not_assessed: "Not assessed", stale: "Rating out of date" };

/** What the controls suggested for a residual rating, with the arithmetic shown. */
export function suggestionView(program, suggested) {
  if (!suggested) return null;
  const axis = (name, title) => {
    const lines = suggested.controls.filter((c) => c.reduces === name || c.reduces === "both");
    const total = suggested.totals[name];
    return h("div", { class: "stack-sm" },
      h("div", { class: "label" }, `${title}: ${suggested.from[name]} → ${suggested[name]}`),
      lines.length ? h("table", { class: "table table-compact" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Control"), h("th", { scope: "col" }, "Relied on as"),
          h("th", { scope: "col" }, "Known to be"), h("th", { scope: "col", class: "numeric" }, "Counts"))),
        h("tbody", {}, lines.map((c) => h("tr", {},
          h("td", {}, c.name ?? c.ref ?? "A control"), h("td", {}, c.reliance === "primary" ? "Primary" : "Supporting"),
          h("td", {}, STATES[c.state] ?? c.state), h("td", { class: "numeric" }, `${c.strength} × ${c.weight} = ${c.counts}`)))),
        h("tfoot", {}, h("tr", {}, h("td", { colspan: "3" }, `Total ${total}: down ${suggested.steps[name]} ${suggested.steps[name] === 1 ? "level" : "levels"}`
          + (Math.floor(total + 1e-9) > suggested.limit ? ` (the limit is ${suggested.limit})` : "")), h("td", {}))))
        : h("p", { class: "muted" }, `No control is linked that reduces ${name}.`));
  };
  return h("div", { class: "stack" },
    h("div", { class: "row wrap" }, h("span", { class: "muted" }, "From"), rating(program, suggested.from.rating),
      h("span", { "aria-hidden": "true" }, "→"), h("span", { class: "muted" }, "the controls suggest"), rating(program, suggested.rating)),
    axis("likelihood", "Likelihood"), axis("impact", "Impact"),
    h("p", { class: "subtle" }, "A control that has not been assessed, or whose rating is out of date, counts for nothing."));
}

/** One assessment's reasoning, as it was made: the levels, what they mean, who, when, and why. */
export function reasons(program, assessment) {
  const dims = assessment.dimensions.map((d) => [h("dt", {}, d.label),
    h("dd", {}, h("strong", {}, `${d.level} ${d.level_label}`), h("div", { class: "cell-sub" }, d.definition))]);
  return h("div", { class: "stack" },
    h("div", { class: "row wrap" }, ratingBadge(assessment.ramp_level, assessment.rating_label),
      assessment.superseded ? pill("Superseded") : null,
      h("span", { class: "muted" }, `by ${assessment.assessed_by}`),
      h("time", { class: "subtle", datetime: assessment.assessed_at, title: dateTime(assessment.assessed_at) }, date(assessment.assessed_at))),
    h("dl", { class: "dl" },
      h("dt", {}, "Likelihood"), h("dd", {}, h("strong", {}, `${assessment.likelihood} ${assessment.likelihood_label}`),
        h("div", { class: "cell-sub" }, assessment.likelihood_definition)),
      dims,
      h("dt", {}, "Overall impact"), h("dd", {}, h("strong", {}, `${assessment.impact} ${assessment.impact_label}`),
        h("div", { class: "cell-sub" }, "The highest level rated on any dimension."))),
    h("div", {}, h("div", { class: "label" }, "Why"), h("p", { class: "prose" }, assessment.rationale)),
    assessment.suggested ? h("details", { class: "examples", open: assessment.suggested.rating !== assessment.rating },
      h("summary", {}, assessment.suggested.rating === assessment.rating
        ? "What the controls suggested (the assessor agreed)" : "What the controls suggested (the assessor judged otherwise)"),
      suggestionView(program, assessment.suggested)) : null,
    h("p", { class: "subtle" }, `Scoring method version ${assessment.method_version}.`));
}

/** A row of defined levels to choose from. The definition of the chosen level is always in view. */
export function levelPicker({ legend, hint = null, levels, value = null, allowNone = false, onChange = null }) {
  let chosen = value;
  const about = h("div", { class: "level-about", "aria-live": "polite" });
  const describe = () => {
    const level = levels.find((item) => item.level === chosen);
    about.textContent = level ? level.definition ?? "" : allowNone ? "Does not apply, or has not been judged." : "Choose a level.";
  };
  const name = `level-${Math.random().toString(36).slice(2)}`;
  const option = (level, text) => h("label", { class: "level", title: levels.find((item) => item.level === level)?.definition ?? "" },
    h("input", { type: "radio", name, value: String(level ?? ""), checked: chosen === level, onchange: () => {
      chosen = level;
      describe();
      onChange?.(chosen);
    } }),
    h("span", {}, level ? h("b", {}, String(level)) : null, text));
  describe();
  return {
    node: h("fieldset", { class: "level-picker" }, h("legend", {}, legend), hint ? h("p", { class: "hint subtle" }, hint) : null,
      h("div", { class: "levels" }, allowNone ? option(null, "None") : null, levels.map((item) => option(item.level, item.label))), about),
    value: () => chosen,
  };
}

export function closeOrReopen(risk, { onClose, onReopen }) {
  return risk.status === "closed"
    ? button("Reopen", { onclick: onReopen })
    : button("Close", { kind: "btn-ghost", onclick: onClose });
}
