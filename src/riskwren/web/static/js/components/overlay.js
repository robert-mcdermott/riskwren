// Drawers and dialogs: accessible modal panels that trap focus and close on Escape.

import { button, h, iconButton, uid } from "../core/dom.js";

let open = null;

function focusables(root) {
  const selector = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';
  return [...root.querySelectorAll(selector)].filter((el) => !el.hidden && el.offsetParent !== null);
}

export function closeOverlay() {
  if (!open) return;
  const { backdrop, panel, returnFocus, onKey, onClose } = open;
  document.removeEventListener("keydown", onKey, true);
  backdrop.remove();
  panel.remove();
  open = null;
  returnFocus?.focus?.();
  onClose?.();
}

/**
 * Open a panel. render(body, footer, close) fills it and may be async. kind is "drawer"
 * (from the right, for editing) or "dialog" (centered, for a question). onClose runs once
 * the panel has gone, however it was closed.
 */
export function openOverlay({ title, subtitle = null, render, kind = "drawer", onClose = null }) {
  closeOverlay();
  const returnFocus = document.activeElement;
  const titleId = uid("overlay-title");
  const body = h("div", { class: "drawer-body" });
  const footer = h("div", { class: "drawer-footer", hidden: true });
  const panel = h("section", { class: kind, role: "dialog", "aria-modal": "true", "aria-labelledby": titleId },
    h("div", { class: "drawer-header" },
      h("div", { class: "grow stack-sm" }, h("h2", { id: titleId }, title),
        subtitle ? h("div", { class: "muted" }, subtitle) : null),
      iconButton("close", "Close", { onclick: closeOverlay })),
    body, footer);
  const backdrop = h("div", { class: "backdrop", onclick: closeOverlay });
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeOverlay();
    } else if (event.key === "Tab") {
      const items = focusables(panel);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  };
  document.addEventListener("keydown", onKey, true);
  document.body.append(backdrop, panel);
  open = { backdrop, panel, returnFocus, onKey, onClose };
  Promise.resolve(render(body, footer, closeOverlay)).then(() => {
    if (open?.panel !== panel) return;
    const items = focusables(panel);
    (items.find((el) => el.matches("input, select, textarea")) ?? items[1] ?? items[0])?.focus();
  });
  return { panel, body, footer };
}

/** Ask before doing something that matters. run() is awaited after the dialog closes. */
export function confirmAction({ title, text, confirmLabel, danger = false, run }) {
  openOverlay({
    title,
    kind: "dialog",
    render: (body, footer, close) => {
      body.append(h("div", { class: "stack" }, typeof text === "string" ? h("p", {}, text) : text));
      footer.replaceChildren(h("div", { class: "row" },
        button(confirmLabel, { kind: danger ? "btn-danger" : "btn-primary", onclick: async () => {
          close();
          await run();
        } }),
        button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
