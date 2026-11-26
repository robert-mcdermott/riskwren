// Icons, drawn here as inline SVG so that they take the color of the text around them.

const NS = "http://www.w3.org/2000/svg";

// Each icon is a list of path data on a 24 by 24 grid, drawn with a round 1.75 stroke.
const PATHS = {
  home: ["M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"],
  people: ["M9 11a3.25 3.25 0 1 0 0-6.5A3.25 3.25 0 0 0 9 11z", "M3 19.5c.4-3.2 2.8-5 6-5s5.6 1.8 6 5", "M16 4.8a3.25 3.25 0 0 1 0 6.1", "M17.5 14.7c2 .6 3.2 2.3 3.5 4.8"],
  units: ["M9 3.5h6v4.5H9z", "M3.5 16h6v4.5h-6z", "M14.5 16h6v4.5h-6z", "M12 8v4", "M6.5 16v-4h11v4"],
  appearance: ["M12 3.5a8.5 8.5 0 1 0 0 17c1.2 0 1.8-.800 1.8-1.7 0-1.3-1-1.6-1-2.8 0-1 .800-1.7 1.9-1.7H17a3.5 3.5 0 0 0 3.5-3.5c0-4-3.8-7.3-8.5-7.3z", "M7.8 12.2h.010", "M9.7 8.2h.010", "M14.2 7.7h.010"],
  search: ["M10.8 17.3a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z", "m20 20-4.3-4.3"],
  menu: ["M4 6.5h16", "M4 12h16", "M4 17.5h16"],
  close: ["m6 6 12 12", "M18 6 6 18"],
  check: ["m5 12.5 4.5 4.5L19 7.5"],
  "chevron-down": ["m6.5 9.5 5.5 5.5 5.5-5.5"],
  "chevron-right": ["m9.5 6.5 5.5 5.5-5.5 5.5"],
  sun: ["M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M12 2.8v2", "M12 19.2v2", "m5.5 5.5 1.4 1.4", "m17.1 17.1 1.4 1.4", "M2.8 12h2", "M19.2 12h2", "m5.5 18.5 1.4-1.4", "m17.1 6.9 1.4-1.4"],
  moon: ["M20 14.2A8 8 0 0 1 9.8 4a8 8 0 1 0 10.2 10.2z"],
  monitor: ["M4 5h16v11H4z", "M9 20h6", "M12 16v4"],
  logout: ["M10 4.5H6a1.5 1.5 0 0 0-1.5 1.5v12A1.5 1.5 0 0 0 6 19.5h4", "M15 8l4 4-4 4", "M19 12H9.5"],
  key: ["M14.5 9.5a4 4 0 1 1-7.7 1.5L3 14.8V18h3.2v-2h2v-2h1.3l.800-.800a4 4 0 0 1 4.2-3.7z", "M15.5 8.5h.010"],
  user: ["M12 11.5a3.75 3.75 0 1 0 0-7.5 3.75 3.75 0 0 0 0 7.5z", "M5 20c.500-3.5 3.3-5.5 7-5.5s6.5 2 7 5.5"],
  plus: ["M12 5v14", "M5 12h14"],
  upload: ["M12 15.5V4.5", "m7.5 8.5 4.5-4.5 4.5 4.5", "M4.5 15v3.5a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1V15"],
  alert: ["M12 4 2.8 19.5h18.4z", "M12 10v4.5", "M12 17h.010"],
  info: ["M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17z", "M12 11v5.5", "M12 7.8h.010"],
  edit: ["M4 20h4L19 9l-4-4L4 16z", "m13.5 6.5 4 4"],
  trash: ["M4.5 7h15", "M9.5 7V4.5h5V7", "M6.5 7l.800 12.5h9.4L17.5 7"],
  shield: ["M12 3.5 5 6v5.5c0 4.3 2.9 7.3 7 9 4.1-1.7 7-4.7 7-9V6z"],
  dot: ["M12 12h.010"],
};

/** An icon by name. It is decorative: put the words beside it, or label the button. */
export function icon(name, className = "icon") {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", className);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.75");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  for (const d of PATHS[name] ?? PATHS.dot) {
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

/**
 * The wren on its perch: a round body, a short beak, and the cocked tail that makes a wren a
 * wren. The line beneath it is the perch, and the threshold it watches from.
 */
export function wren(className = "brand-mark") {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 64 64");
  svg.setAttribute("class", className);
  svg.setAttribute("aria-hidden", "true");
  const shapes = [
    ["path", { d: "M22 34 13.5 11", fill: "none", stroke: "currentColor", "stroke-width": "7", "stroke-linecap": "round" }],
    ["ellipse", { cx: "33", cy: "37", rx: "17", ry: "13", transform: "rotate(12 33 37)", fill: "currentColor" }],
    ["path", { d: "M37 27.5a8.5 8.5 0 1 0 17 0 8.5 8.5 0 1 0-17 0zm9.4-2.3a1.6 1.6 0 1 0 3.2 0 1.6 1.6 0 1 0-3.2 0z", fill: "currentColor", "fill-rule": "evenodd" }],
    ["path", { d: "M52 23.5 61.5 21.5l-8.5 6.5z", fill: "currentColor" }],
    ["path", { d: "M36 48.5V56M29 47.5V56", fill: "none", stroke: "currentColor", "stroke-width": "2.4", "stroke-linecap": "round" }],
    ["path", { d: "M10 57.5H54", fill: "none", stroke: "currentColor", "stroke-width": "3.4", "stroke-linecap": "round" }],
  ];
  for (const [tag, attrs] of shapes) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    svg.append(node);
  }
  return svg;
}
