// Reports → Measures: every defined figure, what it counts, its value for the reader, and the
// organization's trend over the last quarter. Each figure opens the records it counts.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date } from "../core/format.js";
import { listHref } from "../components/charts.js";
import { card, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const NS = "http://www.w3.org/2000/svg";
function svg(name, attrs = {}, ...children) {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) if (value != null) node.setAttribute(key, value);
  for (const child of children.flat()) if (child) node.append(child);
  return node;
}

/** A small line of the snapshots, with its first and last figures in words for those who cannot see it. */
function spark(points) {
  if (points.length < 2) return h("span", { class: "subtle" }, points.length ? "One snapshot so far" : "No snapshots yet");
  const values = points.map((point) => point.value);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  const width = 160;
  const height = 36;
  const x = (index) => 2 + (index * (width - 4)) / (values.length - 1);
  const y = (value) => 4 + (1 - (value - low) / span) * (height - 8);
  const label = `From ${values[0]} on ${date(points[0].day)} to ${values[values.length - 1]} on ${date(points[points.length - 1].day)}`;
  return svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart chart-spark measure-spark", role: "img", "aria-label": label },
    svg("polyline", { points: values.map((value, index) => `${x(index)},${y(value)}`).join(" "), class: "chart-line" }),
    svg("circle", { cx: x(values.length - 1), cy: y(values[values.length - 1]), r: 3, class: "chart-dot" }));
}

function change(measure) {
  if (measure.change == null || measure.change === 0) return h("span", { class: "subtle" }, measure.change === 0 ? "No change" : "");
  const up = measure.change > 0;
  const good = measure.better === "neither" ? null : (measure.better === "lower") !== up;
  const words = `${up ? "Up" : "Down"} ${Math.abs(measure.change)} in the quarter`;
  return h("span", { class: good == null ? "subtle" : good ? "ok-text" : "warn-text" }, words);
}

export function measuresPage(main) {
  return show(main, {
    title: "Measures",
    load: async () => (await get("/api/v1/measures", null, { fresh: true })).data,
    view: (data) => {
      const groups = Object.entries(data.groups).map(([key, label]) => {
        const rows = data.measures.filter((measure) => measure.group === key);
        return card({ title: label, flush: true },
          h("div", { class: "table-wrap" }, h("table", { class: "table measure-table" },
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Measure"), h("th", { scope: "col", class: "numeric" }, "Now"),
              h("th", { scope: "col" }, `The last ${Math.round(data.days / 30)} months`), h("th", { scope: "col" }, "Change"))),
            h("tbody", {}, rows.map((measure) => h("tr", {},
              h("td", {}, h("div", { class: "cell-main" }, measure.label), h("div", { class: "cell-sub" }, measure.counts)),
              h("td", { class: "numeric" }, h("a", { class: "measure-value", href: listHref(`/${measure.path}`, measure.filters),
                "aria-label": `${measure.value}: open the list of ${measure.label.toLowerCase()}` }, String(measure.value))),
              h("td", {}, spark(measure.trend)),
              h("td", {}, change(measure))))))));
      });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Measures",
          lede: "Each figure says what it counts, and opens the list of records it counts, as you may see them. The trend is the whole organization's, from a snapshot taken each day." }),
        groups);
    },
  });
}
