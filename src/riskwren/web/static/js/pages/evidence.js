// Evidence: the list, and one item with its file, its dates, and what it supports.

import { get, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural, relative } from "../core/format.js";
import { label, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { editEvidence, fileSize, freshness, KINDS, kindLabel, stateOptions } from "../components/evidence.js";
import { banner, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { recordChip, TYPES } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { exportButton } from "../components/exchange.js";
import { show } from "./page.js";
import { facts, outside, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const TABS = [["overview", "Overview"], ["history", "History"]];

/** Say what the evidence supports: controls and scopes. */
function editSubjects(item, reload) {
  const chosen = item.subjects.records.map((record) => ({ ...record }));
  openOverlay({
    title: "What this evidence supports",
    subtitle: `${item.ref} · ${item.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const list = h("div", { class: "stack-sm" });
      const search = h("input", { class: "input", type: "search", placeholder: "Find a control or a scope", "aria-label": "Find a control or a scope" });
      const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Controls and scopes found" });
      const draw = () => {
        list.replaceChildren(...(chosen.length ? chosen.map((record, index) => h("div", { class: "owner-row" },
          h("div", { class: "grow" }, recordChip(record, { link: false })),
          button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${record.name}`, onclick: () => {
            chosen.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "Nothing yet. Evidence counts once it is attached to the control it shows.")]));
      };
      let latest = 0;
      let timer = null;
      const look = async () => {
        const mine = ++latest;
        const words = search.value.trim();
        if (words.length < 2) {
          results.replaceChildren();
          return;
        }
        const pages = await Promise.all(["control", "scope"].map((type) =>
          get(`/api/v1/${TYPES[type].path}`, { q: words, sort: "name", limit: 6, status: "active" }, { fresh: true })));
        if (mine !== latest) return;
        const offered = pages.flatMap((page, index) => page.data.map((r) => ({ ...r, type: ["control", "scope"][index] }))).filter((r) => !chosen.some((c) => c.ref === r.ref));
        results.replaceChildren(...(offered.length ? offered.map((record) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
          chosen.push(record);
          search.value = "";
          results.replaceChildren();
          draw();
        } }, icon(TYPES[record.type].iconName), h("span", {}, h("span", { class: "cell-main" }, record.name), h("span", { class: "cell-sub" }, ` ${record.ref}`))))
          : [h("div", { class: "subtle pick-none" }, "Nothing matches.")]));
      };
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(look, 180);
      });
      draw();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/evidence/${item.ref}/subjects`, { subjects: chosen.map((record) => record.ref) }) });
        if (done) {
          close();
          toast("Saved.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, list, h("div", { class: "field" }, h("div", { class: "label" }, "Add"), search, results),
        item.subjects.hidden ? h("p", { class: "subtle" }, `It also supports ${item.subjects.hidden} that you do not have access to. They stay as they are.`) : null));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function overview(item, ctx) {
  const period = item.covers_from || item.covers_to ? [item.covers_from ? date(item.covers_from) : "the start", item.covers_to ? date(item.covers_to) : "now"].join(" to ") : null;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      item.state === "stale" ? alert("danger", icon("alert"), h("div", {}, `This stopped counting on ${date(item.valid_until)}. It stays on the record. Collect it again and add a new item.`))
        : item.state === "expiring" ? alert("warn", icon("alert"), h("div", {}, `This stops counting on ${date(item.valid_until)}.`)) : null,
      card({ title: "What it is" },
        item.summary ? prose(item.summary) : null,
        item.kind === "file" ? (item.file
          ? h("div", { class: "row" }, h("span", { class: "owed-icon" }, icon("file")),
            h("div", { class: "grow" }, h("div", { class: "cell-main" }, item.file.name), h("div", { class: "cell-sub" }, fileSize(item.file.size))),
            h("a", { class: "btn", href: `/api/v1/evidence/${item.ref}/file`, download: item.file.name }, "Download"))
          : h("p", { class: "muted" }, "No file has been sent yet. Edit the item to send one.")) : null,
        item.kind === "link" ? h("p", {}, outside(item.url)) : null,
        item.note ? h("div", {}, item.kind === "file" || item.kind === "link" ? h("div", { class: "label" }, "Note") : null, prose(item.note)) : null),
      card({ title: "Supports", actions: item.can.edit ? button("Edit", { kind: "btn-sm", onclick: () => editSubjects(item, ctx.reload) }) : null },
        item.subjects.records.length ? h("div", { class: "chips" }, item.subjects.records.map((record) => recordChip(record)))
          : h("p", { class: "muted" }, "Not attached to anything yet, so it counts toward nothing."),
        item.subjects.hidden ? h("p", { class: "subtle" }, `And ${item.subjects.hidden} more that you do not have access to.`) : null)),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Kind", kindLabel(item.kind)],
        ["Collected", date(item.collected_on)],
        ["Covers", period],
        ["Holds until", h("div", {}, date(item.valid_until), " ", freshness(item.state))],
        ["Data class", item.data_class ? label(ctx.vocab, "data_classes", item.data_class) : null],
        ["Unit", ctx.units.byId.get(item.org_unit_id)?.name],
      ])),
      ownersCard(item, ctx)));
}

export function evidencePage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/evidence/${params.ref}`;
      const [item, vocab, unitIndex, extra] = await Promise.all([get(base, null, { fresh: true }), vocabularies(), units(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { item: { ...item.data, type: "evidence" }, vocab, units: unitIndex, extra: extra?.data ?? [] };
    },
    view: (data, reload) => {
      const item = data.item;
      document.title = `${item.name} · ${item.ref}`;
      const ctx = { vocab: data.vocab, units: data.units, reload };
      const edit = item.can.edit ? button("Edit", { iconName: "edit", onclick: () => editEvidence({ item, vocab: data.vocab, units: data.units, onDone: reload }) }) : null;
      return h("div", { class: "stack" },
        recordHeader(item, { badges: [freshness(item.state), item.restricted ? pill("Restricted") : null, item.status === "retired" ? pill("Retired") : null], actions: edit }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : overview(item, ctx));
    },
  });
}

