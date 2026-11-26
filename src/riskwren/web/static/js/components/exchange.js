// Getting a list out, and records in from a spreadsheet saved as CSV: choose the file, say
// which column is which, check it, read the report, and only then import.

import { buildUrl, upload } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural } from "../core/format.js";
import { query } from "../core/router.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { alert } from "./ui.js";

/** A button that offers the list on the page as a file: as filtered, and as you may see it. */
export function exportButton(kind, params = null) {
  return button("Export", { iconName: "download", onclick: () => openOverlay({
    kind: "dialog",
    title: "Export this list",
    subtitle: "As it is filtered now, and as much of it as you may see.",
    render: (body, footer, close) => {
      const asked = { ...(params ?? Object.fromEntries(query())), cursor: null, limit: null };
      const link = (format, text) => h("a", { class: "btn", href: buildUrl(`/api/v1/exports/${kind}`, { ...asked, format }), download: "", onclick: () => setTimeout(close, 0) }, icon("download"), text);
      body.append(h("div", { class: "stack" },
        h("div", { class: "row wrap" }, link("csv", "A spreadsheet (CSV)"), link("json", "Data (JSON)")),
        h("p", { class: "subtle" }, "Taking an export is recorded in the history. A CSV of records can be imported into another installation.")));
      footer.replaceChildren(button("Close", { kind: "btn-ghost", onclick: close }));
      footer.hidden = false;
    },
  }) });
}

function report(data) {
  if (!data.problems.length) {
    return h("div", { class: "report" },
      h("div", { class: "report-counts" }, h("div", {}, h("strong", {}, data.created), "to add")),
      alert("ok", icon("check"), h("div", {}, `All ${plural(data.rows, "row")} are good. Nothing has been added yet.`)));
  }
  return h("div", { class: "report" },
    alert("danger", icon("alert"), h("div", {},
      h("strong", {}, `${plural(data.problems.length, "problem")} to fix. `), "Nothing is imported until every row is good.")),
    h("ul", { class: "problem-list" }, data.problems.map((problem) =>
      h("li", {}, h("span", { class: "row-no" }, `Row ${problem.row}`), h("span", {}, problem.message)))));
}

/**
 * Import from a CSV. `path` is where the file is sent, under /api/v1/imports: for example
 * "records/systems", or "requirements/<framework key>". `what` names what is imported.
 */
export function openRecordImport({ path, what, onDone }) {
  openOverlay({
    title: `Import ${what}`,
    subtitle: "From a spreadsheet saved as CSV, with a header row.",
    render: (body, footer, close) => {
      const file = h("input", { type: "file", class: "input", accept: ".csv,text/csv", "aria-label": "CSV file" });
      const matching = h("div", {});
      const result = h("div", { "aria-live": "polite" });
      const check = button("Check the file", { kind: "btn-primary", disabled: true });
      const apply = button("Import", { kind: "btn-primary", hidden: true });
      let text = null;
      let choices = {};
      const failed = (error) => {
        const detail = (error.errors ?? []).map((each) => each.message).join(" ") || Object.values(error.fields ?? {}).join(" ") || error.detail || "The file could not be read.";
        result.replaceChildren(alert("danger", icon("alert"), h("div", {}, detail)));
      };
      const send = (step, params) => upload(`/api/v1/imports/${path}${step}`, new Blob([text], { type: "text/csv" }), params);
      const reset = () => {
        check.hidden = false;
        apply.hidden = true;
        result.replaceChildren();
      };
      const drawColumns = (found) => {
        choices = Object.fromEntries(found.fields.map((field) => [field.name, field.column ?? ""]));
        matching.replaceChildren(h("div", { class: "stack" },
          h("p", { class: "muted" }, `${plural(found.rows, "row")}. Say which column of the file holds each thing. What the headings made plain is filled in.`),
          h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "This"), h("th", { scope: "col" }, "Is in the column"))),
            h("tbody", {}, found.fields.map((field) => {
              const id = `map-${field.name}`;
              const pick = h("select", { class: "select", id, onchange: (event) => {
                choices[field.name] = event.target.value;
                reset();
              } },
              h("option", { value: "" }, field.required ? "Choose…" : "Not in the file"),
              found.columns.map((column) => h("option", { value: column, selected: column === field.column }, column)));
              return h("tr", {},
                h("td", {}, h("label", { for: id, class: "cell-main" }, field.label, field.required ? h("span", { class: "subtle" }, " (needed)") : null),
                  field.hint ? h("div", { class: "cell-sub" }, field.hint) : null),
                h("td", {}, pick));
            })))),
          found.unused.length ? h("p", { class: "subtle" }, `Not read unless chosen above: ${found.unused.join(", ")}.`) : null));
      };
      const run = async (dryRun) => {
        const active = dryRun ? check : apply;
        active.disabled = true;
        try {
          const answer = await send("", { dry_run: dryRun, mapping: JSON.stringify(choices) });
          if (!dryRun && answer.data.applied) {
            close();
            toast(`Imported: ${answer.data.created} added.`);
            onDone?.();
            return;
          }
          result.replaceChildren(report(answer.data));
          const ready = !answer.data.problems.length && answer.data.created > 0;
          apply.hidden = !ready;
          check.hidden = ready;
        } catch (error) {
          failed(error);
        } finally {
          active.disabled = false;
        }
      };
      file.addEventListener("change", async () => {
        text = file.files[0] ? await file.files[0].text() : null;
        check.disabled = !text;
        matching.replaceChildren();
        reset();
        if (!text) return;
        try {
          drawColumns((await send("/columns", {})).data);
        } catch (error) {
          check.disabled = true;
          failed(error);
        }
      });
      check.addEventListener("click", () => run(true));
      apply.addEventListener("click", () => run(false));
      body.append(h("div", { class: "stack-lg" },
        h("p", { class: "muted" }, "Each row is added as if by hand, by the same rules, and in your name. Nothing is added unless every row can be. An export from this list has the right columns already."),
        file, matching, result));
      footer.replaceChildren(h("div", { class: "row" }, check, apply, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
