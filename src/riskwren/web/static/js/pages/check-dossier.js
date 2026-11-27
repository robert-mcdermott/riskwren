// Reports → Check a dossier: is a dossier whole and unchanged, and when was it taken.

import { upload } from "../core/api.js";
import { h, uid } from "../core/dom.js";
import { dateTime } from "../core/format.js";
import { alert, card, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

function verdict(found) {
  const manifest = found.manifest ?? {};
  const record = manifest.record ?? {};
  if (!found.verified) {
    return alert("danger", h("strong", {}, "It does not verify. "),
      found.problems.length === 1 ? found.problems[0] : h("ul", {}, found.problems.map((problem) => h("li", {}, problem))));
  }
  return h("div", { class: "stack" },
    alert("ok", h("strong", {}, "It verifies. "), `The dossier of ${record.ref} ${record.name} is whole and unchanged: every one of its ${manifest.files} files is as its manifest lists it.`),
    h("p", {}, found.recorded
      ? `The history says ${found.recorded.by} took it on ${dateTime(found.recorded.at)}.`
      : `It says ${manifest.taken_by} took it on ${dateTime(manifest.taken_at)}, but this installation's history has no record of it: it may have been taken from another.`),
    h("p", { class: "subtle" }, "Fingerprint (SHA-256): ", h("code", { class: "fingerprint" }, manifest.fingerprint)));
}

export function checkDossier(main) {
  return show(main, {
    title: "Check a dossier",
    view: () => {
      const id = uid("dossier");
      const result = h("div", { role: "status", "aria-live": "polite" });
      const input = h("input", { id, type: "file", accept: ".zip,application/zip", class: "input" });
      input.addEventListener("change", async () => {
        const file = input.files?.[0];
        if (!file) return;
        result.replaceChildren(h("p", { class: "subtle" }, "Checking…"));
        try {
          const found = (await upload("/api/v1/dossiers/check", file)).data;
          result.replaceChildren(verdict(found));
        } catch (error) {
          result.replaceChildren(alert("danger", error.detail || "It could not be checked."));
        }
      });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Check a dossier",
          lede: "A dossier is a scope, a risk, or a third party with everything known about it, as one ZIP file. Choose one to check that every file in it is as its manifest lists it, and that nothing was added or taken away. The file is read, not kept." }),
        card({}, h("div", { class: "field" }, h("label", { for: id }, "The dossier's ZIP file"), input,
          h("div", { class: "hint" }, "Up to 32 MB here. For a larger one, run riskwren check-dossier FILE on the server.")), result));
    },
  });
}
