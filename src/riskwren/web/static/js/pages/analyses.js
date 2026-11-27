// Risk analyses: a structured assessment over a scope. Each thing in it is taken against
// each threat, and the answer is that it does not apply, that a risk on the register covers
// it, or that a risk is raised.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, dateTime, plural, relative } from "../core/format.js";
import { program as loadProgram, unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { segments } from "../components/charts.js";
import { banner, checkbox, field, section, select, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { hrefOf, statusPill, TYPES } from "../components/record.js";
import { ownUnits } from "../core/session.js";
import { rating } from "../components/risk.js";
import { listTools } from "../components/tidy.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const OUTCOME = {
  pending: ["Not answered", ""], not_applicable: ["Does not apply", ""],
  covered: ["Covered by a risk", "ok"], raised: ["Risk raised", "warn"],
};
const outcomePill = (key) => pill(OUTCOME[key]?.[0] ?? key, OUTCOME[key]?.[1] ?? "");
const said = (error) => Object.values(error.fields ?? {}).join(" ") || error.detail || "That did not work.";

function progress(counts) {
  return segments([
    { label: "do not apply", value: counts.not_applicable, tone: "none" },
    { label: "covered by a risk", value: counts.covered, tone: "ok" },
    { label: plural(counts.raised, "risk raised", "risks raised").replace(/^\d+ /, ""), value: counts.raised, tone: "warn" },
    { label: "not answered", value: counts.pending, tone: "gap" },
  ], { label: `${counts.considered} of ${counts.items} questions answered` });
}

function riskLink(risk, programData) {
  return h("span", { class: "row-sm wrap" }, h("a", { href: hrefOf(risk.ref) }, risk.name), h("span", { class: "ref" }, risk.ref),
    risk.residual_rating ? rating(programData, risk.residual_rating) : null);
}

function start({ programData, unitIndex, scopes, library }) {
  openOverlay({
    title: "Start a risk analysis",
    subtitle: "Choose what to look at and which threats to take it against. One question is made for each pair.",
    render: (body, footer, close) => {
      const name = field("Name", { required: true, maxlength: 200, hint: "Such as “Clinical systems, security risk analysis 2027”." });
      const summary = field("Why, and how", { type: "textarea", hint: "What prompted it and who is taking part. It heads the report." });
      const over = select("Look at", [["scope", "What a scope's boundary names"], ["unit", "Everything a unit holds"]], { value: scopes.length ? "scope" : "unit" });
      const scope = select("Scope", [["", "Choose…"], ...scopes.map((item) => [item.ref, `${item.name} (${item.ref})`])]);
      const unit = select("Unit", unitOptions(unitIndex.tree, { only: can("assess") ? null : ownUnits(), blank: "Choose…" }),
        { hint: "With every unit beneath it. Only what is in use is looked at." });
      const perCategory = new Map();
      for (const entry of library) perCategory.set(entry.category, (perCategory.get(entry.category) ?? 0) + 1);
      const boxes = programData.categories.map((top) => {
        const count = [top, ...top.children].reduce((sum, item) => sum + (perCategory.get(item.key) ?? 0), 0);
        return count ? { key: top.key, box: checkbox(`${top.name} (${count})`) } : null;
      }).filter(Boolean);
      const sized = h("p", { class: "muted", "aria-live": "polite" }, "Choose what to look at and at least one kind of threat.");
      const threatsError = h("div", { class: "error", role: "alert", hidden: true });
      const problem = banner();
      const values = () => ({
        name: name.input.value, summary: summary.input.value,
        ...(over.input.value === "scope" ? { scope: scope.input.value || null } : { org_unit_id: unit.input.value ? Number(unit.input.value) : null }),
        categories: boxes.filter((item) => item.box.input.checked).map((item) => item.key),
      });
      let latest = 0;
      const size = async () => {
        scope.node.hidden = over.input.value !== "scope";
        unit.node.hidden = over.input.value === "scope";
        const asked = values();
        const mine = ++latest;
        if (!(asked.scope || asked.org_unit_id) || !asked.categories.length) {
          sized.textContent = "Choose what to look at and at least one kind of threat.";
          return;
        }
        try {
          const found = (await post("/api/v1/risk-analyses/preview", asked)).data;
          if (mine === latest) sized.textContent = `${plural(found.assets, "thing")} against ${plural(found.threats, "threat")}: ${plural(found.items, "question")}.`;
        } catch (error) {
          if (mine === latest) sized.textContent = said(error);
        }
      };
      for (const node of [over.input, scope.input, unit.input, ...boxes.map((item) => item.box.input)]) node.addEventListener("change", size);
      size();
      const go = button("Start", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        threatsError.hidden = true;
        const done = await submit({ button: go, fields: { name, summary, scope, org_unit_id: unit }, banner: problem, run: async () => {
          try {
            return await post("/api/v1/risk-analyses", values());
          } catch (error) {
            const about = error.fields?.threats ?? error.fields?.categories;
            if (about) {
              threatsError.textContent = about;
              threatsError.hidden = false;
            }
            throw error;
          }
        } });
        if (!done) return;
        close();
        toast(`${done.data.ref} was started.`);
        navigate(`/risk-analyses/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("What it is", name.node, summary.node),
        section("What to look at", over.node, scope.node, unit.node),
        section("Which threats", h("p", { class: "muted" }, "Threats come from the risk library, by category. Each is a risk that could apply to a thing."),
          h("div", { class: "stack-sm", role: "group", "aria-label": "Kinds of threat" }, boxes.map((item) => item.box.node)), threatsError, sized)));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function analysisList(main) {
  const meta = TYPES.risk_analysis;
  return show(main, {
    title: meta.plural,
    load: async () => {
      const [page, unitIndex] = await Promise.all([get("/api/v1/risk-analyses", Object.fromEntries(query()), { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data) => {
      const rows = data.page.data;
      const mayStart = can("steward") || can("assess");
      const begin = async () => {
        const [programData, scopes, library] = await Promise.all([loadProgram(), get("/api/v1/scopes", { limit: 200, status: "active" }, { fresh: true }), get("/api/v1/risk-library")]);
        start({ programData, unitIndex: data.units, scopes: scopes.data, library: library.data });
      };
      const search = searchBox("Search risk analyses");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search), listTools(),
        filterSelect("status", [["", "Open and closed"], ["open", "Open"], ["closed", "Closed"]], "Status"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Analysis", "name"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Led by"),
          h("th", { scope: "col" }, "Answered"), h("th", { scope: "col" }, "Risks raised"), sortHeader("Status", "status"), sortHeader("Updated", "updated_at"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/risk-analyses/${row.ref}` }, row.name), h("div", { class: "cell-sub" }, row.ref)),
          h("td", {}, data.units.byId.get(row.org_unit_id)?.name ?? ""), ownerCell(row),
          h("td", { class: "numeric" }, `${row.considered} of ${row.items}`), h("td", { class: "numeric" }, String(row.raised)),
          h("td", {}, statusPill(row.status)), h("td", { class: "nowrap muted" }, relative(row.updated_at)))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: meta.iconName, title: "No risk analyses yet", text: meta.lede, action: mayStart ? button("Start a risk analysis", { kind: "btn-primary", onclick: begin }) : null });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Risks", title: meta.plural, lede: meta.lede,
          actions: mayStart ? button("Start a risk analysis", { kind: "btn-primary", iconName: "plus", onclick: begin }) : null }),
        bar, card({ title: plural(data.page.meta.total, "risk analysis", "risk analyses"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

function closing(record, reload) {
  if (record.status === "closed") {
    return card({ title: "What it found", actions: record.can_reopen ? button("Reopen", { kind: "btn-sm", onclick: async () => {
      await post(`/api/v1/risk-analyses/${record.ref}/reopen`);
      toast("Reopened.");
      reload();
    } }) : null }, prose(record.conclusion), h("p", { class: "subtle" }, `Closed ${date(record.closed_at)} by ${record.closed_by}.`));
  }
  if (!record.can_work) return null;
  const left = record.counts.pending;
  const conclusion = field("What the analysis found", { type: "textarea", rows: 4, hint: "A few sentences: what is new, what needs another look, and what was set aside. It heads the report." });
  const problem = banner();
  const go = button("Close the analysis", { kind: "btn-primary", disabled: left > 0 });
  go.addEventListener("click", async () => {
    const done = await submit({ button: go, fields: { conclusion }, banner: problem, run: () => post(`/api/v1/risk-analyses/${record.ref}/close`, { conclusion: conclusion.input.value }) });
    if (!done) return;
    toast("Closed. What it considered stays on record as its report.");
    reload();
  });
  return card({ title: "Close the analysis" }, h("div", { class: "stack" }, problem,
    left ? alert("info", `${plural(left, "question")} still ${left === 1 ? "has" : "have"} no answer. Each needs one before the analysis can be closed, so that the report says what was considered.`) : null,
    conclusion.node, h("div", {}, go)));
}

function reportTab(record, programData) {
  const groups = new Map();
  for (const item of record.items) {
    if (!groups.has(item.subject.ref)) groups.set(item.subject.ref, { subject: item.subject, items: [] });
    groups.get(item.subject.ref).items.push(item);
  }
  return h("div", { class: "stack-lg" },
    h("div", { class: "row no-print" }, h("p", { class: "muted grow" }, "Everything the analysis considered, thing by thing, with what was decided and why."),
      button("Print", { onclick: () => window.print() })),
    record.conclusion ? card({ title: "What it found" }, prose(record.conclusion)) : null,
    [...groups.values()].map((group) => card({ title: `${group.subject.name} · ${group.subject.ref}`, flush: true },
      h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Threat"), h("th", { scope: "col" }, "Decided"), h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "Why"), h("th", { scope: "col" }, "By"))),
        h("tbody", {}, group.items.map((item) => h("tr", {},
          h("td", { class: "cell-main" }, item.threat.title), h("td", {}, outcomePill(item.outcome)),
          h("td", {}, item.risk ? riskLink(item.risk, programData) : item.risk_hidden ? h("span", { class: "muted" }, "A risk you may not see") : ""),
          h("td", {}, item.note ?? ""),
          h("td", { class: "cell-sub" }, item.by ? [item.by, h("div", {}, h("time", { datetime: item.at, title: dateTime(item.at) }, date(item.at)))] : "")))))))));
}

export function analysisPage(main, params) {
  const tab = ["report", "history"].includes(query().get("tab")) ? query().get("tab") : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/risk-analyses/${params.ref}`;
      const [record, programData, unitIndex, vocab, entries] = await Promise.all([get(base, null, { fresh: true }), loadProgram(), units(), vocabularies(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { record: record.data, program: programData, units: unitIndex, vocab, history: entries?.data ?? [] };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const raised = record.items.filter((item) => item.outcome === "raised" && item.risk);
      const covered = [...new Map(record.items.filter((item) => item.outcome === "covered" && item.risk).map((item) => [item.risk.ref, item.risk])).values()];
      const next = record.assets.find((asset) => asset.pending);
      const overview = () => h("div", { class: "split" },
        h("div", { class: "stack-lg" },
          record.summary ? card({ title: "Why, and how" }, prose(record.summary)) : null,
          card({ title: "How far it has got", actions: record.can_work && next ? h("a", { class: "btn btn-primary btn-sm", href: `/risk-analyses/${record.ref}/${next.ref}` }, "Carry on") : null },
            progress(record.counts)),
          card({ title: "What it looks at", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Thing"), h("th", { scope: "col" }, "Answered"), h("th", { scope: "col" }, "Covered"), h("th", { scope: "col" }, "Raised"))),
            h("tbody", {}, record.assets.map((asset) => h("tr", {},
              h("td", {}, h("a", { class: "cell-main", href: `/risk-analyses/${record.ref}/${asset.ref}` }, asset.name),
                h("div", { class: "cell-sub" }, [TYPES[asset.type]?.label, asset.ref].filter(Boolean).join(" · "))),
              h("td", { class: "numeric nowrap" }, `${asset.considered} of ${asset.items}`, asset.pending ? null : [" ", icon("check", "icon icon-sm")]),
              h("td", { class: "numeric" }, String(asset.covered)), h("td", { class: "numeric" }, String(asset.raised)))))))),
          card({ title: "The threats it takes them against", flush: true }, h("ul", { class: "plain-list rows" }, record.threats.map((threat) => h("li", { class: "row" },
            h("span", { class: "grow" }, threat.title), h("span", { class: "muted numeric" }, `applies to ${threat.covered + threat.raised} of ${threat.items}`))))),
          raised.length || covered.length ? card({ title: "Risks" }, h("div", { class: "stack" },
            raised.length ? h("div", { class: "stack-sm" }, h("div", { class: "label" }, `Raised by this analysis (${raised.length})`),
              h("ul", { class: "plain-list stack-sm" }, raised.map((item) => h("li", {}, riskLink(item.risk, data.program))))) : null,
            covered.length ? h("div", { class: "stack-sm" }, h("div", { class: "label" }, `Already on the register, and looked at again (${covered.length})`),
              h("ul", { class: "plain-list stack-sm" }, covered.map((risk) => h("li", {}, riskLink(risk, data.program))))) : null)) : null,
          closing(record, reload)),
        h("div", { class: "stack-lg" },
          card({ title: "At a glance" }, facts([
            ["Over", record.scope ? h("a", { href: hrefOf(record.scope.ref) }, `${record.scope.name} (${record.scope.ref})`) : `Everything ${data.units.byId.get(record.org_unit_id)?.name ?? "the unit"} holds`],
            ["Unit", data.units.byId.get(record.org_unit_id)?.name ?? ""], ["Started", date(record.created_at)],
            ["Things", String(record.assets.length)], ["Threats", String(record.threats.length)], ["Questions", String(record.counts.items)]])),
          ownersCard(record, { vocab: data.vocab, units: data.units, reload })));
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [statusPill(record.status)] }),
        tabBar([["overview", "Overview"], ["report", "Report"], ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history)) : tab === "report" ? reportTab(record, data.program) : overview());
    },
  });
}

function answer(page, item, programData, redraw) {
  const base = `/api/v1/risk-analyses/${page.analysis.ref}/items/${item.id}`;
  const send = async (body) => {
    try {
      redraw((await post(base, body)).data);
    } catch (error) {
      toast(said(error));
    }
  };
  if (item.outcome !== "pending") {
    return h("div", { class: "stack-sm" },
      h("div", { class: "row-sm wrap" }, outcomePill(item.outcome), item.risk ? riskLink(item.risk, programData) : item.risk_hidden ? h("span", { class: "muted" }, "A risk you may not see") : null,
        page.can_work ? button("Change", { kind: "btn-sm btn-ghost", "aria-label": `Change the answer for ${item.threat.title}`, onclick: () => send({ outcome: "pending" }) }) : null),
      item.note ? h("p", {}, item.note) : null,
      h("div", { class: "cell-sub" }, `${item.by}, ${date(item.at)}`));
  }
  if (!page.can_work) return h("div", {}, outcomePill("pending"));
  const note = h("textarea", { class: "textarea", rows: 2, "aria-label": `Why, for ${item.threat.title}`, placeholder: "Why (it is kept in the report)" });
  const again = checkbox("Its rating needs another look", { hint: "Puts the risk's residual rating in doubt and tells its owners." });
  const search = h("input", { class: "input", type: "search", placeholder: "Another risk, by name or reference", "aria-label": `Find a risk that covers ${item.threat.title}` });
  const found = h("div", { class: "row-sm wrap", "aria-live": "polite" });
  const cover = (risk) => button(`Covered by ${risk.ref} ${risk.name}`, { kind: "btn-sm", onclick: () => send({ outcome: "covered", risk: risk.ref, note: note.value, look_again: again.input.checked }) });
  let timer = null;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const words = search.value.trim();
      if (!words) return found.replaceChildren();
      const rows = (await get("/api/v1/risks", { q: words, limit: 6, status: "open" })).data;
      return found.replaceChildren(...(rows.length ? rows.map(cover) : [h("span", { class: "muted" }, "No open risk you may see matches.")]));
    }, 250);
  });
  return h("div", { class: "stack-sm" },
    note,
    h("div", { class: "row-sm wrap" },
      button("Does not apply", { "aria-label": `${item.threat.title} does not apply`, onclick: () => send({ outcome: "not_applicable", note: note.value }) }),
      button("Raise a risk", { iconName: "plus", "aria-label": `Raise a risk for ${item.threat.title}`, onclick: () => send({ outcome: "raised", note: note.value }) })),
    h("details", { class: "fold" }, h("summary", {}, item.suggested.length ? `A risk already covers it (${item.suggested.length} likely)` : "A risk already covers it"),
      h("div", { class: "stack-sm" },
        item.suggested.length ? h("div", { class: "row-sm wrap" }, item.suggested.map(cover)) : null,
        search, found, again.node)));
}

export function analysisAsset(main, params) {
  return show(main, {
    title: params.subject,
    load: async () => {
      const [page, programData, unitIndex] = await Promise.all([get(`/api/v1/risk-analyses/${params.ref}/assets/${params.subject}`, null, { fresh: true }), loadProgram(), units()]);
      return { page: page.data, program: programData, units: unitIndex };
    },
    view: (data) => {
      const holder = h("div", { class: "stack-lg" });
      const draw = (page) => {
        const base = `/risk-analyses/${page.analysis.ref}`;
        const kind = TYPES[page.subject.type];
        const left = page.counts.pending;
        const restNote = h("input", { class: "input", type: "text", placeholder: "Why none of the rest apply", "aria-label": "Why none of the rest apply" });
        holder.replaceChildren(
          h("a", { class: "back-link", href: base }, icon("chevron-left", "icon icon-sm"), `${page.analysis.name} · ${page.analysis.ref}`),
          pageHeader({ eyebrow: `${kind?.label ?? "Thing"} · ${page.subject.ref}`, title: page.subject.name,
            lede: page.thing?.summary ?? null,
            actions: h("div", { class: "row-sm" },
              page.previous ? h("a", { class: "btn", href: `${base}/${page.previous}` }, icon("chevron-left", "icon icon-sm"), "Previous") : null,
              page.next ? h("a", { class: "btn", href: `${base}/${page.next}` }, "Next", icon("chevron-right", "icon icon-sm")) : h("a", { class: "btn", href: base }, "Back to the analysis")) }),
          h("div", { class: "row wrap" },
            h("span", { class: "muted" }, `${page.counts.considered} of ${page.counts.items} answered`),
            page.thing ? h("a", { href: hrefOf(page.subject.ref), target: "_blank", rel: "noopener" }, "Open its record") : h("span", { class: "muted" }, "Its record is no longer here, or is not yours to see."),
            page.analysis.status === "closed" ? pill("The analysis is closed") : null),
          card({ title: "Could this happen to it?", flush: true }, h("ul", { class: "plain-list rows" }, page.items.map((item) => h("li", { class: "question" },
            h("div", { class: "stack-sm" }, h("div", { class: "cell-main" }, item.threat.title),
              item.threat.event ? h("div", { class: "cell-sub" }, "What happens: ", item.threat.event) : null,
              item.threat.consequence ? h("div", { class: "cell-sub" }, "What follows: ", item.threat.consequence) : null),
            answer(page, item, data.program, draw))))),
          page.can_work && left ? card({ title: "The rest" }, h("div", { class: "row wrap" }, h("div", { class: "grow" }, restNote),
            button(`None of the other ${left} ${left === 1 ? "applies" : "apply"}`, { onclick: async () => {
              try {
                draw((await post(`/api/v1/risk-analyses/${page.analysis.ref}/assets/${page.subject.ref}/rest`, { note: restNote.value })).data);
              } catch (error) {
                toast(said(error));
              }
            } }))) : null);
      };
      draw(data.page);
      return holder;
    },
  });
}

