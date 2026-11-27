// Reports → Leadership reports: the reports issued, the next one as it stands now, and each
// report as it was issued, with whether its fingerprint verifies. An issued report is
// frozen: its figures are what they were, so they do not open today's lists.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime, plural, titleCase } from "../core/format.js";
import { navigate, query } from "../core/router.js";
import { banner, field, submit } from "../components/form.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, rampLevel, ratingBadge, stat } from "../components/ui.js";
import { show } from "./page.js";

const LEDE = "A report given to leadership once: the top risks and how they moved, appetite, posture by framework, the third parties with most at stake, the measures against the last report, and what is overdue. Issued, it is frozen with a fingerprint, and reopens exactly as it was.";
const MOVES = { added: "New since the last report", entered: "Joined the top", same: "Unchanged" };

function period(body) {
  return `${date(body.from)} to ${date(body.to)}`;
}

function table(caption, columns, rows) {
  return h("div", { class: "table-wrap" }, h("table", { class: "table report-table" },
    h("caption", { class: "sr-only" }, caption),
    h("thead", {}, h("tr", {}, columns.map(([label, numeric]) => h("th", { scope: "col", class: numeric ? "numeric" : null }, label)))),
    h("tbody", {}, rows)));
}

function link(ref, path) {
  return h("a", { class: "mono", href: `/${path}/${ref}` }, ref);
}

function movement(row) {
  if (!row.movement) return h("span", { class: "subtle" }, "No earlier report");
  if (row.movement === "up") return h("span", { class: "warn-text" }, `Rose from ${row.was}`);
  if (row.movement === "down") return h("span", { class: "ok-text" }, `Fell from ${row.was}`);
  return h("span", { class: row.movement === "same" ? "subtle" : "" }, MOVES[row.movement]);
}

function change(value, better, unit = "") {
  if (value == null) return h("span", { class: "subtle" }, "—");
  if (value === 0) return h("span", { class: "subtle" }, "No change");
  const up = value > 0;
  const good = better === "neither" ? null : (better === "lower") !== up;
  return h("span", { class: good == null ? "" : good ? "ok-text" : "warn-text" }, `${up ? "Up" : "Down"} ${Math.abs(value)}${unit}`);
}

function topRisks(body) {
  const rows = body.top_risks.map((row) => h("tr", {},
    h("td", {}, h("div", { class: "cell-main" }, link(row.ref, "risks"), " ", row.name),
      h("div", { class: "cell-sub" }, [row.unit, row.category].filter(Boolean).join(" · "))),
    h("td", {}, ratingBadge(rampLevel(row.place, row.places), row.rating_label)),
    h("td", {}, titleCase(row.standing)),
    h("td", {}, movement(row)),
    h("td", {}, row.owners.join(", ") || h("span", { class: "subtle" }, "Nobody"))));
  const left = body.left_top.length ? h("div", { class: "card-body stack" }, h("h3", {}, "No longer among the top"),
    h("ul", { class: "plain-list" }, body.left_top.map((row) => h("li", {}, link(row.ref, "risks"), " ", row.name, h("span", { class: "subtle" },
      row.status === "open" ? ` — was ${row.was}, now ${row.rating_label ?? "not rated"}` : ` — was ${row.was}, now ${row.status}`))))) : null;
  return card({ title: "Top risks", flush: true },
    rows.length ? table("The open risks rated highest", [["Risk"], ["Residual rating"], ["Standing"], ["Since the last report"], ["Owners"]], rows)
      : h("div", { class: "card-body subtle" }, "No open risk has a residual rating."),
    left);
}

function appetite(body) {
  if (!body.appetite.length) return null;
  return card({ title: "Appetite", flush: true }, table("Open risks by family, against its appetite",
    [["Family of risk"], ["Open", true], ["Above appetite", true], ["Need a decision", true], ["Reviews overdue", true]],
    body.appetite.map((row) => h("tr", {},
      h("td", {}, h("div", { class: "cell-main" }, row.label), row.appetite ? h("div", { class: "cell-sub" }, `Appetite: ${row.appetite}`) : null),
      h("td", { class: "numeric" }, String(row.open)), h("td", { class: "numeric" }, String(row.above)),
      h("td", { class: "numeric" }, String(row.decide)), h("td", { class: "numeric" }, String(row.overdue))))));
}

