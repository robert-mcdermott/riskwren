// Incidents: report something in one short form, see those you may, and triage and handle
// them. A reporter sees what they reported, where it stands, and what is said to them; those
// handling it see the rest.

import { get, post, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime, plural } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query } from "../core/router.js";
import { session } from "../core/session.js";
import { banner, field, section, select, submit } from "../components/form.js";
import { recordPicker, severityPill } from "../components/issue.js";
import { KIND, reportFields } from "../components/incident-report.js";
import { openOverlay } from "../components/overlay.js";
import { peoplePicker, personField } from "../components/people-picker.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, pager, searchBox, sortHeader } from "./records.js";

const STATUS = { reported: ["Waiting for triage", "warn"], handling: ["Being handled", "info"], closed: ["Closed", ""] };
const SUBJECTS = ["system", "service", "information", "third_party", "process", "risk", "control", "scope"];
const statusOf = (status) => pill(STATUS[status]?.[0] ?? status, STATUS[status]?.[1] ?? "");
const kindOf = (kind) => pill(KIND[kind]?.[0] ?? kind);

// --- Reporting ----------------------------------------------------------------------------------

export function incidentNew(main, meta) {
  return show(main, {
    title: "Report something",
    load: async () => ({ units: await units() }),
    view: (data) => {
      const mine = session()?.member_units ?? [];
      const form = reportFields({ unitIndex: data.units, unitValue: mine.find((id) => data.units.byId.has(id)) ?? "" });
      const problem = banner();
      const send = button("Send the report", { kind: "btn-primary" });
      send.addEventListener("click", async () => {
        const done = await submit({ button: send, banner: problem, fields: form.fields, run: () => post("/api/v1/incidents", form.values()) });
        if (!done) return;
        toast(`Sent as ${done.data.ref}. Those who triage it have been told.`);
        navigate(`/incidents/${done.data.ref}`);
      });
      return h("div", { class: "stack-lg narrow" },
        pageHeader({ eyebrow: "Incidents", title: "Report something",
          lede: "An incident, a near miss, or a concern: it takes a minute. It goes to those who triage for its unit, and is seen only by them, by whoever handles it, by the unit's leaders, and by you." }),
        card({}, h("div", { class: "stack" }, problem, ...form.nodes, h("div", { class: "row" }, send, h("a", { class: "btn btn-ghost", href: "/incidents" }, "Cancel")))),
        meta?.report_without_name ? alert("info", "If you would rather not give your name, ", h("a", { href: "/report" }, "report it without one"),
          ". Nothing about who sent it is kept, and a code lets you follow it up.") : null);
    },
  });
}

// --- The list ------------------------------------------------------------------------------------

