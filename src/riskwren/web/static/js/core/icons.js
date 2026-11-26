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
  process: ["M4 5h5v4.5H4z", "M15 14.5h5V19h-5z", "M9 7.2h3.5a2 2 0 0 1 2 2v5.300", "M9.500 16.800H6.500", "M4 14.5h2.5V19H4z"],
  risk: ["M12 4 2.8 19.5h18.4z", "M12 10v4.5", "M12 17h.010"],
  control: ["M12 3.5 5 6v5.5c0 4.3 2.9 7.3 7 9 4.1-1.7 7-4.7 7-9V6z", "m9 12 2.2 2.2L15.200 10"],
  system: ["M4 5.5h16v13H4z", "M4 9.5h16", "M7 7.500h.010", "M9.500 7.500h.010", "M8 13h8", "M8 15.800h5"],
  third_party: ["M4 9.5 5.5 4.5h13L20 9.5", "M4 9.5c0 1.4 1.2 2.5 2.7 2.5s2.6-1.1 2.6-2.5c0 1.4 1.2 2.5 2.7 2.5s2.7-1.1 2.7-2.5c0 1.4 1.1 2.5 2.6 2.5S20 10.9 20 9.5", "M5.5 12v7.5h13V12", "M10 19.5v-4h4v4"],
  plan: ["M8 6.500h11", "M8 12h11", "M8 17.500h11", "m3.800 6 .9.9 1.600-1.800", "m3.800 11.500.9.9 1.600-1.800", "M4.500 17.500h.010"],
  accept: ["M12 20.500a8.500 8.500 0 1 0 0-17 8.500 8.500 0 0 0 0 17z", "m8.500 12.200 2.400 2.400 4.600-5"],
  grid: ["M4.500 4.500h6v6h-6z", "M13.500 4.500h6v6h-6z", "M4.500 13.500h6v6h-6z", "M13.500 13.500h6v6h-6z"],
  chart: ["M4.500 19.500h15", "M7 16.500v-5", "M12 16.500V7", "M17 16.500v-8"],
  program: ["M5 6.5h7", "M16 6.5h3", "M5 12h3", "M12 12h7", "M5 17.5h9", "M18 17.5h1", "M14 4.5v4", "M10 10v4", "M16 15.500v4"],
  history: ["M4.5 12a7.5 7.5 0 1 0 2.4-5.5", "M4 4.5v3.5h3.5", "M12 8v4.3l2.8 1.7"],
  link: ["M10 14a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1 1", "M14 10a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5l1-1"],
  lock: ["M6.5 11h11v8.5h-11z", "M8.5 11V8a3.5 3.5 0 0 1 7 0v3"],
  "chevron-left": ["m14.5 6.5-5.5 5.5 5.5 5.5"],
  external: ["M13.5 5H19v5.5", "M19 5l-8 8", "M17 13.5V19H5V7h5.5"],
  dot: ["M12 12h.01"],
  file: ["M7 3.5h7l4 4v13H7z", "M14 3.5v4h4"],
  evidence: ["M7 3.5h7l4 4v13H7z", "M14 3.5v4h4", "m9.5 14 2 2 3.5-4"],
  information: ["M5 6.5c0-1.4 3.1-2.5 7-2.5s7 1.1 7 2.5-3.1 2.5-7 2.5-7-1.1-7-2.5z", "M5 6.5v11c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-11", "M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"],
  scope: ["M4.5 7.5v-3h3", "M16.5 4.5h3v3", "M19.5 16.5v3h-3", "M7.5 19.5h-3v-3", "M9 9h6v6H9z"],
  framework: ["M5.5 4.5h10a3 3 0 0 1 3 3v12h-10a3 3 0 0 1-3-3z", "M5.5 16.5a3 3 0 0 1 3-3h10", "M9.5 8.5h5"],
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