function posture(body) {
  if (!body.posture.length) return null;
  return card({ title: "Posture by framework", flush: true }, table("How much of each framework is verified or in place",
    [["Framework"], ["Verified or in place", true], ["Since the last report"], ["Open issues", true], ["Overdue", true], ["Exceptions in force", true]],
    body.posture.map((row) => h("tr", {},
      h("td", {}, h("div", { class: "cell-main" }, row.label), h("div", { class: "cell-sub" }, row.scopes.join(", "))),
      h("td", { class: "numeric" }, row.share == null ? "—" : `${row.share}%`, h("div", { class: "cell-sub" }, `${row.ready} of ${row.applicable}`)),
      h("td", {}, row.before == null || row.share == null ? h("span", { class: "subtle" }, "—") : change(row.share - row.before, "higher", " points")),
      h("td", { class: "numeric" }, String(row.issues)), h("td", { class: "numeric" }, String(row.overdue)),
      h("td", { class: "numeric" }, String(row.exceptions))))));
}

function thirdParties(body) {
  if (!body.third_parties.length) return null;
  return card({ title: "Third parties with most at stake", flush: true }, table("Third parties in the two highest tiers",
    [["Third party"], ["Next review"], ["Open risks", true], ["Open issues", true], ["Sharing not covered", true]],
    body.third_parties.map((row) => h("tr", {},
      h("td", {}, h("div", { class: "cell-main" }, link(row.ref, "third-parties"), " ", row.label), row.note ? h("div", { class: "cell-sub" }, row.note) : null),
      h("td", {}, row.next_review_on ? date(row.next_review_on) : "—"),
      h("td", { class: "numeric" }, String(row.figures.risks)), h("td", { class: "numeric" }, String(row.figures.issues)),
      h("td", { class: "numeric" }, String(row.figures.stops))))));
}

function figures(body) {
  const against = body.against;
  const compared = !against ? "There is nothing earlier to compare with."
    : against.kind === "report" ? `Compared with the last report, ${against.ref}, to ${date(against.on)}.`
      : `Compared with the organization's figures on ${date(against.on)}.`;
  const rows = Object.entries(body.groups).flatMap(([key, label]) => {
    const inGroup = body.figures.filter((row) => row.group === key);
    if (!inGroup.length) return [];
    return [h("tr", { class: "group-row" }, h("th", { scope: "colgroup", colspan: 4 }, label)),
      ...inGroup.map((row) => h("tr", {},
        h("td", {}, h("div", { class: "cell-main" }, row.label), h("div", { class: "cell-sub" }, row.counts)),
        h("td", { class: "numeric" }, String(row.value)),
        h("td", { class: "numeric" }, row.before == null ? "—" : String(row.before)),
        h("td", {}, change(row.change, row.better))))];
  });
  return card({ title: "Measures", flush: true },
    h("p", { class: "card-body subtle" }, compared),
    table("Each measure now and before", [["Measure"], ["Now", true], ["Before", true], ["Change"]], rows));
}

function overdue(body) {
  return card({ title: "Overdue" }, h("div", { class: "grid-2" }, body.overdue.map((kind) => h("div", { class: "stack" },
    h("h3", {}, `${kind.label}: ${kind.total}`),
    kind.items.length ? h("ul", { class: "plain-list" }, kind.items.map((item) => h("li", {},
      item.ref ? link(item.ref, kind.key === "issues" ? "issues" : kind.key === "risk_reviews" ? "risks" : kind.key === "actions" ? "actions" : "third-parties") : null,
      " ", item.name, item.days != null ? h("span", { class: "subtle" }, ` — ${plural(item.days, "day")} late`) : null)))
      : h("p", { class: "subtle" }, "Nothing."),
    kind.total > kind.items.length ? h("p", { class: "subtle" }, `And ${kind.total - kind.items.length} more.`) : null))));
}

/** What a report says, issued or not. */
export function reportBody(body) {
  const period_ = body.in_period;
  return h("div", { class: "stack-lg" },
    body.summary ? card({ title: "Summary" }, h("div", { class: "stack" }, body.summary.split(/\n{2,}/).map((part) => h("p", {}, part)))) : null,
    h("div", { class: "grid-3" },
      stat(String(period_.risks_added), "Risks added in the period"),
      stat(String(period_.issues_raised), "Issues raised in the period"),
      stat(String(period_.issues_closed), "Issues closed in the period")),
    topRisks(body), appetite(body), posture(body), thirdParties(body), figures(body), overdue(body));
}

