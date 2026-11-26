// The person's own choices: light or dark, and a palette.

import { h, icon } from "../core/dom.js";
import { MODES, mode, ownPalette, palette, setMode, setPalette } from "../core/prefs.js";
import { titleCase } from "../core/format.js";
import { openOverlay } from "./overlay.js";

const MODE_ICONS = { system: "monitor", light: "sun", dark: "moon" };

export function modeSwitch() {
  const group = h("div", { class: "segmented", role: "group", "aria-label": "Light or dark" });
  const draw = () => {
    group.replaceChildren(...MODES.map((name) => h("button", {
      type: "button",
      "aria-pressed": String(mode() === name),
      onclick: () => {
        setMode(name);
        draw();
      },
    }, icon(MODE_ICONS[name], "icon icon-sm"), titleCase(name))));
  };
  draw();
  return group;
}

export function openAppearance(meta) {
  openOverlay({
    title: "Appearance",
    subtitle: "These choices are remembered in this browser.",
    kind: "dialog",
    render: (body) => {
      const palettes = h("div", { class: "segmented", role: "group", "aria-label": "Palette" });
      const draw = () => {
        const defaultName = meta.branding.palette;
        palettes.replaceChildren(...meta.palettes.map((name) => h("button", {
          type: "button",
          "aria-pressed": String(palette() === name),
          onclick: () => {
            setPalette(name === defaultName ? null : name);
            draw();
          },
        }, titleCase(name))));
        note.textContent = ownPalette()
          ? `Your organization's default is ${titleCase(defaultName)}.`
          : "This is your organization's default.";
      };
      const note = h("p", { class: "subtle" });
      body.append(h("div", { class: "stack-lg" },
        h("div", { class: "stack-sm" }, h("div", { class: "label" }, "Mode"), modeSwitch()),
        h("div", { class: "stack-sm" }, h("div", { class: "label" }, "Palette"), palettes, note)));
      draw();
    },
  });
}
