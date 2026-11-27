// Policy documents: their text drawn from the small Markdown, the two sides of a comparison,
// and the words used for their kinds and states.

import { h } from "../core/dom.js";
import { date } from "../core/format.js";
import { contents, parse } from "../core/markdown.js";
import { pill } from "./ui.js";

export const KINDS = { policy: "Policy", standard: "Standard", procedure: "Procedure", guideline: "Guideline" };
export const KIND_HINTS = {
  policy: "What the organization requires, and why. Approved by its leadership.",
  standard: "The particular rules that meet a policy: how long a password, which encryption.",
  procedure: "The steps someone follows to meet a standard or a policy.",
  guideline: "Advice that helps people do it well. Recommended, not required.",
};
export const WORKING = {
  draft: ["Draft", "info"],
  in_review: ["Awaiting approval", "warn"],
  approved: ["Approved, not published", "ok"],
};
export const DECISIONS = {
  pending: ["Not yet", ""],
  approved: ["Approved", "ok"],
  returned: ["Returned", "danger"],
  cancelled: ["No longer asked", ""],
};

export function kindPill(kind) {
  return pill(KINDS[kind] ?? kind, "");
}

export function workingPill(status) {
  const found = WORKING[status];
  return found ? pill(found[0], found[1]) : null;
}

export function reviewPill(state, when) {
  if (state === "overdue") return pill(`Review overdue since ${date(when)}`, "danger");
  if (state === "due") return pill(`Review due ${date(when)}`, "warn");
  return null;
}

function inlineNodes(nodes) {
  return nodes.map((node) => {
    if (node.type === "text") return node.text;
    if (node.type === "code") return h("code", {}, node.text);
    if (node.type === "strong") return h("strong", {}, inlineNodes(node.children));
    if (node.type === "em") return h("em", {}, inlineNodes(node.children));
    const outside = /^https?:/i.test(node.href);
    return h("a", { href: node.href, ...(outside ? { target: "_blank", rel: "noopener noreferrer" } : {}) },
      inlineNodes(node.children));
  });
}

function blockNodes(blocks, shift) {
  return blocks.map((block) => {
    if (block.type === "heading") {
      const level = Math.min(6, block.level + shift);
      return h(`h${level}`, { id: `s-${block.id}`, tabindex: "-1" }, inlineNodes(block.inline));
    }
    if (block.type === "paragraph") return h("p", {}, inlineNodes(block.inline));
    if (block.type === "rule") return h("hr", {});
    if (block.type === "code") return h("pre", {}, h("code", {}, block.text));
    if (block.type === "quote") return h("blockquote", {}, blockNodes(block.blocks, shift));
    if (block.type === "table") {
      return h("div", { class: "table-wrap" }, h("table", { class: "table doc-table" },
        h("thead", {}, h("tr", {}, block.head.map((cell) => h("th", { scope: "col" }, inlineNodes(cell))))),
        h("tbody", {}, block.rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, inlineNodes(cell))))))));
    }
    const tag = block.ordered ? "ol" : "ul";
    return h(tag, block.ordered && block.start !== 1 ? { start: block.start } : {},
      block.items.map((item) => h("li", {}, inlineNodes(item.inline), blockNodes(item.children, shift))));
  });
}

/**
 * A document's text. Its headings sit beneath the page's own, so a "#" in the text is drawn
 * one level down. With three or more sections, a list of contents goes first.
 */
export function documentText(text, { shift = 1, withContents = true } = {}) {
  const blocks = parse(text);
  const sections = contents(blocks);
  const jump = (id) => {
    const target = document.getElementById(`s-${id}`);
    target?.scrollIntoView({ block: "start" });
    target?.focus({ preventScroll: true });
  };
  return h("div", { class: "doc-text" },
    withContents && sections.length >= 3
      ? h("nav", { class: "doc-contents", "aria-label": "Contents" }, h("div", { class: "label" }, "Contents"),
        h("ol", {}, sections.map((section) => h("li", { "data-level": String(section.level) },
          h("button", { type: "button", class: "link-button", onclick: () => jump(section.id) }, section.text)))))
      : null,
    blockNodes(blocks, shift));
}

const SAID = { changed: "Changed: ", added: "Added: ", removed: "Removed: " };

function side(pieces, op) {
  if (!pieces) return h("td", { class: "diff-none" }, h("span", { class: "sr-only" }, "Not in this version"));
  return h("td", {}, SAID[op] ? h("span", { class: "sr-only" }, SAID[op]) : null,
    pieces.map((piece) => (piece.mark ? h("mark", {}, piece.text) : piece.text)));
}

/** Two versions side by side: each row a line, the words that differ marked. */
export function comparison(found, { before, after }) {
  if (!found.rows.length) {
    return h("p", { class: "muted" }, found.same ? "The two versions say the same." : "These versions are not text, so they are compared by their fingerprints alone: they differ.");
  }
  return h("div", { class: "table-wrap" }, h("table", { class: "table diff" },
    h("caption", { class: "sr-only" }, `${before} on the left, ${after} on the right`),
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, before), h("th", { scope: "col" }, after))),
    h("tbody", {}, found.rows.map((row) => (row.op === "folded"
      ? h("tr", { class: "diff-folded" }, h("td", { colspan: "2" }, `${row.count} ${row.count === 1 ? "line" : "lines"} the same`))
      : h("tr", { "data-op": row.op }, side(row.before, row.op), side(row.after, row.op)))))));
}

/** The roles a document can be said to apply to, as their holders are called. */
export const ROLE_NAMES = { admin: "Administrators", manager: "Managers", assessor: "Assessors", auditor: "Auditors", leader: "Leaders", steward: "Stewards" };