export function leadershipList(main) {
  return show(main, {
    title: "Leadership reports",
    load: async () => (await get("/api/v1/leadership-reports", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Reports", title: "Leadership reports", lede: LEDE,
        actions: data.can_issue ? h("a", { class: "btn btn-primary", href: "/leadership-reports/next" }, "Prepare the next report") : null }),
      data.reports.length ? card({ flush: true }, table("Leadership reports issued", [["Report"], ["Period"], ["Issued"]],
        data.reports.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/leadership-reports/${row.ref}` }, row.title), h("div", { class: "cell-sub mono" }, row.ref)),
          h("td", {}, period(row)),
          h("td", {}, date(row.issued_at), h("div", { class: "cell-sub" }, row.issued_by))))))
        : emptyState({ iconName: "chart", title: "No report has been issued yet",
          text: data.can_issue ? "Prepare the first: it covers the last quarter." : "When one is issued it will be here." })),
  });
}

export function leadershipNext(main) {
  const asked = query();
  const params = { from: asked.get("from") || undefined, to: asked.get("to") || undefined };
  return show(main, {
    title: "The next leadership report",
    load: async () => (await get("/api/v1/leadership-reports/next", params, { fresh: true })).data,
    view: (data) => {
      const body = data.body;
      const from = field("From", { type: "date", value: body.from });
      const to = field("To", { type: "date", value: body.to });
      const title = field("Title", { value: data.title, maxlength: 200 });
      const summary = field("Summary", { type: "textarea", rows: 5, hint: "What you have to say about the period: it is issued with the report and frozen with it." });
      const problem = banner();
      const refresh = button("Show this period", { kind: "btn-secondary" });
      refresh.addEventListener("click", () => navigate(`/leadership-reports/next?from=${from.input.value}&to=${to.input.value}`));
      const go = button("Issue the report", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { from, to, title, summary },
          run: () => post("/api/v1/leadership-reports", { from: from.input.value, to: to.input.value, title: title.input.value, summary: summary.input.value }) });
        if (!done) return;
        toast(`${done.data.ref} is issued, and frozen as it is now.`);
        navigate(`/leadership-reports/${done.data.ref}`);
      });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Leadership reports", title: "The next report",
          lede: "This is the report as it stands now. Nothing is kept until it is issued; then what it says is frozen, and the history records its fingerprint." }),
        card({ title: "Issue it" }, h("div", { class: "stack" }, problem,
          h("div", { class: "row wrap" }, from.node, to.node, refresh), title.node, summary.node,
          h("div", { class: "row" }, go, h("a", { class: "btn btn-ghost", href: "/leadership-reports" }, "Cancel")))),
        h("h2", {}, `As it stands: ${period(body)}`),
        reportBody(body));
    },
  });
}

export function leadershipReport(main, { ref }) {
  return show(main, {
    title: ref,
    load: async () => (await get(`/api/v1/leadership-reports/${ref}`)).data,
    view: (data) => {
      const check = data.check;
      const verdict = check.verified
        ? alert("ok", h("strong", {}, "The fingerprint verifies. "), `This is the report as it was issued on ${dateTime(data.issued_at)}: what it says still matches the fingerprint the history recorded then.`)
        : alert("danger", h("strong", {}, "The fingerprint does not verify. "), "What this report says no longer matches the fingerprint recorded when it was issued. It has been changed since.");
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: `Leadership report ${data.ref}`, title: data.title,
          lede: `${period(data.body)}. Issued by ${data.issued_by} on ${date(data.issued_at)}.`,
          actions: button("Print", { kind: "btn-secondary", iconName: "file", onclick: () => window.print() }) }),
        verdict,
        h("p", { class: "subtle" }, "Fingerprint (SHA-256): ", h("code", { class: "fingerprint" }, check.fingerprint)),
        data.body.previous ? h("p", { class: "subtle" }, "The report before it: ", h("a", { href: `/leadership-reports/${data.body.previous.ref}` }, data.body.previous.title), ".") : null,
        reportBody(data.body));
    },
  });
}
