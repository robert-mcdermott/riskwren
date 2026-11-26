// Exceptions: the register, one exception with its decision, and the form that asks for one.

import { get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { banner, field, submit } from "../components/form.js";
import { EXCEPTION_STATE, exceptionState } from "../components/issue.js";
import { openOverlay } from "../components/overlay.js";
import { recordChip, TYPES } from "../components/record.js";
import { section } from "../components/record-forms.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, pager, searchBox, sortHeader } from "./records.js";

const TABS = [["overview", "Overview"], ["history", "History"]];
const iso = (day) => day.toISOString().slice(0, 10);

function footerOf(footer, save, close) {
  footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
  footer.hidden = false;
}

function covered(subject) {
  if (subject.type === "requirement") {
    const text = [h("span", { class: "requirement-code" }, subject.code ?? ""), " ", subject.code === subject.name ? "" : subject.name];
    return subject.framework ? h("a", { href: `/frameworks/${subject.framework.key}?r=${encodeURIComponent(subject.code)}` }, text) : h("span", {}, text);
  }
  return subject.ref ? recordChip(subject, { link: subject.open !== false }) : h("span", {}, subject.name);
}

/**
 * Ask for an exception. Give `scope` ({ ref, name }) with a `control` ({ ref, name }) or a
 * `requirement` ({ framework, code, title }); or `renews`, an exception to carry on from; or
 * `exception`, a request not yet decided, to reword it.
 */
export function requestException({ scope = null, control = null, requirement = null, renews = null, exception = null, onDone = null }) {
  const from = exception ?? renews;
  openOverlay({
    title: exception ? "Edit the request" : renews ? "Ask for it again" : "Ask for an exception",
    subtitle: from ? `${from.ref} · ${from.name}` : "A departure for a time, with what makes up for it.",
    render: (body, footer, close) => {
      const what = from ? covered(from.subject) : control ? recordChip({ ...control, type: "control" }, { link: false })
        : h("span", {}, h("span", { class: "requirement-code" }, requirement.code), " ", requirement.title ?? "");
      const where = from ? from.scope : scope;
      const today = new Date();
      const begins = renews ? new Date(new Date(renews.expires_on).getTime() + 86400000) : today;
      const start = field("From", { type: "date", value: exception?.starts_on ?? iso(begins > today ? begins : today) });
      const months = from?.max_months ?? 12;
      const end = field("Until", { type: "date", required: true, value: exception?.expires_on ?? "", hint: `At most ${plural(months, "month")}. After that it is asked for again.` });
      const why = field("Why it is needed", { type: "textarea", rows: 4, required: true, value: exception?.justification ?? "", hint: "What stands in the way, and what will change by the date it ends." });
      const instead = field("What makes up for it meanwhile", { type: "textarea", rows: 3, value: (exception ?? renews)?.compensating ?? "", hint: "What is done in its place while the exception runs." });
      const problem = banner();
      const save = button(exception ? "Save" : "Ask", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const values = { justification: why.input.value, compensating: instead.input.value || null, starts_on: start.input.value || null, expires_on: end.input.value || null };
        const done = await submit({ button: save, fields: { justification: why, compensating: instead, starts_on: start, expires_on: end }, banner: problem,
          run: () => (exception ? patch(`/api/v1/exceptions/${exception.ref}`, { version: exception.version, ...values })
            : post("/api/v1/exceptions", { ...values, ...(renews ? { renews: renews.ref }
              : { scope: scope?.ref ?? null, control: control?.ref ?? null, requirement: requirement ? { framework: requirement.framework, code: requirement.code } : null }) })) });
        if (!done) return;
        close();
        toast(exception ? "Saved." : `${done.data.ref} was requested. Someone with authority over the unit decides it.`);
        if (onDone) onDone(done.data);
        else navigate(`/exceptions/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("What it is an exception to", h("p", {}, what), where ? h("p", { class: "subtle" }, `Within ${where.name}.`) : h("p", { class: "subtle" }, "Wherever the control is relied on.")),
        section("Why, and what instead", why.node, instead.node),
        section("For how long", h("div", { class: "grid-2" }, start.node, end.node),
          h("p", { class: "subtle" }, "While it is in force, what it covers is shown as excepted. The day after it ends, the state underneath is back, without anyone doing anything."))));
      footerOf(footer, save, close);
    },
  });
}

function decide(item, reload) {
  openOverlay({
    title: "Decide this request",
    subtitle: `${item.ref} · ${item.name}`,
    render: (body, footer, close) => {
      const until = field("Until", { type: "date", value: item.expires_on, hint: "It can be approved for less time than was asked." });
      const note = field("Note", { type: "textarea", rows: 3, hint: "Needed to refuse it: say why." });
      const problem = banner();
      const yes = button("Approve", { kind: "btn-primary" });
      const no = button("Refuse");
      const send = (approve, pressed) => async () => {
        const done = await submit({ button: pressed, fields: { note, expires_on: until }, banner: problem,
          run: () => post(`/api/v1/exceptions/${item.ref}/decision`, { approve, note: note.input.value || null, expires_on: approve ? until.input.value || null : null }) });
        if (done) {
          close();
          toast(approve ? `Approved until ${date(done.data.expires_on)}.` : "Refused.");
          reload();
        }
      };
      yes.addEventListener("click", send(true, yes));
      no.addEventListener("click", send(false, no));
      body.append(h("div", { class: "stack-lg" }, problem,
        section("What is asked", facts([["Exception to", covered(item.subject)], ["Within", item.scope?.name ?? "Wherever the control is relied on"],
          ["Asked by", `${item.requested_by}, ${date(item.requested_at)}`], ["From", date(item.starts_on)]]),
        h("div", {}, h("div", { class: "label" }, "Why it is needed"), prose(item.justification)),
        h("div", {}, h("div", { class: "label" }, "What makes up for it"), item.compensating ? prose(item.compensating) : h("p", { class: "muted" }, "Nothing is offered in its place."))),
        until.node, note.node));
      footer.replaceChildren(h("div", { class: "row" }, yes, no, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function withdraw(item, reload) {
  const approved = item.status === "approved";
  openOverlay({
    kind: "dialog",
    title: approved ? "End this exception early?" : "Take back this request?",
    subtitle: `${item.ref} · ${item.name}`,
    render: (body, footer, close) => {
      const reason = field("Why", { type: "textarea", rows: 3, required: approved });
      const problem = banner();
      const save = button(approved ? "End it" : "Take it back", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { reason }, banner: problem, run: () => post(`/api/v1/exceptions/${item.ref}/withdrawal`, { reason: reason.input.value || null }) });
        if (done) {
          close();
          toast("Withdrawn.");
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        approved ? h("p", { class: "muted" }, "What it covers goes back at once to the state underneath.") : null, reason.node));
      footerOf(footer, save, close);
    },
  });
}

function overview(item, ctx) {
  const state = item.state;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      state === "requested" ? alert("info", icon("info"), h("div", {}, "Not yet decided. It covers nothing until someone with authority over the unit, who did not ask for it, approves it.")) : null,
      state === "expiring" ? alert("warn", icon("alert"), h("div", {}, `This ends on ${date(item.expires_on)}. If it is still needed, ask again before then.`)) : null,
      state === "expired" ? alert("info", icon("info"), h("div", {}, `This ended on ${date(item.expires_on)}. What it covered is back to the state underneath.`)) : null,
      card({ title: "What it is an exception to" }, h("p", {}, covered(item.subject)),
        h("p", { class: "subtle" }, item.scope ? ["Within ", h("a", { href: `/scopes/${item.scope.ref}?tab=requirements` }, item.scope.name), "."] : "Wherever the control is relied on.")),
      card({ title: "Why it is needed" }, prose(item.justification)),
      card({ title: "What makes up for it meanwhile" }, item.compensating ? prose(item.compensating) : h("p", { class: "muted" }, "Nothing is offered in its place.")),
      item.decided_by ? card({ title: item.status === "refused" ? "Refused" : item.status === "withdrawn" ? "Withdrawn" : "Approved" },
        item.decision_note ? prose(item.decision_note) : null, h("p", { class: "subtle" }, `Decided by ${item.decided_by} on ${date(item.decided_at)}.`)) : null),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Standing", exceptionState(state)],
        ["From", date(item.starts_on)],
        ["Until", date(item.expires_on)],
        ["Asked by", `${item.requested_by}, ${date(item.requested_at)}`],
        ["Unit", ctx.units.byId.get(item.org_unit_id)?.name],
        ["Carries on from", item.renews ? h("a", { href: `/exceptions/${item.renews.ref}` }, item.renews.ref) : null],
        ["Asked for again", item.renewed_by ? h("a", { href: `/exceptions/${item.renewed_by.ref}` }, item.renewed_by.ref) : null],
      ])),
      ownersCard({ ...item, can: { edit: false } }, ctx)));
}

export function exceptionPage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/exceptions/${params.ref}`;
      const [item, vocab, unitIndex, extra] = await Promise.all([get(base, null, { fresh: true }), vocabularies(), units(),
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null]);
      return { item: { ...item.data, type: "exception" }, vocab, units: unitIndex, extra: extra?.data ?? [] };
    },
    view: (data, reload) => {
      const item = data.item;
      document.title = `${item.name} · ${item.ref}`;
      const can = item.can_act;
      const actions = h("div", { class: "row wrap" },
        can.decide ? button("Decide", { kind: "btn-primary", onclick: () => decide(item, reload) }) : null,
        can.renew ? button("Ask again", { kind: item.state === "expiring" ? "btn-primary" : "", onclick: () => requestException({ renews: item }) }) : null,
        item.can.edit ? button("Edit", { iconName: "edit", onclick: () => requestException({ exception: item, onDone: reload }) }) : null,
        can.withdraw ? button(item.status === "approved" ? "End it early" : "Take it back", { kind: "btn-ghost", onclick: () => withdraw(item, reload) }) : null);
      return h("div", { class: "stack" },
        recordHeader(item, { badges: [exceptionState(item.state)], actions }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : overview(item, { vocab: data.vocab, units: data.units, reload }));
    },
  });
}

export function exceptionList(main) {
  const meta = TYPES.exception;
  return show(main, {
    title: "Exceptions",
    load: async () => {
      const [page, unitIndex] = await Promise.all([get("/api/v1/exceptions", Object.fromEntries(query()), { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data) => {
      const rows = data.page.data;
      const search = searchBox("Search exceptions");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("state", [["", "Any standing"], ...["requested", "in_force", "expired", "refused", "withdrawn"].map((key) => [key, EXCEPTION_STATE[key][0]])], "Standing"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Exception", "name", "expires_on"), h("th", { scope: "col" }, "To"), h("th", { scope: "col" }, "Within"), h("th", { scope: "col" }, "Asked by"),
          sortHeader("Until", "expires_on", "expires_on"), h("th", { scope: "col" }, "Standing"))),
        h("tbody", {}, rows.map((r) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/exceptions/${r.ref}` }, r.name), h("div", { class: "cell-sub" }, r.ref)),
          h("td", {}, r.subject.type === "requirement" ? h("span", { class: "requirement-code" }, r.subject.code ?? r.subject.name) : r.subject.name),
          h("td", {}, r.scope ? h("a", { href: `/scopes/${r.scope.ref}` }, r.scope.name) : h("span", { class: "subtle" }, "Everywhere")),
          h("td", {}, r.requested_by, r.decided_by ? h("div", { class: "cell-sub" }, `Decided by ${r.decided_by}`) : null),
          h("td", { class: "nowrap" }, date(r.expires_on)),
          h("td", {}, exceptionState(r.state)))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "exception", title: "No exceptions", text: `${meta.lede} One is asked for from a scope: from a requirement on its Requirements tab, or a control on its Controls tab.` });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Compliance", title: "Exceptions", lede: meta.lede }),
        bar,
        card({ title: plural(data.page.meta.total, "exception"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
