import { h } from "../core/dom.js";
import { emptyState } from "../components/ui.js";
import { show } from "./page.js";

export function notFound(main) {
  return show(main, {
    title: "Not found",
    view: () => emptyState({ iconName: "search", title: "There is nothing at this address",
      text: "The page may have moved, or you may not have access to it.",
      action: h("a", { class: "btn btn-primary", href: "/" }, "Go home") }),
  });
}
