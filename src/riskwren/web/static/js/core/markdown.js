// A small Markdown, for the text of documents. It is read into plain objects, never HTML, so
// nothing written in a document can become markup: the page builds its elements from these
// objects with the DOM helper, which only ever inserts text.
//
// Blocks: headings (# to ####), paragraphs, bulleted and numbered lists (one level of
// nesting), quotations, code between ``` fences, rules (---), and tables with a header row.
// Inline: **strong**, *emphasis*, `code`, and [links](https://…). A link may go to http,
// https, or mailto, or to a path in this app; anything else is shown as text.

const HEADING = /^(#{1,4})\s+(.*?)\s*#*\s*$/;
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const FENCE = /^\s{0,3}```/;
const QUOTE = /^\s{0,3}>\s?(.*)$/;
const ITEM = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/;
const DIVIDER = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;
const INLINE = /`([^`]+)`|\*\*(.+?)\*\*|__(.+?)__|\*(?!\s)(.+?)\*|(?<![\w])_(?!\s)(.+?)_(?![\w])|\[([^\]]+)\]\(([^()\s]+)\)/;

export function safeHref(href) {
  return /^(https?:|mailto:)/i.test(href) || /^\/(?!\/)/.test(href) ? href : null;
}

/** Inline text into nodes: text, strong, em, code, and link. */
export function inline(text) {
  const out = [];
  let rest = String(text ?? "");
  while (rest) {
    const found = INLINE.exec(rest);
    if (!found) {
      out.push({ type: "text", text: rest });
      break;
    }
    if (found.index) out.push({ type: "text", text: rest.slice(0, found.index) });
    const [whole, code, strong, strong2, em, em2, label, href] = found;
    if (code !== undefined) out.push({ type: "code", text: code });
    else if (strong !== undefined || strong2 !== undefined) out.push({ type: "strong", children: inline(strong ?? strong2) });
    else if (em !== undefined || em2 !== undefined) out.push({ type: "em", children: inline(em ?? em2) });
    else {
      const safe = safeHref(href);
      out.push(safe ? { type: "link", href: safe, children: inline(label) } : { type: "text", text: whole });
    }
    rest = rest.slice(found.index + whole.length);
  }
  // Neighbouring pieces of plain text are one.
  return out.reduce((all, node) => {
    const last = all[all.length - 1];
    if (node.type === "text" && last?.type === "text") last.text += node.text;
    else all.push(node);
    return all;
  }, []);
}

/** The words of inline nodes, without their marks: for headings' anchors and contents. */
export function plainText(nodes) {
  return nodes.map((node) => node.text ?? plainText(node.children ?? [])).join("");
}

function cells(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function list(lines, start) {
  // Items at the first indent; deeper lines are a list inside the item before them.
  const first = ITEM.exec(lines[start]);
  const indent = first[1].length;
  const ordered = /\d/.test(first[2]);
  const items = [];
  const raw = [];
  let index = start;
  while (index < lines.length) {
    const line = lines[index];
    const item = ITEM.exec(line);
    if (item && item[1].length < indent) break;
    if (item && item[1].length <= indent + 1) {
      if (/\d/.test(item[2]) !== ordered) break;
      items.push({ inline: inline(item[3]), children: [] });
      raw.push(item[3]);
      index += 1;
    } else if (item && item[1].length > indent + 1 && items.length) {
      const nested = list(lines, index);
      items[items.length - 1].children.push(nested.block);
      index = nested.next;
    } else if (line.trim() && /^\s{2,}\S/.test(line) && items.length) {
      // A line carried on under its item.
      raw[raw.length - 1] += ` ${line.trim()}`;
      items[items.length - 1].inline = inline(raw[raw.length - 1]);
      index += 1;
    } else {
      break;
    }
  }
  return { block: { type: "list", ordered, start: ordered ? Number.parseInt(first[2], 10) : null, items }, next: index };
}

/** Text into blocks. */
export function parse(text) {
  const lines = String(text ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  const used = new Map();
  let index = 0;
  const anchor = (words) => {
    const base = words.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "section";
    const seen = used.get(base) ?? 0;
    used.set(base, seen + 1);
    return seen ? `${base}-${seen + 1}` : base;
  };
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (FENCE.test(line)) {
      const body = [];
      index += 1;
      while (index < lines.length && !FENCE.test(lines[index])) body.push(lines[index++]);
      index += 1;
      blocks.push({ type: "code", text: body.join("\n") });
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      const nodes = inline(heading[2]);
      blocks.push({ type: "heading", level: heading[1].length, inline: nodes, id: anchor(plainText(nodes)) });
      index += 1;
      continue;
    }
    if (RULE.test(line)) {
      blocks.push({ type: "rule" });
      index += 1;
      continue;
    }
    if (QUOTE.test(line)) {
      const body = [];
      while (index < lines.length && QUOTE.test(lines[index])) body.push(QUOTE.exec(lines[index++])[1]);
      blocks.push({ type: "quote", blocks: parse(body.join("\n")) });
      continue;
    }
    if (ITEM.test(line)) {
      const found = list(lines, index);
      blocks.push(found.block);
      index = found.next;
      continue;
    }
    if (line.includes("|") && index + 1 < lines.length && DIVIDER.test(lines[index + 1])) {
      const head = cells(line).map(inline);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        const row = cells(lines[index++]).map(inline);
        while (row.length < head.length) row.push([]);
        rows.push(row.slice(0, head.length));
      }
      blocks.push({ type: "table", head, rows });
      continue;
    }
    const words = [];
    while (
      index < lines.length && lines[index].trim() && !HEADING.test(lines[index]) && !FENCE.test(lines[index])
      && !QUOTE.test(lines[index]) && !ITEM.test(lines[index]) && !RULE.test(lines[index])
    ) {
      words.push(lines[index++].trim());
    }
    blocks.push({ type: "paragraph", inline: inline(words.join(" ")) });
  }
  return blocks;
}

/** The headings, for a list of contents. A first heading that is the document's title is
 * not a section of it, and is left out. */
export function contents(blocks) {
  const titled = blocks[0]?.type === "heading" && blocks[0].level === 1;
  const found = blocks.filter((block, at) => block.type === "heading" && block.level <= 2 && !(titled && at === 0));
  const top = Math.min(...found.map((block) => block.level));
  return found.map((block) => ({ id: block.id, level: block.level - top + 1, text: plainText(block.inline) }));
}
