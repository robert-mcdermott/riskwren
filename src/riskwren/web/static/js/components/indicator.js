// How an indicator is shown: where it stands, which way it is going, and its readings as a
// line against its levels. The picture is never the only telling: the same readings are in a
// table, and the state is always a word as well as a color.

import { h } from "../core/dom.js";
import { pill } from "../components/ui.js";

export const STATES = { breach: ["Past its limit", "danger"], warn: ["Past its warning level", "warn"], ok: ["Within its limits", "ok"], no_reading: ["No reading yet", ""] };
const TRENDS = { worse: "Getting worse", better: "Getting better", steady: "Steady" };
const SVG = "http://www.w3.org/2000/svg";

export const statePill = (state) => pill(...(STATES[state] ?? [state, ""]));
export const trendWord = (trend) => TRENDS[trend] ?? "";

export function amount(indicator, value) {
  if (value == null) return "";
  const number = Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
  return indicator.measure === "%" ? `${number}%` : indicator.measure ? `${number} ${indicator.measure}` : number;
}

function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs)) if (value != null) node.setAttribute(key, String(value));
  node.append(...children.flat().filter(Boolean));
  return node;
}

/** The readings as a line, with the warning level and the limit drawn across. */
export function readingChart(indicator, readings, { width = 640, height = 200, compact = false } = {}) {
  const values = readings.map((reading) => (typeof reading === "number" ? reading : reading.value));
  if (!values.length) return h("p", { class: "muted" }, "No readings yet.");
  const levels = [indicator.breach_at, indicator.warn_at].filter((level) => level != null);
  const low = Math.min(...values, ...levels);
  const high = Math.max(...values, ...levels);
  const span = high - low || 1;
  const pad = compact ? 4 : 28;
  const left = compact ? 2 : 44;
  const x = (index) => left + (values.length === 1 ? (width - left - pad) / 2 : (index * (width - left - pad)) / (values.length - 1));
  const y = (value) => pad + (1 - (value - low) / span) * (height - pad * 2);
  const level = (value, tone, text) => (value == null ? null : [
    svg("line", { x1: left, x2: width - pad + (compact ? pad : 0), y1: y(value), y2: y(value), class: `chart-level chart-${tone}` }),
    compact ? null : svg("text", { x: left - 6, y: y(value) + 4, class: "chart-label", "text-anchor": "end" }, text)]);
  const last = values.length - 1;
  const label = `${values.length} readings, from ${amount(indicator, values[0])} to ${amount(indicator, values[last])}. `
    + `Limit ${amount(indicator, indicator.breach_at)}${indicator.warn_at != null ? `, warning level ${amount(indicator, indicator.warn_at)}` : ""}.`;
  return svg("svg", { viewBox: `0 0 ${width} ${height}`, class: compact ? "chart chart-spark" : "chart", role: "img", "aria-label": label, preserveAspectRatio: compact ? "none" : null },
    level(indicator.warn_at, "warn", amount(indicator, indicator.warn_at)),
    level(indicator.breach_at, "danger", amount(indicator, indicator.breach_at)),
    values.length > 1 ? svg("polyline", { points: values.map((value, index) => `${x(index)},${y(value)}`).join(" "), class: "chart-line" }) : null,
    compact ? svg("circle", { cx: x(last), cy: y(values[last]), r: 3, class: "chart-dot" })
      : values.map((value, index) => svg("circle", { cx: x(index), cy: y(value), r: index === last ? 4.5 : 3, class: "chart-dot" })));
}
