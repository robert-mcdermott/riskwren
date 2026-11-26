// How one record is connected to the others: a picture, and beside it a list that says the
// same thing in full. Both are drawn from one answer, so they cannot disagree. Every record
// in the picture can be reached and opened with the keyboard.

import { get } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural } from "../core/format.js";
import { layout, VIEW } from "../core/graph-layout.js";
import { navigate } from "../core/router.js";
import { hrefOf, recordChip, TYPES, typeOfRef } from "../components/record.js";
import { card, emptyState } from "../components/ui.js";
import { show } from "./page.js";

const NS = "http://www.w3.org/2000/svg";

function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  node.append(...children.flat().filter((child) => child != null));
  return node;
}

const short = (text, most) => (text.length > most ? `${text.slice(0, most - 1).trimEnd()}…` : text);
const typeLabel = (record) => TYPES[record.type ?? typeOfRef(record.ref)]?.label ?? "Record";

/** Something in the picture that acts when clicked, or when Enter or Space is pressed on it. */
function pressable(role, label, act, attrs, ...children) {
  return svg("g", { role, tabindex: "0", "aria-label": label, ...attrs,
    onclick: act,
    onkeydown: (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        act();
      }
    } }, ...children);
}

function picture(graph, opened, toggle) {
  const { nodes, edges, labels } = layout(graph, opened);
  const { width, height } = VIEW.node;
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const lines = edges.map((edge) => {
    const from = byId.get(edge.from);
    const to = byId.get(edge.to);
    const out = to.x >= from.x ? 1 : -1;
    const x1 = from.x + (out * width) / 2;
    const x2 = to.x - (out * width) / 2;
    const mid = (x1 + x2) / 2;
    return svg("path", { class: "gedge", d: `M ${x1} ${from.y} C ${mid} ${from.y}, ${mid} ${to.y}, ${x2} ${to.y}` });
  });
  const drawn = nodes.map((node) => {
    const left = node.x - width / 2;
    const top = node.y - height / 2;
    if (node.more) {
      return svg("g", { class: "gnode gnode-more" },
        svg("rect", { x: left, y: top, width, height, rx: 8 }),
        svg("text", { x: node.x, y: node.y + 5, "text-anchor": "middle" }, `and ${node.more} more, in the list`));
    }
    const record = node.record;
    const type = record.type ?? typeOfRef(record.ref);
    const canOpen = node.ring === 1;
    const isOpen = Boolean(opened[record.ref]);
    const said = `${typeLabel(record)} ${record.ref}: ${record.name}`;
    const body = [
      svg("rect", { x: left, y: top, width, height, rx: 8 }),
      svg("rect", { class: "gnode-kind", x: left, y: top, width: 6, height, rx: 3 }),
      svg("text", { x: left + 16, y: node.y - 1 }, short(record.name, canOpen ? 20 : 24)),
      svg("text", { class: "gnode-ref", x: left + 16, y: node.y + 12 }, record.ref),
      svg("title", {}, said)];
    const main = node.ring === 0
      ? svg("g", { class: "gnode", "data-record": type, "data-ring": "0" }, ...body)
      : pressable("link", `${said}. Show its connections.`, () => navigate(`/graph/${record.ref}`), { class: "gnode", "data-record": type, "data-ring": String(node.ring) }, ...body);
    if (!canOpen) return main;
    const bx = left + width - 17;
    const more = node.beyond ? svg("text", { class: "gnode-beyond", x: node.x, y: top + height + 12, "text-anchor": "middle" }, `and ${node.beyond} more`) : null;
    return svg("g", {}, main, more,
      pressable("button", isOpen ? `Hide what ${record.name} is connected to` : `Show what ${record.name} is connected to`, () => toggle(record.ref),
        { class: "gexpand", "aria-expanded": String(isOpen) },
        svg("circle", { cx: bx, cy: node.y, r: 10 }), svg("text", { x: bx, y: node.y + 4.5, "text-anchor": "middle", "aria-hidden": "true" }, isOpen ? "−" : "+")));
  });
  return svg("svg", { class: "graph", viewBox: `0 0 ${VIEW.width} ${VIEW.height}`, role: "group",
    "aria-label": `${graph.center.name} and the ${plural(graph.count, "record")} connected to it. The list beside the picture says the same.` },
  lines, labels.map((label) => svg("text", { class: "glabel", x: label.x - width / 2, y: label.y }, label.text)), drawn);
}

