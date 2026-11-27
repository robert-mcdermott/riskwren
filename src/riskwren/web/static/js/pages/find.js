// Finding anything on record, and keeping the record in order.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural, titleCase } from "../core/format.js";
import { units } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { listHref } from "../components/charts.js";
import { personField } from "../components/people-picker.js";
import { hrefOf, statusPill, TYPES } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const ACTION = { label: "Action", plural: "Actions", iconName: "check" };
const meta = (type) => TYPES[type] ?? ACTION;
const hrefFor = (item) => (item.type === "action" ? `/actions?q=${encodeURIComponent(item.ref)}` : hrefOf(item.ref));

/** Records found by words, for the command palette. */
export async function quickFind(text) {
  const found = (await get("/api/v1/search", { q: text, limit: 4 }, { fresh: true })).data;
  return found.groups.flatMap((group) => group.items.map((item) => ({
    label: item.name, hint: `${meta(item.type).label} · ${item.ref}`, iconName: meta(item.type).iconName, href: hrefFor(item),
  })));
}

export function searchPage(main) {
  const asked = query().get("q") ?? "";
  const only = query().get("type");
  return show(main, {
    title: "Search",
    load: async () => {
      const [found, unitIndex] = await Promise.all([
        asked.trim().length > 1 ? get("/api/v1/search", { q: asked, type: only || undefined, limit: only ? 50 : 6 }, { fresh: true }) : null, units()]);
      return { found: found?.data ?? null, units: unitIndex };
    },
    view: (data) => {
      const box = h("input", { class: "input", type: "search", value: asked, placeholder: "A name, a reference, or a few words", "aria-label": "Search" });
      let timer = null;
      box.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => setQuery({ q: box.value || null, type: null }), 300);
      });
      if (document.activeElement?.getAttribute?.("aria-label") === "Search" || !asked) {
        queueMicrotask(() => {
          box.focus();
          box.setSelectionRange(box.value.length, box.value.length);
        });
      }
      const found = data.found;
      const groups = found?.groups ?? [];
      const results = !found
        ? emptyState({ iconName: "search", title: "Search everything on record", text: "Risks, controls, issues, systems, evidence, and the rest, by name, reference, summary, or what something is called in another system. You find only what you may open." })
        : !groups.length
          ? emptyState({ iconName: "search", title: `Nothing matches “${asked}”`, text: "Every word has to be on the record. Try fewer words, or part of one." })
          : groups.map((group) => card({ title: `${titleCase(group.label)} · ${group.total}`, flush: true,
            actions: group.total > group.items.length ? h("a", { href: `/${group.path}?q=${encodeURIComponent(asked)}` }, `All ${group.total}`) : null },
          h("ul", { class: "plain-list rows found" }, group.items.map((item) => h("li", {},
            h("div", { class: "record-icon small", "data-record": item.type, "aria-hidden": "true" }, icon(meta(item.type).iconName, "icon icon-sm")),
            h("div", { class: "grow" },
              h("a", { class: "cell-main", href: hrefFor(item) }, item.name),
              h("div", { class: "cell-sub" }, [item.ref, data.units.byId.get(item.org_unit_id)?.name, item.summary].filter(Boolean).join(" · "))),
            item.status && !["active", "open"].includes(item.status) ? statusPill(item.status) : null)))));
      return h("div", { class: "stack-lg" },
        pageHeader({ title: "Search", lede: found && groups.length ? `${plural(found.total, "record")} for “${found.query}”${only ? `, ${meta(only).plural.toLowerCase()} only` : ""}.` : null }),
        h("div", { class: "filters" }, h("div", { class: "filter-search wide" }, box),
          only ? button("Every kind", { onclick: () => setQuery({ type: null }) }) : null),
        results);
    },
  });
}

function completenessCard(rows) {
  if (!rows.length) return card({ title: "What records are missing" }, emptyState({ iconName: "check", title: "Nothing to describe yet" }));
  return card({ title: "What records are missing", flush: true },
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Kind"), h("th", { scope: "col" }, "Missing something"), h("th", { scope: "col" }, "What"))),
      h("tbody", {}, rows.map((row) => h("tr", {},
        h("td", { class: "cell-main" }, titleCase(row.label)),
        h("td", { class: "nowrap" }, row.incomplete
          ? h("a", { href: listHref(`/${row.path}`, row.filters) }, `${row.incomplete} of ${row.total}`)
          : h("span", { class: "muted" }, `None of ${row.total}`)),
        h("td", {}, row.missing.length ? h("ul", { class: "plain-list" }, row.missing.map((figure) => h("li", {},
          h("a", { href: listHref(`/${row.path}`, figure.filters) }, `${figure.count} without ${figure.label}`))))
          : h("span", { class: "muted" }, "Everything expected is said")))))))); 
}

function duplicatesCard(groups, unitIndex, reload) {
  const pairs = groups.flatMap((group) => group.pairs.map((pair) => ({ ...pair, label: group.label })));
  const title = "Likely duplicates";
  if (!pairs.length) {
    return card({ title }, emptyState({ iconName: "check", title: "No two records look like the same thing",
      text: "Records are compared by name: the same words in any order, or nearly the same spelling." }));
  }
  return card({ title, flush: true },
    h("p", { class: "card-note muted" }, "Two records with the same words in their names, or nearly the same spelling. Nothing is merged for you: open both, keep the better one, move what the other holds, and retire it. If they are different things, say so and the pair is not suggested again."),
    h("ul", { class: "plain-list rows" }, pairs.map((pair) => h("li", { class: "row wrap" },
      h("div", { class: "grow stack-sm" }, pair.records.map((record) => h("div", {},
        h("a", { class: "cell-main", href: hrefOf(record.ref) }, record.name), " ",
        h("span", { class: "cell-sub" }, [record.ref, unitIndex.byId.get(record.org_unit_id)?.name].filter(Boolean).join(" · "))))),
      button("Different things", { kind: "btn-sm", "aria-label": `${pair.records[0].ref} and ${pair.records[1].ref} are different things`, onclick: async () => {
        try {
          await post("/api/v1/tidy/not-duplicates", { refs: pair.records.map((record) => record.ref) });
          toast("Noted. The pair will not be suggested again.");
          reload();
        } catch (error) {
          toast(error.detail || "That did not work.");
        }
      } })))));
}

