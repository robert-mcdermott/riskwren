// Every change in one place, for those who may read everything: narrowed to a person, a
// record, a kind of record, or a span of dates.

import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { dateTime, relative } from "../core/format.js";
import { query, setQuery } from "../core/router.js";
import { peoplePicker } from "../components/people-picker.js";
import { recordChip, TYPES } from "../components/record.js";
import { avatar, card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { filterSelect } from "./records.js";

function entries(rows) {
  return h("ol", { class: "timeline" }, rows.map((entry) => h("li", {},
    h("div", { class: "timeline-dot", "aria-hidden": "true" }),
    h("div", { class: "grow" },
      h("div", { class: "row wrap" }, h("span", { class: "cell-main" }, entry.title),
        h("span", { class: "muted" }, `by ${entry.actor}`),
        h("time", { class: "subtle spacer", datetime: entry.at, title: relative(entry.at) }, dateTime(entry.at))),
      entry.record ? h("div", { class: "timeline-record" }, recordChip(entry.record)) : null,
      entry.lines.length ? h("dl", { class: "changes" }, entry.lines.map((line) => [
        h("dt", {}, line.label),
        h("dd", {}, line.before != null ? h("del", {}, String(line.before)) : h("span", { class: "subtle" }, "empty"),
          h("span", { "aria-hidden": "true" }, " → "), h("span", { class: "sr-only" }, " became "),
          line.after != null ? h("ins", {}, String(line.after)) : h("span", { class: "subtle" }, "empty")),
      ])) : null))));
}

export function wholeHistory(main) {
  return show(main, {
    title: "History",
    load: async () => {
      const asked = Object.fromEntries(query());
      const who = asked.actor ? get(`/api/v1/accounts/${asked.actor}`).then((answer) => answer.data).catch(() => null) : null;
      // Changes to records, unless something else is asked for: sign-ins would crowd them out.
      const [page, person] = await Promise.all([get("/api/v1/history", { ...asked, kind: asked.kind === "all" ? null : asked.kind ?? "records" }, { fresh: true }), who]);
      return { page: page.data, person, asked };
    },
    view: (data) => {
      const { page, asked } = data;
      const filtering = ["actor", "about", "kind", "since", "until"].some((key) => asked[key]);
      const about = h("input", { class: "input", type: "search", value: asked.about ?? "", placeholder: "A reference, such as CTL-0012", "aria-label": "Changes to one record, by its reference",
        onchange: (event) => setQuery({ about: event.target.value.trim().toUpperCase() || null, before: null }) });
      const day = (name, text) => h("label", { class: "filter-date" }, h("span", { class: "sr-only" }, text),
        h("input", { class: "input", type: "date", value: asked[name] ?? "", "aria-label": text, onchange: (event) => setQuery({ [name]: event.target.value || null, before: null }) }));
      const person = data.person
        ? h("div", { class: "row-sm" }, avatar(data.person.display_name), h("span", {}, data.person.display_name),
          button("Anyone", { kind: "btn-sm btn-ghost", "aria-label": "Show changes by anyone", onclick: () => setQuery({ actor: null, before: null }) }))
        : peoplePicker({ label: "Find a person", onPick: (account) => setQuery({ actor: account.id, before: null }) });
      const kinds = [["", "Changes to any record"], ...Object.entries(TYPES).map(([key, type]) => [key, type.plural]), ["other", "Sign-ins, exports, and settings"], ["all", "Everything"]];
      const bar = h("div", { class: "filters filters-history" },
        h("div", { class: "filter-search" }, about), filterSelect("kind", kinds, "Kind of record"),
        day("since", "From this date"), day("until", "Up to this date"));
      const body = page.entries.length ? entries(page.entries)
        : emptyState(filtering ? { iconName: "search", title: "Nothing matches", text: "No change fits what was asked for.", action: button("Clear", { onclick: () => setQuery({ actor: null, about: null, kind: null, since: null, until: null, before: null }) }) }
          : { iconName: "history", title: "No history yet" });
      const older = page.next ? button("Older", { onclick: () => setQuery({ before: page.next }, { replace: false }) }) : null;
      const newest = asked.before ? button("Back to the newest", { kind: "btn-ghost", onclick: () => setQuery({ before: null }) }) : null;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "History",
          lede: "Every change, newest first, as it was recorded: who did what, to which record, and what each thing was before. Nothing here can be edited." }),
        h("div", { class: "split split-history" }, h("div", { class: "stack" }, bar,
          card({ flush: true, footer: older || newest ? h("div", { class: "row" }, older, newest) : null }, body)),
        card({ title: "By one person" }, person)));
    },
  });
}
