// Import from a spreadsheet saved as CSV: check first, read the report, then apply.

import { upload } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural } from "../core/format.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { alert } from "./ui.js";

function report(data) {
  const counts = h("div", { class: "report-counts" },
    h("div", {}, h("strong", {}, data.created), "to add"),
    h("div", {}, h("strong", {}, data.updated), "to change"),
    h("div", {}, h("strong", {}, data.unchanged), "unchanged"));
  if (!data.problems.length) {
    return h("div", { class: "report" }, counts,
      alert("ok", icon("check"), h("div", {}, `All ${plural(data.rows, "row")} are good. Nothing has been changed yet.`)));
  }
  return h("div", { class: "report" },
    alert("danger", icon("alert"), h("div", {},
      h("strong", {}, `${plural(data.problems.length, "problem")} to fix. `), "Nothing will be imported until every row is good.")),
    h("ul", { class: "problem-list" }, data.problems.map((problem) =>
      h("li", {}, h("span", { class: "row-no" }, `Row ${problem.row}`), h("span", {}, problem.message)))));
}

/** kind: "units" or "people". columns: the header line, shown as an example. */
export function openImport({ kind, title, intro, sample, onDone }) {
  openOverlay({
    title,
    subtitle: intro,
    render: (body, footer, close) => {
      const file = h("input", { type: "file", class: "input", accept: ".csv,text/csv", "aria-label": "CSV file" });
      const result = h("div", { "aria-live": "polite" });
      const check = button("Check the file", { kind: "btn-primary", disabled: true });
      const apply = button("Import", { kind: "btn-primary", hidden: true });
      let text = null;
      const run = async (dryRun) => {
        const active = dryRun ? check : apply;
        active.disabled = true;
        try {
          const answer = await upload(`/api/v1/imports/${kind}`, new Blob([text], { type: "text/csv" }), { dry_run: dryRun });
          if (!dryRun && answer.data.applied) {
            close();
            toast(`Imported: ${answer.data.created} added, ${answer.data.updated} changed.`);
            onDone?.();
            return;
          }
          result.replaceChildren(report(answer.data));
          const ready = !answer.data.problems.length && (answer.data.created + answer.data.updated) > 0;
          apply.hidden = !ready;
          check.hidden = ready;
        } catch (error) {
          const detail = Object.values(error.fields ?? {}).join(" ") || error.detail || "The file could not be read.";
          result.replaceChildren(alert("danger", icon("alert"), h("div", {}, detail)));
        } finally {
          active.disabled = false;
        }
      };
      file.addEventListener("change", async () => {
        text = file.files[0] ? await file.files[0].text() : null;
        check.disabled = !text;
        check.hidden = false;
        apply.hidden = true;
        result.replaceChildren();
      });
      check.addEventListener("click", () => run(true));
      apply.addEventListener("click", () => run(false));
      body.append(h("div", { class: "stack" },
        h("p", { class: "muted" }, "Save your spreadsheet as CSV with a header row like this:"),
        h("div", { class: "sample" }, sample),
        file, result));
      footer.replaceChildren(h("div", { class: "row" }, check, apply, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
