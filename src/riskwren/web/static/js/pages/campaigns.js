// Campaigns: asking a set of people for one thing by a date. Whoever runs one sees who has
// answered and coverage by unit; whoever is asked sees the one thing asked of them.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { unitOptions, units } from "../core/lookups.js";
import { navigate, query, setQuery } from "../core/router.js";
import { segments } from "../components/charts.js";
import { banner, field, select, submit } from "../components/form.js";
import { closeOverlay, confirmAction, openOverlay } from "../components/overlay.js";
import { asAsked, questionnaireForm } from "../components/questionnaire.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const STATUS = { open: ["Open", "info"], closed: ["Closed", ""], cancelled: ["Cancelled", ""] };
const ITEM = { pending: ["Waiting", "warn"], done: ["Answered", "ok"], excused: ["Excused", ""] };
const OUTCOMES = { yes: "Operates as described", partly: "Operates only partly", no: "Does not operate", stands: "Still stands, rating right",
  no_longer_stands: "No longer stands", rating_not_right: "Rating no longer right", complete: "Records complete", gaps: "Records need attention", attached: "Evidence attached" };
const statusPill = (campaign) => (campaign.overdue ? pill("Overdue", "danger") : pill(...STATUS[campaign.status]));

function bar(percent, label) {
  const fill = h("i");
  fill.style.setProperty("width", `${percent}%`);
  return h("span", { class: "coverage-bar", role: "img", "aria-label": label }, fill);
}