function handoverCard(people) {
  const title = "From people who have left";
  if (!people.length) {
    return card({ title }, emptyState({ iconName: "check", title: "Nothing is waiting to be passed on",
      text: "When an account is disabled, what the person alone answered for goes to the steward of its unit, and is listed here until someone is named for good." }));
  }
  return card({ title, flush: true }, h("ul", { class: "plain-list rows" }, people.map((person) => h("li", { class: "row" },
    h("div", { class: "grow" }, h("a", { class: "cell-main", href: `/handover/${person.id}` }, person.name),
      h("div", { class: "cell-sub" }, `${plural(person.count, "thing")} you can pass on`)),
    h("a", { class: "btn btn-sm", href: `/handover/${person.id}` }, "Pass on")))));
}

export function tidyPage(main) {
  return show(main, {
    title: "Tidy",
    load: async () => {
      const [found, unitIndex] = await Promise.all([get("/api/v1/tidy", null, { fresh: true }), units()]);
      return { ...found.data, units: unitIndex };
    },
    view: (data, reload) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Reports", title: "Tidy", lede: "What would make the record more use: facts not yet said, the same thing written down twice, and what people who have left still hold. Each figure is the count of the list it opens, for what you may see." }),
      handoverCard(data.handover),
      completenessCard(data.completeness),
      duplicatesCard(data.duplicates, data.units, reload)),
  });
}

const KINDS = { owner: "Owner", delegate: "Delegate", asked: "Asked in a campaign" };

export function handoverPage(main, params) {
  return show(main, {
    title: "Pass on",
    load: async () => {
      const [found, unitIndex] = await Promise.all([get(`/api/v1/accounts/${params.id}/holdings`, null, { fresh: true }), units()]);
      return { ...found.data, units: unitIndex };
    },
    view: (data, reload) => {
      const person = data.account;
      const mine = data.items.filter((item) => item.can_pass_on);
      const chosen = new Set(mine.map((item) => `${item.type}:${item.id}`));
      const to = personField("Who takes it", { hint: "Someone whose account is not disabled. They are told." });
      const go = button("Pass on", { kind: "btn-primary" });
      const count = h("span", { class: "muted" });
      const tally = () => {
        count.textContent = `${plural(chosen.size, "thing")} chosen`;
        go.disabled = !chosen.size;
      };
      go.addEventListener("click", async () => {
        if (!to.value()) {
          to.setError("Choose who takes it.");
          return;
        }
        to.setError(null);
        go.disabled = true;
        try {
          const only = mine.filter((item) => chosen.has(`${item.type}:${item.id}`)).map((item) => ({ type: item.type, id: item.id }));
          const done = await post(`/api/v1/accounts/${person.id}/handover`, { to: to.value(), only });
          toast(`${plural(done.data.passed_on, "thing")} passed on.`);
          reload();
        } catch (error) {
          to.setError(error.fields?.to ?? error.detail ?? "That did not work.");
          go.disabled = false;
        }
      });
      tally();
      const rows = data.items.map((item) => {
        const key = `${item.type}:${item.id}`;
        const what = TYPES[item.type]?.label ?? (item.type === "plan" ? "Treatment plan" : item.type === "action" ? "Action" : "Campaign");
        return h("tr", {},
          h("td", {}, item.can_pass_on ? h("input", { type: "checkbox", class: "pick", checked: true, "aria-label": `Pass on ${item.name}`, onchange: (event) => {
            if (event.target.checked) chosen.add(key);
            else chosen.delete(key);
            tally();
          } }) : null),
          h("td", {}, h("a", { class: "cell-main", href: item.href }, item.name),
            h("div", { class: "cell-sub" }, [titleCase(what), item.ref].filter(Boolean).join(" · "))),
          h("td", {}, KINDS[item.kind] ?? titleCase(item.kind)),
          h("td", {}, data.units.byId.get(item.org_unit_id)?.name ?? ""),
          h("td", {}, item.held_by ? `${item.held_by}, standing in` : h("span", { class: "muted" }, `Still ${person.name}`)));
      });
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: "/tidy" }, icon("chevron-left", "icon icon-sm"), "Tidy"),
        pageHeader({ title: `What ${person.name} held`,
          lede: person.status === "disabled"
            ? "Their account is disabled. What they alone answered for went to the steward of its unit, so nothing is without an owner. Name who takes each thing for good."
            : "Everything they are named on. Pass it on if they are changing jobs or about to leave." }),
        !data.items.length ? card({}, emptyState({ iconName: "check", title: "Nothing left to pass on", text: "Nothing you may see is still in their name or with a stand-in." }))
          : [mine.length ? card({ title: "Pass on" }, h("div", { class: "stack" }, to.node, h("div", { class: "row" }, go, count)))
            : alert("info", "None of this is yours to pass on. An administrator can, or a steward or manager for their own units."),
          card({ title: plural(data.items.length, "thing"), flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Pass on")), h("th", { scope: "col" }, "What"),
              h("th", { scope: "col" }, "As"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "With now"))),
            h("tbody", {}, rows))))]);
    },
  });
}
