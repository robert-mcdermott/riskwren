// Which questions of a questionnaire are showing, given the answers so far. This is the twin
// of riskwren/oversight/questionnaires.py (showing): both must pass the cases in
// tests/fixtures/questionnaire-cases.json. The server's answer is the one that counts; this one
// lets a form show and hide questions as it is filled in.

import { evaluate } from "./conditions.js";

const blank = (value) => value == null || value === "" || (Array.isArray(value) && value.length === 0);

/** { keys: the questions showing, in order; kept: the answers that count }. An answer to a
 *  question that an earlier answer has hidden is dropped, so it cannot decide what else is asked. */
export function showing(document, answers) {
  const kept = {};
  const keys = [];
  for (const section of document.sections) {
    if (!evaluate(section.show_when, { answers: kept })) continue;
    for (const question of section.questions) {
      if (!evaluate(question.show_when, { answers: kept })) continue;
      keys.push(question.key);
      if (!blank(answers[question.key])) kept[question.key] = answers[question.key];
    }
  }
  return { keys, kept };
}

/** Which sections have at least one question showing. */
export function sectionsShowing(document, keys) {
  const shown = new Set(keys);
  return document.sections.filter((section) => section.questions.some((question) => shown.has(question.key))).map((section) => section.key);
}
