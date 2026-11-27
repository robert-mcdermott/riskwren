// Saved views: a list's filters and sort kept under a name. Loaded when the panel is opened.

import { del, get, patch, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { query } from "../core/router.js";
import { banner, checkbox, field, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { emptyState } from "./ui.js";

/** The filters as they stand, without where the reader is in the list. */
function asked() {
  const params = query();
  params.delete("cursor");
  params.sort();
  return params.toString();
}

export function openViews() {
  const path = window.location.pathname;
  openOverlay({
    title: "Saved views",
    subtitle: "A view keeps this list's filters and sort under a name. It keeps the question, not the answer: whoever opens it sees what they may see.",
    render: async (body, footer, close) => {
      const draw = async () => {
        const found = await get("/api/v1/views", { path }, { fresh: true });
        const mayShare = found.meta.can_share;
        const now = asked();
        const rows = found.data.map((view) => h("li", { class: "row" },
          h("div", { class: "grow" },
            h("a", { class: "cell-main", href: view.href, "aria-current": view.query === now ? "true" : null, onclick: close }, view.name),
            h("div", { class: "cell-sub" }, [view.shared ? (view.mine ? "Shared with everyone" : `Shared by ${view.by}`) : "Only you", view.query === now ? "showing now" : null].filter(Boolean).join(" · "))),
          view.mine && mayShare ? button(view.shared ? "Stop sharing" : "Share", { kind: "btn-sm btn-ghost", "aria-label": `${view.shared ? "Stop sharing" : "Share"} ${view.name}`,
            onclick: async () => {
              await patch(`/api/v1/views/${view.id}`, { shared: !view.shared });
              draw();
            } }) : null,
          view.can_change ? button("Delete", { kind: "btn-sm btn-ghost", "aria-label": `Delete ${view.name}`, onclick: async () => {
            await del(`/api/v1/views/${view.id}`);
            toast(`“${view.name}” was deleted.`);
            draw();
          } }) : null));
        const name = field("Name", { required: true, maxlength: 80, hint: now ? "Keeps the filters and sort this list has now." : "Nothing is filtered now, so this would keep the whole list." });
        const share = mayShare ? checkbox("Share with everyone", { hint: "It appears in this list for everyone. Each person still sees only what they may see." }) : null;
        const problem = banner();
        const save = button("Save this view", { kind: "btn-primary", type: "submit" });
        const form = h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
          event.preventDefault();
          const done = await submit({ button: save, fields: { name }, banner: problem,
            run: () => post("/api/v1/views", { name: name.input.value, path, query: now, shared: share?.input.checked || undefined }) });
          if (!done) return;
          toast(`“${done.data.name}” was saved.`);
          draw();
        } }, problem, name.node, share?.node ?? null, h("div", {}, save));
        body.replaceChildren(h("div", { class: "stack-lg" },
          rows.length ? h("ul", { class: "plain-list rows" }, rows)
            : emptyState({ iconName: "search", title: "No saved views of this list", text: "Filter the list the way you keep needing it, then save it here." }),
          h("div", { class: "stack" }, h("h3", {}, "Save what is showing"), form)));
      };
      await draw();
    },
  });
}