export function incidentList(main) {
  return show(main, {
    title: "Incidents",
    load: async () => {
      const [page, unitIndex, vocab] = await Promise.all([get("/api/v1/incidents", Object.fromEntries(query()), { fresh: true }), units(), vocabularies()]);
      return { page, units: unitIndex, vocab };
    },
    view: (data) => {
      const rows = data.page.data;
      const search = searchBox("Search incidents");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("status", [["", "Every status"], ["live", "Open"], ["reported", "Waiting for triage"], ["handling", "Being handled"], ["closed", "Closed"]], "Status"),
        filterSelect("kind", [["", "Every kind"], ...Object.entries(KIND).map(([key, [text]]) => [key, text])], "Kind"),
        filterSelect("category", options(data.vocab, "incident_categories", { blank: "Every category" }), "Category"),
        filterSelect("reported", [["", "Anyone's"], ["true", "Reported by me"]], "Reported by"));
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Incident", "name"), h("th", { scope: "col" }, "Kind"), h("th", { scope: "col" }, "Category"),
          h("th", { scope: "col" }, "Severity"), h("th", { scope: "col" }, "Status"), sortHeader("Reported", "created_at"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/incidents/${row.ref}` }, row.name),
            h("div", { class: "cell-sub" }, [row.ref, data.units.byId.get(row.org_unit_id)?.name].filter(Boolean).join(" · "))),
          h("td", {}, KIND[row.kind]?.[0] ?? row.kind),
          h("td", {}, row.category ? label(data.vocab, "incident_categories", row.category) : h("span", { class: "subtle" }, "Not yet")),
          h("td", {}, row.severity ? severityPill(row.severity) : h("span", { class: "subtle" }, "Not yet")),
          h("td", {}, statusOf(row.status), row.restricted ? h("div", { class: "cell-sub" }, "Restricted case") : null),
          h("td", {}, date(row.reported_at), row.anonymous ? h("div", { class: "cell-sub" }, "Without a name") : null))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "alert", title: "Nothing reported that you can see", text: "What you report appears here, with where it stands." });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Incidents", title: "Incidents", lede: "Incidents, near misses, and concerns: what you reported, and those you triage, handle, or lead the unit of.",
          actions: h("a", { class: "btn btn-primary", href: "/incidents/new" }, "Report something") }),
        bar, card({ title: plural(data.page.meta.total, "report"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

// --- One incident --------------------------------------------------------------------------------

function triageForm(record, data, reload) {
  openOverlay({ title: record.triaged ? "Triage again" : "Triage", subtitle: "Its category, how serious it is, what it concerns, and who handles it.",
    render: (body, footer, close) => {
      const category = select("Category", options(data.vocab, "incident_categories", { blank: "Choose…" }), { value: record.category ?? "", required: true });
      const severity = select("Severity", options(data.vocab, "issue_severities", { blank: "Choose…" }), { value: record.severity ?? "", required: true,
        hint: "On the same scale as issues: how much harm it has done or could do." });
      const unit = select("Unit", unitOptions(data.units.tree), { value: record.org_unit_id });
      const chosen = [...(record.subjects?.records ?? [])];
      const picker = recordPicker({ types: SUBJECTS, chosen, label: "The records it concerns", placeholder: "Search systems, information, third parties, risks…", empty: "None yet." });
      const owner = record.owners.find((each) => each.kind === "owner");
      const handler = personField("Who handles it", { value: owner ? { account_id: owner.account_id, name: owner.name } : null });
      const problem = banner();
      const save = button("Save the triage", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { category, severity, org_unit_id: unit, handler_id: handler },
          run: () => post(`/api/v1/incidents/${record.ref}/triage`, { category: category.input.value || null, severity: severity.input.value || null,
            org_unit_id: Number(unit.input.value), subjects: chosen.map((each) => each.ref), handler_id: handler.value() }) });
        if (!done) return;
        close();
        toast("Triaged. Whoever handles it has been told.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("What it is", category.node, severity.node, unit.node),
        section("Records", picker),
        section("Handling", handler.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function closeForm(record, reload) {
  openOverlay({ title: `Close ${record.ref}`, render: (body, footer, close) => {
    const note = field("How it ended", { type: "textarea", rows: 4, required: true, hint: "What was done, and what was found. Whoever reported it is told it is closed." });
    const problem = banner();
    const save = button("Close it", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { note }, run: () => post(`/api/v1/incidents/${record.ref}/close`, { note: note.input.value }) });
      if (!done) return;
      close();
      toast("Closed.");
      reload();
    });
    body.append(h("div", { class: "stack" }, problem, note.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function caseForm(record, reload) {
  const case_ = record.case;
  openOverlay({ title: case_.restricted ? "Who is named on the case" : "Restrict it to those named",
    subtitle: "A restricted case is known only to those named on it, its handlers, and whoever reported it.",
    render: (body, footer, close) => {
      const members = case_.members.map((each) => ({ ...each }));
      const list = h("ul", { class: "plain-list stack-sm", "aria-label": "People named on the case" });
      const draw = () => list.replaceChildren(...(members.length ? members.map((person, index) => h("li", { class: "row" },
        h("span", { class: "grow" }, h("span", { class: "cell-main" }, person.name), h("span", { class: "cell-sub" }, ` ${person.email ?? ""}`)),
        button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${person.name}`, onclick: () => {
          members.splice(index, 1);
          draw();
        } }))) : [h("li", { class: "muted" }, "Nobody besides its handlers, and you.")]));
      const picker = peoplePicker({ label: "Name someone", exclude: (account) => members.some((each) => each.account_id === account.id),
        onPick: (account) => {
          members.push({ account_id: account.id, name: account.display_name, email: account.email });
          draw();
        } });
      draw();
      const problem = banner();
      const save = button(case_.restricted ? "Save" : "Restrict it", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/incidents/${record.ref}/case`, { restricted: true, members: members.map((each) => each.account_id) }) });
        if (!done) return;
        close();
        toast(case_.restricted ? "Saved." : "Restricted. Only those named on it know it exists.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        alert("warn", "Everyone not named loses sight of it at once: its unit's leaders and stewards, those who triage, and those who read everything. The notices that told them of it are taken back, though one already sent as email cannot be. You are named too, so that you keep sight of it."),
        section("Named on the case", list, picker)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

function caseCard(record, reload) {
  const case_ = record.case;
  const change = case_.can_change;
  const lift = () => openOverlay({ title: "Lift the restriction?", render: (body, footer, close) => {
    const problem = banner();
    const go = button("Lift it", { kind: "btn-primary" });
    go.addEventListener("click", async () => {
      const done = await submit({ button: go, banner: problem,
        run: () => put(`/api/v1/incidents/${record.ref}/case`, { restricted: false, members: case_.members.map((each) => each.account_id) }) });
      if (!done) return;
      close();
      toast("The restriction is lifted.");
      reload();
    });
    body.append(h("div", { class: "stack" }, problem,
      h("p", {}, "Its unit's leaders and stewards, those who triage for its unit, and those who read everything will see it, with all that has been written on it and its history.")));
    footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
  return card({ title: "Who sees it", actions: case_.restricted ? pill("Restricted case", "warn") : null },
    h("div", { class: "stack" },
      h("p", { class: "muted" }, case_.restricted
        ? "Only those named here, its handlers, and whoever reported it know it exists."
        : "Its reporter, its handlers, those who triage for its unit, the unit's leaders and stewards, and those who read everything."),
      case_.restricted ? (case_.members.length ? h("ul", { class: "plain-list stack-sm" }, case_.members.map((each) => h("li", {}, each.name)))
        : h("p", { class: "muted" }, "Nobody is named besides its handlers.")) : null,
      change ? h("div", { class: "row wrap" },
        button(case_.restricted ? "Change who is named" : "Restrict it", { kind: "btn-sm", onclick: () => caseForm(record, reload) }),
        case_.restricted ? button("Lift the restriction", { kind: "btn-ghost btn-sm", onclick: lift }) : null) : null));
}

function said(message) {
  const who = message.from_reporter ? "From the reporter" : message.shared ? "To the reporter" : "Note";
  return h("li", { class: "message" },
    h("div", { class: "row wrap" }, h("span", { class: "cell-main" }, message.by), pill(who, message.shared ? "info" : ""),
      h("span", { class: "subtle" }, dateTime(message.at))),
    prose(message.body));
}

function conversation(record, reload) {
  const list = record.messages.length ? h("ol", { class: "plain-list stack messages" }, record.messages.map(said))
    : h("p", { class: "muted" }, record.everything ? "Nothing written yet." : "Nothing has been said to you yet. Anything you add here goes to those handling it.");
  if (!record.can_act.message) return card({ title: "What has been said" }, list);
  const text = field(record.everything ? "Write" : "Add something", { type: "textarea", rows: 3, maxlength: 10000 });
  const who = record.everything && (record.reporter || record.anonymous)
    ? select("Who reads it", [["note", "Only those handling it"], ["shared", "The reporter too"]], { value: "note" }) : null;
  const problem = banner();
  const send = button("Send", { kind: "btn-primary" });
  send.addEventListener("click", async () => {
    const done = await submit({ button: send, banner: problem, fields: { body: text },
      run: () => post(`/api/v1/incidents/${record.ref}/messages`, { body: text.input.value, shared: who ? who.input.value === "shared" : !record.everything }) });
    if (!done) return;
    toast("Sent.");
    reload();
  });
  return card({ title: "What has been said" }, h("div", { class: "stack" }, list, problem, text.node, who?.node, h("div", {}, send)));
}

export function incidentPage(main, params) {
  const tab = ["history", "breach"].includes(query().get("tab")) ? query().get("tab") : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/incidents/${params.ref}`;
      const [record, unitIndex, vocab] = await Promise.all([get(base, null, { fresh: true }), units(), vocabularies()]);
      const entries = tab === "history" && record.data.everything ? await get(`${base}/history`, null, { fresh: true }) : null;
      const breach = tab === "breach" && record.data.everything
        ? await Promise.all([get(`${base}/breach`, null, { fresh: true }), import("./incident-breach.js")]) : null;
      return { record: record.data, units: unitIndex, vocab, history: entries?.data ?? [], breach };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const act = record.can_act;
      const unitName = data.units.byId.get(record.org_unit_id)?.name;
      const actions = h("div", { class: "row wrap" },
        act.triage ? button(record.triaged ? "Triage again" : "Triage", { kind: record.triaged ? "" : "btn-primary", onclick: () => triageForm(record, data, reload) }) : null,
        act.close ? button("Close", { onclick: () => closeForm(record, reload) }) : null,
        act.reopen ? button("Reopen", { onclick: async () => {
          await post(`/api/v1/incidents/${record.ref}/reopen`, {});
          toast("Reopened.");
          reload();
        } }) : null);
      const badges = [kindOf(record.kind), statusOf(record.status), record.severity ? severityPill(record.severity) : null].filter(Boolean);
      const header = recordHeader(record, { badges, actions });
      if (!record.everything) {
        const handlers = record.owners.filter((each) => each.kind === "owner").map((each) => each.name);
        return h("div", { class: "stack" }, header,
          alert("info", "You reported this. You see what you reported, where it stands, and what is said to you; those handling it see the rest."),
          h("div", { class: "split" },
            h("div", { class: "stack-lg" },
              card({ title: "What you reported" }, h("div", { class: "stack" }, prose(record.summary),
                facts([["When it happened", record.occurred_on ? date(record.occurred_on) : null], ["Where", record.location]]))),
              conversation(record, reload)),
            card({ title: "Where it stands" }, facts([
              ["Status", statusOf(record.status)],
              ["Reported", dateTime(record.created_at)],
              ["Handled by", handlers.join(", ") || null],
              ["Closed", record.closed_at ? dateTime(record.closed_at) : null],
            ]))));
      }
      const subjects = record.subjects;
      const waiting = record.status === "reported"
        ? alert("warn", h("strong", {}, "Waiting for triage. "), act.triage ? "Give it a category, a severity, what it concerns, and who handles it." : "Those who triage for its unit have been told.") : null;
      const overview = h("div", { class: "split" },
        h("div", { class: "stack-lg" },
          waiting,
          card({ title: "What happened" }, h("div", { class: "stack" }, prose(record.summary),
            facts([["When it happened", record.occurred_on ? date(record.occurred_on) : "Not known"], ["Where", record.location]]))),
          card({ title: "What it concerns" }, subjects.records.length
            ? h("div", { class: "row wrap" }, subjects.records.map((chip) => recordChip(chip)))
            : h("p", { class: "muted" }, record.triaged ? "No records named." : "Named at triage."),
          subjects.hidden ? h("p", { class: "subtle" }, `And ${plural(subjects.hidden, "record")} you do not have access to.`) : null),
          conversation(record, reload),
          record.closure_note ? card({ title: "How it ended" }, prose(record.closure_note)) : null),
        h("div", { class: "stack-lg" },
          card({ title: "At a glance" }, facts([
            ["Status", statusOf(record.status)],
            ["Kind", KIND[record.kind]?.[0]],
            ["Category", record.category ? label(data.vocab, "incident_categories", record.category) : "Not yet"],
            ["Severity", record.severity ? severityPill(record.severity) : "Not yet"],
            ["Unit", unitName],
            ["Reported by", record.anonymous ? "Someone without a name" : record.reporter?.name],
            ["Reported", dateTime(record.created_at)],
            ["Triaged", record.triaged ? `${dateTime(record.triaged.at)} by ${record.triaged.by}` : null],
            ["Closed", record.closed_at ? dateTime(record.closed_at) : null],
          ])),
          caseCard(record, reload),
          // Until it is triaged nobody handles it, and triage names who does.
          ownersCard({ ...record, orphaned: record.orphaned && record.triaged != null },
            { vocab: data.vocab, units: data.units, reload, ownersTitle: "Who handles it" })));
      return h("div", { class: "stack" }, header,
        tabBar([["overview", "Overview"], ["breach", "Breach assessment"], ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history))
          : data.breach ? data.breach[1].breachTab(record, data.breach[0].data, data.vocab, reload) : overview);
    },
  });
}
