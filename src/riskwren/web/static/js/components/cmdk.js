// The command palette: jump to a page or run an action from the keyboard.

import { h, icon } from "../core/dom.js";
import { navigate } from "../core/router.js";

let open = null;

function close() {
  if (!open) return;
  document.removeEventListener("keydown", open.onKey, true);
  open.backdrop.remove();
  open.panel.remove();
  open.returnFocus?.focus?.();
  open = null;
}

/** items: [{ label, hint, iconName, href | run, keywords }] */
export function openPalette(items) {
  if (open) {
    close();
    return;
  }
  const returnFocus = document.activeElement;
  const input = h("input", { class: "palette-input", type: "text", placeholder: "Go to a page or run an action…",
    "aria-label": "Command", role: "combobox", "aria-expanded": "true", "aria-controls": "palette-list", autocomplete: "off" });
  const list = h("div", { class: "palette-list", id: "palette-list", role: "listbox" });
  const panel = h("div", { class: "palette", role: "dialog", "aria-modal": "true", "aria-label": "Command palette" }, input, list);
  const backdrop = h("div", { class: "backdrop", onclick: close });
  let shown = [];
  let selected = 0;

  const choose = (item) => {
    close();
    if (item.href) navigate(item.href);
    else item.run?.();
  };
  const draw = () => {
    const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    shown = items.filter((item) => {
      const text = `${item.label} ${item.hint ?? ""} ${item.keywords ?? ""}`.toLowerCase();
      return words.every((word) => text.includes(word));
    });
    selected = Math.min(selected, Math.max(0, shown.length - 1));
    if (!shown.length) {
      list.replaceChildren(h("div", { class: "palette-empty" }, "Nothing matches."));
      return;
    }
    list.replaceChildren(...shown.map((item, index) => h("div", {
      class: "palette-item", role: "option", id: `palette-item-${index}`, "aria-selected": String(index === selected),
      onclick: () => choose(item),
      onmousemove: () => {
        if (selected !== index) {
          selected = index;
          draw();
        }
      },
    }, icon(item.iconName ?? "chevron-right"), h("span", {}, item.label), item.hint ? h("span", { class: "hint" }, item.hint) : null)));
    input.setAttribute("aria-activedescendant", `palette-item-${selected}`);
    list.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!shown.length) return;
      selected = (selected + (event.key === "ArrowDown" ? 1 : -1) + shown.length) % shown.length;
      draw();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (shown[selected]) choose(shown[selected]);
    } else if (event.key === "Tab") {
      event.preventDefault(); // the palette is one control
    }
  };
  input.addEventListener("input", () => {
    selected = 0;
    draw();
  });
  document.addEventListener("keydown", onKey, true);
  document.body.append(backdrop, panel);
  open = { backdrop, panel, onKey, returnFocus };
  draw();
  input.focus();
}