export function campaignList(main) {
  return show(main, {
    title: "Campaigns",
    load: async () => (await get("/api/v1/campaigns", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Compliance", title: "Campaigns",
        lede: "Ask the owners of controls to attest, the owners of risks to look again, stewards to check their unit's records, or anyone for a piece of evidence, by a date. Then see who has answered.",
        actions: data.can_start ? button("Start a campaign", { kind: "btn-primary", iconName: "plus", onclick: () => startOne(data.kinds) }) : null }),
      data.campaigns.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Campaign"), h("th", { scope: "col" }, "Asks"), h("th", { scope: "col" }, "Due"),
          h("th", { scope: "col" }, "Answered"), h("th", { scope: "col" }, "Status"))),
        h("tbody", {}, data.campaigns.map((item) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/campaigns/${item.ref}` }, item.name),
            h("div", { class: "cell-sub" }, `${item.ref} · ${item.kind_label}${item.scope ? ` · ${item.scope.name}` : item.unit ? ` · ${item.unit.name}` : ""}`)),
          h("td", {}, item.asks),
          h("td", {}, date(item.due_on)),
          h("td", {}, h("div", { class: "stack-sm" }, `${item.counts.done} of ${item.counts.asked}`, bar(item.answered, `${item.answered}% answered`))),
          h("td", {}, statusPill(item))))))))
        : card({}, emptyState({ iconName: "bell", title: "No campaigns yet",
          text: data.can_start ? "Start one to ask many people the same thing by a date, and see coverage by unit as answers come in."
            : "What you have been asked is on your Home page." }))),
  });
}

function startOne(kinds) {
  openOverlay({ title: "Start a campaign", render: async (body) => {
    const [unitIndex, scopes, asking] = await Promise.all([units(), get("/api/v1/scopes", { limit: 200 }),
      get("/api/v1/documents", { acknowledge: true, status: "active", limit: 200 })]);
    const kind = select("What to ask", kinds.map((each) => [each.key, `${each.label}: ${each.asks.toLowerCase()}`]));
    const name = field("Name", { required: true, hint: "As people will see it, such as “Control attestation, spring 2027”." });
    const due = field("Answers due", { type: "date", required: true });
    const unit = select("About what lies in", unitOptions(unitIndex.tree, { blank: "The whole organization" }), { hint: "The unit and everything beneath it." });
    const scope = select("Or only the controls a scope uses", [["", "Not limited to a scope"], ...scopes.data.map((each) => [each.ref, `${each.name} (${each.ref})`])]);
    const doc = select("Which document", [["", asking.data.length ? "Choose…" : "No published document asks to be acknowledged"],
      ...asking.data.map((each) => [each.ref, `${each.name} (${each.ref}), version ${each.number}`])],
      { required: true, hint: "Only the people it applies to are asked, and those who have acknowledged it already are counted as done." });
    const wanted = field("What evidence is wanted", { type: "textarea", rows: 2, required: true, hint: "Each owner is asked for this. Their request closes when evidence is attached to the control." });
    const summary = field("A note to those asked", { type: "textarea", rows: 2 });
    const who = h("p", { class: "muted", "aria-live": "polite" });
    const problem = banner();
    const save = button("Start, and tell those asked", { kind: "btn-primary", type: "submit" });
    const values = () => ({ kind: kind.input.value, name: name.input.value, due_on: due.input.value, summary: summary.input.value || null,
      org_unit_id: scope.input.value ? null : Number(unit.input.value) || null, scope: scope.input.value || null, wanted: wanted.input.value || null,
      document: doc.input.value || null });
    const sync = async () => {
      const chosen = kinds.find((each) => each.key === kind.input.value);
      scope.node.hidden = !chosen.by_scope;
      if (!chosen.by_scope) scope.input.value = "";
      unit.node.hidden = Boolean(scope.input.value);
      wanted.node.hidden = chosen.key !== "evidence";
      doc.node.hidden = chosen.key !== "acknowledgment";
      if (chosen.key === "acknowledgment" && !doc.input.value) {
        who.textContent = "Choose the document.";
        return;
      }
      try {
        const found = (await post("/api/v1/campaigns/preview", { ...values(), name: "preview", due_on: "2999-01-01", wanted: "preview" })).data;
        who.textContent = found.items ? `This would ask ${plural(found.people, "person", "people")} about ${plural(found.items, "thing")} in ${plural(found.units, "unit")}.`
          + (found.nobody_to_ask ? ` ${found.nobody_to_ask} ${found.nobody_to_ask === 1 ? "has" : "have"} nobody to ask, and will show as such.` : "")
          : "There is nobody to ask.";
      } catch (error) {
        who.textContent = error.detail ?? "";
      }
    };
    for (const each of [kind, unit, scope, doc]) each.input.addEventListener("change", sync);
    body.append(h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
      event.preventDefault();
      const done = await submit({ button: save, fields: { kind, name, due_on: due, org_unit_id: unit, scope, wanted, document: doc }, banner: problem,
        run: () => post("/api/v1/campaigns", values()) });
      if (done) {
        closeOverlay();
        toast(`${done.data.ref} is started.`);
        navigate(`/campaigns/${done.data.ref}`);
      }
    } }, problem, kind.node, doc.node, name.node, due.node, unit.node, scope.node, wanted.node, summary.node, who, h("div", {}, save)));
    await sync();
  } });
}

function itemsTable(campaign, shown) {
  if (!shown.length) return h("p", { class: "muted pad" }, "Nothing here.");
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "About"), h("th", { scope: "col" }, "Asked"), h("th", { scope: "col" }, "Status"), h("th", { scope: "col" }, "Answer"))),
    h("tbody", {}, shown.map((item) => h("tr", {},
      h("td", {}, item.subject.href ? h("a", { class: "cell-main", href: item.subject.href }, item.subject.name) : h("span", { class: "cell-main" }, item.subject.name),
        item.subject.ref ? h("div", { class: "cell-sub mono" }, item.subject.ref) : null),
      h("td", {}, item.asked ?? h("span", { class: "text-danger" }, "Nobody to ask")),
      h("td", {}, pill(...ITEM[item.status])),
      h("td", {}, item.status === "done" ? h("a", { href: `/campaign-items/${item.id}` }, OUTCOMES[item.outcome] ?? "Read it")
        : item.status === "excused" ? h("span", { class: "subtle" }, item.note)
          : item.can_answer ? h("a", { href: `/campaign-items/${item.id}` }, "Answer") : ""))))));
}

export function campaignPage(main, params) {
  const filter = ["pending", "done", "excused"].includes(query().get("show")) ? query().get("show") : "all";
  return show(main, {
    title: params.ref,
    load: async () => (await get(`/api/v1/campaigns/${params.ref}`, null, { fresh: true })).data,
    view: (campaign, reload) => {
      const act = (path, done) => async () => {
        await post(`/api/v1/campaigns/${campaign.ref}/${path}`, {});
        toast(done);
        reload();
      };
      const remind = button("Remind those who have not answered", { onclick: async () => {
        const told = (await post(`/api/v1/campaigns/${campaign.ref}/remind`, {})).data.reminded;
        toast(told ? `Reminded ${plural(told, "person", "people")}.` : "There is nobody left to remind.");
      } });
      const shown = campaign.items.filter((item) => filter === "all" || item.status === filter);
      const tabs = [["all", `Everything (${campaign.items.length})`], ["pending", `Waiting (${campaign.counts.pending})`], ["done", `Answered (${campaign.counts.done})`],
        ...(campaign.counts.excused ? [["excused", `Excused (${campaign.counts.excused})`]] : [])];
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: "/campaigns" }, icon("chevron-left", "icon icon-sm"), "Campaigns"),
        pageHeader({ eyebrow: `${campaign.kind_label} · ${campaign.ref}`, title: campaign.name, lede: campaign.summary ?? campaign.wanted,
          actions: campaign.can.run ? h("div", { class: "row-sm wrap" }, remind,
            button("Close", { onclick: () => confirmAction({ title: "Close this campaign?", text: "What has been answered is kept. Nobody else will be asked.", confirmLabel: "Close it", run: act("close", "Closed.") }) }),
            button("Cancel it", { kind: "btn-ghost", onclick: () => confirmAction({ title: "Cancel this campaign?", text: "For one started in error. Answers already given are kept on record.", confirmLabel: "Cancel it", danger: true, run: act("cancel", "Cancelled.") }) })) : null }),
        h("div", { class: "row-sm wrap" }, statusPill(campaign), h("span", { class: "muted" },
          `${campaign.asks} · due ${date(campaign.due_on)} · started by ${campaign.started_by} on ${date(campaign.started_at)}`,
          campaign.scope ? ` · the controls of ${campaign.scope.name}` : campaign.unit ? ` · ${campaign.unit.name} and beneath` : " · the whole organization",
          campaign.document ? [" · ", h("a", { href: `/documents/${campaign.document.ref}?tab=acknowledgments` }, `${campaign.document.ref} ${campaign.document.name}`)] : "",
          campaign.questionnaire ? [" · asks ", h("a", { href: `/questionnaires/${campaign.questionnaire.key}?tab=questions&version=${campaign.questionnaire.version}` }, `${campaign.questionnaire.title}, version ${campaign.questionnaire.version}`)] : "")),
        campaign.nobody_to_ask ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, `${plural(campaign.nobody_to_ask, "thing")} ${campaign.nobody_to_ask === 1 ? "has" : "have"} nobody to ask. `),
          "Name an owner on each, or excuse it from the campaign.")) : null,
        card({ title: `${campaign.answered}% answered` }, h("div", { class: "stack" },
          segments([{ label: "answered", value: campaign.counts.done, tone: "ok" }, { label: "waiting", value: campaign.counts.pending, tone: "warn" },
            { label: "excused", value: campaign.counts.excused, tone: "none" }], { label: `${campaign.counts.done} of ${campaign.counts.asked} answered` }),
          Object.keys(campaign.outcomes).length && campaign.kind !== "acknowledgment" ? h("p", { class: "muted" }, "Of those answered: ",
            Object.entries(campaign.outcomes).map(([key, count]) => `${count} ${(OUTCOMES[key] ?? key).toLowerCase()}`).join(", "), ".") : null)),
        card({ title: "Coverage by unit", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Asked"), h("th", { scope: "col" }, "Answered"), h("th", { scope: "col" }, "Coverage"))),
          h("tbody", {}, campaign.coverage.map((row) => h("tr", {},
            h("td", {}, row.unit.name), h("td", {}, String(row.asked)), h("td", {}, String(row.done)),
            h("td", {}, h("div", { class: "row-sm" }, bar(row.answered, `${row.answered}% of ${row.unit.name} answered`), `${row.answered}%`)))))))),
        card({ title: "What was asked, and of whom", flush: true },
          h("div", { class: "tabs pad-x", role: "tablist" }, tabs.map(([key, text]) => h("button", { type: "button", class: "tab", role: "tab", "aria-selected": String(filter === key),
            onclick: () => setQuery({ show: key === "all" ? null : key }, { replace: false }) }, text))),
          itemsTable(campaign, shown)));
    },
  });
}

const ASKS = { attestation: "Does this control still operate as described?", self_assessment: "Look at this risk again.", completeness: "Are this unit's records complete?",
  profile: "How is this system protected?", evidence: "Evidence is wanted for this control." };

export function campaignItem(main, params) {
  return show(main, {
    title: "What you were asked",
    narrow: true,
    load: async () => (await get(`/api/v1/campaign-items/${params.id}`, null, { fresh: true })).data,
    view: (item, reload) => {
      const campaign = item.campaign;
      if (campaign.kind === "acknowledgment" && item.subject.ref) {
        navigate(`/library/${item.subject.ref}`, { replace: true });
        return h("p", { class: "muted" }, "Opening the document…");
      }
      const about = card({ title: item.subject.name, actions: item.subject.href ? h("a", { class: "btn btn-sm", href: item.subject.href }, "Open it") : null },
        h("div", { class: "stack-sm" }, item.subject.ref ? h("div", { class: "mono subtle" }, item.subject.ref) : null,
          item.about.statement ? h("p", {}, item.about.statement) : null));
      let body;
      if (item.status !== "pending") {
        body = card({ title: item.status === "excused" ? "Excused" : `Answered by ${item.completed_by ?? ""}, ${date(item.completed_at)}` },
          item.as_asked ? asAsked(item.as_asked) : h("p", { class: "muted" }, item.note ?? OUTCOMES[item.outcome] ?? "Done."));
      } else if (campaign.status !== "open") {
        body = alert("info", icon("info"), h("div", {}, "This campaign has ended, and nothing more is asked."));
      } else if (!item.questionnaire) {
        body = card({ title: "What is wanted" }, h("div", { class: "stack" }, h("p", {}, campaign.wanted),
          h("p", { class: "muted" }, "Add the evidence to the control. This request closes by itself once it is attached."),
          item.subject.href ? h("div", {}, h("a", { class: "btn btn-primary", href: item.subject.href }, "Open the control to add evidence")) : null));
      } else if (!item.can_answer) {
        body = alert("info", icon("info"), h("div", {}, `This was asked of ${item.asked ?? "nobody yet"}, and is waiting for their answer.`));
      } else {
        const form = questionnaireForm(item.questionnaire.document, item.draft ?? {});
        const problem = banner();
        const send = button("Send my answers", { kind: "btn-primary" });
        const keep = button("Save and finish later");
        const run = (complete) => async () => {
          const done = await submit({ button: complete ? send : keep, banner: problem, run: async () => {
            try {
              return await post(`/api/v1/campaign-items/${item.id}/answer`, { answers: form.answers(), complete });
            } catch (error) {
              form.setErrors(error.fields ?? {});
              if (!Object.keys(error.fields ?? {}).length) throw error;
              throw { detail: "Some answers need another look. Each is marked above.", fields: {} };
            }
          } });
          if (done) {
            toast(complete ? "Sent. Thank you." : "Saved.");
            if (complete) reload(); else form.setErrors({});
          }
        };
        send.addEventListener("click", run(true));
        keep.addEventListener("click", run(false));
        body = card({ title: item.questionnaire.title, footer: h("div", { class: "row" }, send, keep) }, h("div", { class: "stack-lg" }, form.node, problem));
      }
      return h("div", { class: "stack-lg" },
        campaign.can_see ? h("a", { class: "back-link", href: `/campaigns/${campaign.ref}` }, icon("chevron-left", "icon icon-sm"), campaign.name)
          : h("a", { class: "back-link", href: "/" }, icon("chevron-left", "icon icon-sm"), "Home"),
        pageHeader({ eyebrow: `${campaign.kind_label} · ${campaign.name}`, title: ASKS[campaign.kind],
          lede: `Asked by ${campaign.started_by}, due ${date(campaign.due_on)}.${campaign.summary ? ` ${campaign.summary}` : ""}` }),
        about, body);
    },
  });
}
