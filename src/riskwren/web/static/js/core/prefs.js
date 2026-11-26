// What this browser remembers: light or dark, and the person's own palette if they chose one.

const PREFIX = "riskwren.";
export const MODES = ["system", "light", "dark"];

function read(key) {
  try {
    return window.localStorage.getItem(PREFIX + key);
  } catch {
    return null; // storage can be unavailable (private windows, policy)
  }
}

function write(key, value) {
  try {
    if (value == null) window.localStorage.removeItem(PREFIX + key);
    else window.localStorage.setItem(PREFIX + key, value);
  } catch {
    // nothing to do: the choice lasts for this page only
  }
}

let organizationPalette = read("orgPalette") || "wren";
let organizationRamp = read("orgRamp") || "ordinal";

export function mode() {
  const stored = read("mode");
  return MODES.includes(stored) ? stored : "system";
}

export function setMode(value) {
  write("mode", value === "system" ? null : value);
  apply();
}

/** The palette in effect: the person's own choice, or the organization's default. */
export function palette() {
  return read("palette") || organizationPalette;
}

export function ownPalette() {
  return read("palette");
}

export function setPalette(value) {
  write("palette", value);
  apply();
}

/** The organization's default arrives with /meta; it is remembered so the next visit paints right at once. */
export function setOrganizationPalette(value) {
  organizationPalette = value || "wren";
  write("orgPalette", organizationPalette);
  apply();
}

/** How ratings are colored is the organization's choice alone. */
export function setOrganizationRamp(value) {
  organizationRamp = value === "signal" ? "signal" : "ordinal";
  write("orgRamp", organizationRamp);
  apply();
}

export function apply() {
  const root = document.documentElement;
  const current = mode();
  if (current === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", current);
  root.setAttribute("data-palette", palette());
  root.setAttribute("data-ramp", organizationRamp);
}
