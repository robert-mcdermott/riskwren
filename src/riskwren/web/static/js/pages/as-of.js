// Reports → As of a date: a register, or one record, as it stood at the end of a day,
// rebuilt from the history, beside how it is now.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date, plural, titleCase } from "../core/format.js";
import { query, setQuery } from "../core/router.js";
import { card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

function dayPicker(value, labelText = "As it stood at the end of") {
  const input = h("input", { class: "input", type: "date", value, max: new Date().toISOString().slice(0, 10), "aria-label": labelText,
    onchange: () => input.value && setQuery({ on: input.value }) });
  return h("label", { class: "row-sm" }, h("span", { class: "muted" }, labelText), input);
}

function shown(value) {
  if (value == null || value === "") return h("span", { class: "subtle" }, "—");
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value)) ? date(value) : String(value);
}

export function asOfRegister(main) {
  const asked = query();
  const params = { type: asked.get("type") || "risk", on: asked.get("on") || undefined, live: asked.get("live") === "false" ? "false" : "true" };
  return show(main, {
    title: "As of a date",
    load: async () => (await get("/api/v1/as-of", params, { fresh: true })).data,
    view: (data) => {
      const kind = h("select", { class: "select", "aria-label": "Register", onchange: () => setQuery({ type: kind.value }) },
        Object.entries(data.types).map(([key, label]) => h("option", { value: key, selected: key === data.type }, titleCase(label))));
      const live = h("input", { type: "checkbox", id: "as-of-live", checked: data.live_only, onchange: () => setQuery({ live: live.checked ? null : "false" }) });
      const bar = h("div", { class: "filters" }, kind, dayPicker(data.on),
        h("div", { class: "check" }, live, h("label", { for: "as-of-live" }, "Only what was open or in use then")));
      const rows = data.rows.map((row) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/as-of/${row.ref}?on=${data.on}` }, h("span", { class: "mono" }, row.ref), " ", row.name),
          row.renamed ? h("div", { class: "cell-sub" }, "Renamed since") : null),
        data.columns.map((column) => {
          const changed = row.changed.includes(column.key);
          return h("td", { class: changed ? "as-of-changed" : null }, shown(row.then[column.key]),
            changed ? h("div", { class: "cell-sub" }, "Now: ", shown(row.now[column.key])) : null);
        })));
      const what = data.plural.toLowerCase();
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "As of a date",
          lede: "A register as it stood at the end of a day, rebuilt from the history: what existed then, as it was then. Where something has changed since, it says what it is now." }),
        bar,
        h("p", { class: "subtle", role: "status" }, `${plural(data.rows.length, data.label.toLowerCase(), what)} at the end of ${date(data.on)}, of those you may see.`),
        rows.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("caption", { class: "sr-only" }, `${data.plural} as they stood at the end of ${date(data.on)}`),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, data.label), data.columns.map((column) => h("th", { scope: "col" }, column.label)))),
          h("tbody", {}, rows))))
          : emptyState({ iconName: "history", title: `No ${what} then`, text: "Nothing you may see had been added by the end of that day." }));
    },
  });
}

function owners(list) {
  return list.length ? h("ul", { class: "plain-list stack-sm" }, list.map((owner) => h("li", {}, owner.name, h("span", { class: "subtle" }, ` · ${owner.kind_label}`))))
    : h("p", { class: "subtle" }, "Nobody");
}

export function asOfRecord(main, { ref }) {
  const on = query().get("on") || undefined;
  return show(main, {
    title: `${ref} as of a date`,
    load: async () => (await get(`/api/v1/as-of/${ref}`, { on }, { fresh: true })).data,
    view: (data) => {
      const header = pageHeader({ eyebrow: `${data.label} · ${data.ref}`, title: data.name,
        lede: `As it stood at the end of ${date(data.on)}, rebuilt from the history, beside how it is now. ${plural(data.changes_since, "change")} since.`,
        actions: h("a", { class: "btn btn-secondary", href: `/${data.path}/${data.ref}` }, "Open it as it is now") });
      if (!data.existed) {
        return h("div", { class: "stack-lg" }, header, h("div", { class: "filters" }, dayPicker(data.on)),
          emptyState({ iconName: "history", title: "It did not exist yet", text: `It was added on ${date(data.created_at)}.` }));
      }
      const changed = data.fields.filter((field) => field.changed).length;
      const fields = [...data.fields.filter((field) => field.changed), ...data.fields.filter((field) => !field.changed)];
      return h("div", { class: "stack-lg" }, header,
        h("div", { class: "filters" }, dayPicker(data.on), h("span", { class: "subtle", role: "status" }, changed ? `${plural(changed, "field")} changed since` : "Nothing has changed since")),
        card({ title: "Its fields", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table as-of-fields" },
          h("caption", { class: "sr-only" }, `${data.ref} then and now`),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Field"), h("th", { scope: "col" }, `At the end of ${date(data.on)}`), h("th", { scope: "col" }, "Now"))),
          h("tbody", {}, fields.map((field) => h("tr", { class: field.changed ? "as-of-changed" : null },
            h("th", { scope: "row" }, field.label, field.changed ? [" ", pill("Changed", "info")] : null),
            h("td", {}, shown(field.then)), h("td", {}, shown(field.now)))))))),
        h("div", { class: "grid-2" },
          card({ title: `Owners at the end of ${date(data.on)}` }, owners(data.owners_then)),
          card({ title: "Owners now" }, owners(data.owners_now))));
    },
  });
}
