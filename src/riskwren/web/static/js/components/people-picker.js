// Find a person by name or email.

import { get } from "../core/api.js";
import { h, uid } from "../core/dom.js";
import { avatar } from "./ui.js";

/** A search box whose results are buttons. onPick(account) is called with the one chosen. */
export function peoplePicker({ label = "Add a person", exclude = () => false, onPick }) {
  const id = uid("people");
  const input = h("input", { class: "input", type: "search", id, placeholder: "Name or email", autocomplete: "off" });
  const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "People found" });
  let timer = null;
  let latest = 0;
  const search = async () => {
    const words = input.value.trim();
    const mine = ++latest;
    if (words.length < 2) {
      results.replaceChildren();
      return;
    }
    const found = (await get("/api/v1/accounts", { q: words })).data;
    if (mine !== latest) return;
    const shown = found.filter((account) => account.status !== "disabled" && !exclude(account)).slice(0, 6);
    results.replaceChildren(...(shown.length
      ? shown.map((account) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
        input.value = "";
        results.replaceChildren();
        onPick(account);
        input.focus();
      } }, avatar(account.display_name), h("span", {}, h("span", { class: "cell-main" }, account.display_name),
        h("span", { class: "cell-sub" }, ` ${account.email}`))))
      : [h("div", { class: "subtle pick-none" }, "Nobody matches.")]));
  };
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(search, 180);
  });
  return h("div", { class: "field" }, h("label", { for: id }, label), input, results);
}
