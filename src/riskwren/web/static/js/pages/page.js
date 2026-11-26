// The pattern every page follows: show a skeleton, load, then draw; or say what went wrong.

import { h } from "../core/dom.js";
import { errorState, skeletonPage } from "../components/ui.js";

let token = 0;
let product = "RiskWren";

export function setProduct(name) {
  product = name;
}

export function setTitle(title) {
  document.title = title ? `${title} · ${product}` : product;
}

/**
 * Draw a page. load() fetches what it needs; view(data, reload) returns the page's nodes.
 * A later navigation wins over an earlier one that is still loading.
 */
export async function show(main, { title, load = async () => null, view, narrow = false }) {
  const mine = ++token;
  const page = h("div", { class: `page${narrow ? " page-narrow" : ""}` }, skeletonPage());
  main.replaceChildren(page);
  setTitle(title);
  const run = async () => {
    let data;
    try {
      data = await load();
    } catch (error) {
      if (mine !== token) return;
      page.replaceChildren(errorState(error, () => {
        page.replaceChildren(skeletonPage());
        run();
      }));
      return;
    }
    if (mine !== token) return;
    page.replaceChildren(view(data, run));
    page.querySelector("h1")?.focus({ preventScroll: true });
  };
  await run();
}