function listing(graph, opened, toggle, busy) {
  if (!graph.groups.length) return h("p", { class: "muted" }, "Nothing is connected to it that you may see.");
  return h("div", { class: "stack-lg" }, graph.groups.map((group) => h("section", {},
    h("h3", { class: "label" }, `${group.label} (${group.records.length})`),
    h("ul", { class: "glist" }, group.records.map((record) => {
      const more = opened[record.ref];
      return h("li", {},
        h("div", { class: "row-sm wrap" }, h("div", { class: "grow" }, recordChip(record)),
          button(more ? "Hide" : "Expand", { kind: "btn-sm btn-ghost", disabled: busy === record.ref, "aria-expanded": String(Boolean(more)),
            "aria-label": more ? `Hide what ${record.name} is connected to` : `Show what ${record.name} is connected to`, onclick: () => toggle(record.ref) }),
          h("a", { class: "btn btn-sm btn-ghost", href: `/graph/${record.ref}`, "aria-label": `Put ${record.name} in the middle` }, "Center")),
        more ? h("div", { class: "glist-more" }, more.groups.length ? more.groups.map((inner) => h("div", {},
          h("div", { class: "cell-sub" }, inner.label), h("div", { class: "chips" }, inner.records.map((each) => recordChip(each)))))
          : h("p", { class: "subtle" }, "Nothing else is connected to it."),
        more.hidden ? h("p", { class: "subtle" }, `And ${more.hidden} that you do not have access to.`) : null) : null);
    })))));
}

export function graphPage(main, params) {
  return show(main, {
    title: params.ref,
    load: async () => (await get(`/api/v1/graph/${params.ref}`, null, { fresh: true })).data,
    view: (graph) => {
      const center = graph.center;
      const meta = TYPES[center.type ?? typeOfRef(center.ref)];
      document.title = `How ${center.name} is connected`;
      const opened = {};
      let busy = null;
      const stage = h("div", { class: "graph-wrap" });
      const beside = h("div", {});
      const draw = () => {
        // Whatever had the focus keeps it, by its name, when the picture is drawn again.
        const active = document.activeElement;
        const held = active?.getAttribute?.("aria-label");
        const where = beside.contains(active) ? beside : stage;
        stage.replaceChildren(graph.groups.length ? picture(graph, opened, toggle)
          : emptyState({ iconName: "link", title: "Nothing is connected to it yet", text: "Links, risks, controls, scopes, evidence, and issues appear here as they are added." }));
        beside.replaceChildren(listing(graph, opened, toggle, busy));
        if (held) {
          const same = (label) => label.replace(/^(Show|Hide)/, "");
          const again = [...where.querySelectorAll("[aria-label]")].find((node) => same(node.getAttribute("aria-label")) === same(held));
          again?.focus();
        }
      };
      async function toggle(ref) {
        if (opened[ref]) {
          delete opened[ref];
        } else {
          busy = ref;
          try {
            opened[ref] = (await get(`/api/v1/graph/${ref}`, null, { fresh: true })).data;
          } finally {
            busy = null;
          }
        }
        draw();
      }
      draw();
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: hrefOf(center.ref) }, icon("chevron-left", "icon icon-sm"), center.name),
        h("header", { class: "page-header" }, h("div", { class: "grow" },
          h("div", { class: "eyebrow" }, `${meta?.label ?? "Record"} · ${center.ref}`),
          h("h1", { tabindex: "-1" }, `How ${center.name} is connected`),
          h("p", { class: "lede" }, `${plural(graph.count, "record")} joined to it directly. Expand one to see what lies beyond it, or put it in the middle.`,
            graph.hidden ? ` ${graph.hidden} more that you do not have access to ${graph.hidden === 1 ? "is" : "are"} not shown.` : ""))),
        card({ title: "The picture" }, stage,
          h("p", { class: "subtle" }, "Tab moves through the records. Enter on a record puts it in the middle; the button on it shows what lies beyond it.")),
        card({ title: "The same, as a list" }, beside));
    },
  });
}