export function evidenceList(main) {
  const meta = TYPES.evidence;
  return show(main, {
    title: "Evidence",
    load: async () => {
      const [page, vocab, unitIndex] = await Promise.all([get("/api/v1/evidence", Object.fromEntries(query()), { fresh: true }), vocabularies(), units()]);
      return { page, vocab, units: unitIndex };
    },
    view: (data, reload) => {
      const rows = data.page.data;
      const add = () => editEvidence({ vocab: data.vocab, units: data.units, onDone: reload });
      const search = searchBox("Search evidence");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("state", stateOptions("Current or not"), "Whether it counts"),
        filterSelect("kind", [["", "Any kind"], ...KINDS.map(([key]) => [key, kindLabel(key)])], "Kind"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Evidence", "name"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Owner"),
          sortHeader("Collected", "collected_on"), sortHeader("Holds until", "valid_until"), h("th", { scope: "col", class: "numeric" }, "Supports"), sortHeader("Updated", "updated_at"))),
        h("tbody", {}, rows.map((r) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/evidence/${r.ref}` }, r.name),
            h("div", { class: "cell-sub" }, [r.ref, kindLabel(r.kind), r.data_class ? label(data.vocab, "data_classes", r.data_class) : null, r.restricted ? "Restricted" : null].filter(Boolean).join(" · "))),
          h("td", {}, data.units.byId.get(r.org_unit_id)?.name ?? ""),
          ownerCell(r),
          h("td", { class: "nowrap muted" }, date(r.collected_on)),
          h("td", { class: "nowrap" }, date(r.valid_until), " ", freshness(r.state)),
          h("td", { class: "numeric" }, r.supports ? String(r.supports) : h("span", { class: "subtle" }, "Nothing")),
          h("td", { class: "nowrap muted" }, relative(r.updated_at)))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "evidence", title: "No evidence yet", text: meta.lede, action: button("Add evidence", { kind: "btn-primary", onclick: add }) });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Compliance", title: "Evidence", lede: meta.lede, actions: [button("Add evidence", { kind: "btn-primary", iconName: "plus", onclick: add }), exportButton("evidence")] }),
        bar,
        card({ title: plural(data.page.meta.total, "item"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
