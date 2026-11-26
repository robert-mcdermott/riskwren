// How issues and exceptions are shown wherever one is listed, and the picker both use to
// say which records something is about.

import { get } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date } from "../core/format.js";
import { recordChip, TYPES } from "./record.js";
import { pill } from "./ui.js";

// Severity: a word, a tone, and a mark, so it is never told by color alone.
export const SEVERITY = { critical: ["Critical", "danger", "▲▲"], high: ["High", "danger", "▲"], moderate: ["Moderate", "warn", "■"], low: ["Low", "", "▽"] };
export const ISSUE_STATUS = { open: ["Open", "info"], proposed: ["Awaiting confirmation", "warn"], closed: ["Closed", "ok"], cancelled: ["Withdrawn", ""] };
export const EXCEPTION_STATE = { requested: ["Requested", "info"], upcoming: ["Approved, not yet begun", ""], in_force: ["In force", "ok"], expiring: ["Ends soon", "warn"],
  expired: ["Expired", ""], refused: ["Refused", ""], withdrawn: ["Withdrawn", ""] };

export function severityPill(key, labels = null) {
  const [text, tone, mark] = SEVERITY[key] ?? [key, "", "■"];
  const node = pill("", tone);
  node.append(h("span", { "aria-hidden": "true" }, mark), labels?.[key] ?? text);
  return node;
}

export const issueStatus = (issue) => (issue.overdue ? pill("Overdue", "danger") : pill(ISSUE_STATUS[issue.status]?.[0] ?? issue.status, ISSUE_STATUS[issue.status]?.[1] ?? ""));
export const exceptionState = (state) => pill(EXCEPTION_STATE[state]?.[0] ?? state, EXCEPTION_STATE[state]?.[1] ?? "");

/** When an issue is due, with where the date started if it has moved. */
export function issueDue(issue) {
  return h("span", {}, h("span", { class: issue.overdue ? "overdue" : "" }, date(issue.due_on)),
    issue.moved ? h("div", { class: "cell-sub" }, `Moved ${issue.moved === 1 ? "once" : `${issue.moved} times`}, from ${date(issue.original_due_on)}`) : null);
}

/**
 * Choose records by searching for them. `types` are record types to look in; `chosen` is
 * the list being edited, in place. Returns the node to put in a form.
 */
export function recordPicker({ types, chosen, label, placeholder, empty }) {
  const list = h("div", { class: "stack-sm" });
  const search = h("input", { class: "input", type: "search", placeholder, "aria-label": placeholder });
  const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Records found" });
  const draw = () => {
    list.replaceChildren(...(chosen.length ? chosen.map((record, index) => h("div", { class: "owner-row" },
      h("div", { class: "grow" }, recordChip(record, { link: false })),
      button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${record.name}`, onclick: () => {
        chosen.splice(index, 1);
        draw();
      } }))) : [h("p", { class: "muted" }, empty)]));
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
    const pages = await Promise.all(types.map((type) => get(`/api/v1/${TYPES[type].path}`, { q: words, sort: "name", limit: 5 }, { fresh: true })));
    if (mine !== latest) return;
    const offered = pages.flatMap((page, index) => page.data.map((r) => ({ ...r, type: types[index] }))).filter((r) => !chosen.some((c) => c.ref === r.ref));
    results.replaceChildren(...(offered.length ? offered.map((record) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
      chosen.push(record);
      search.value = "";
      results.replaceChildren();
      draw();
    } }, icon(TYPES[record.type].iconName), h("span", {}, h("span", { class: "cell-main" }, record.name), h("span", { class: "cell-sub" }, ` ${record.ref}`))))
      : [h("div", { class: "subtle pick-none" }, "Nothing matches.")]));
  };
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(look, 180);
  });
  draw();
  return h("div", { class: "stack-sm" }, list, h("div", { class: "field" }, h("div", { class: "label" }, label), search, results));
}
