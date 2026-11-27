// Third parties → Due diligence: questionnaires sent to third parties' contacts through a
// link, their answers with the concerns among them, and what was concluded.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime, plural, relative } from "../core/format.js";
import { vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { banner, field, select, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { asAsked } from "../components/questionnaire.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts, ownersCard, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const STATUS = {
  draft: ["Not sent", ""], sent: ["Waiting for answers", "info"], answered: ["Answers to review", "warn"],
  concluded: ["Concluded", "ok"], cancelled: ["Cancelled", ""],
};
const CONCLUSIONS = { approved: ["Approved", "ok"], conditions: ["Approved with conditions", "warn"], declined: ["Not approved", "danger"] };
const LINK = { live: "In use", expired: "Expired", withdrawn: "Withdrawn", used: "Used to send the answers" };

export function reviewStatus(row) {
  if (row.status === "concluded" && row.conclusion) return pill(...CONCLUSIONS[row.conclusion]);
  if (row.status === "sent" && row.late) return pill("Answers late", "danger");
  const [text, tone] = STATUS[row.status] ?? [row.status, ""];
  return pill(text, tone);
}

/** Send the questionnaire to a contact: a new link, shown once. */
export function sendReview(review, { onDone }) {
  const contacts = (review.contacts ?? []).filter((each) => each.status === "active");
  openOverlay({
    title: review.status === "sent" ? "Send it again" : "Send it",
    subtitle: `${review.ref} · ${review.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const who = select("To", [["", "Choose…"], ...contacts.map((each) => [String(each.id), `${each.name} · ${each.email}`])],
        { value: review.contact ? String(review.contact.id) : "", required: true });
      const due = field("Answers wanted by", { type: "date", value: review.due_on ?? "" , hint: "Three weeks from today if left empty." });
      const days = field("The link lasts", { type: "number", value: "30", min: 1, max: 90, hint: "Days, from 1 to 90. After that it opens nothing." });
      const go = button(review.status === "sent" ? "Send a new link" : "Send", { kind: "btn-primary" });
      const sent = h("div", { class: "stack", hidden: true });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { contact_id: who, due_on: due, days },
          run: () => post(`/api/v1/reviews/${review.ref}/send`, { contact_id: Number(who.input.value) || 0,
            due_on: due.input.value || null, days: Number(days.input.value) || null }) });
        if (!done) return;
        const address = h("input", { class: "input mono", readonly: true, value: done.meta.link.url, "aria-label": "The link" });
        sent.replaceChildren(
          alert("ok", h("div", {}, done.meta.link.emailed ? "It was sent by email. The link is below too, this once." : "Send this link to them yourself. It is shown only now.")),
          address,
          button("Copy the link", { iconName: "link", onclick: async () => {
            try {
              await navigator.clipboard.writeText(done.meta.link.url);
              toast("Copied.");
            } catch {
              address.select();
            }
          } }),
          h("p", { class: "subtle" }, "Anyone with the link can answer as them until it expires, so send it only to them. An earlier link no longer works."));
        sent.hidden = false;
        form.hidden = true;
        footer.replaceChildren(h("div", { class: "row" }, button("Done", { kind: "btn-primary", onclick: () => {
          close();
          onDone?.();
        } })));
        address.select();
      });
      const form = h("div", { class: "stack-lg" }, problem,
        contacts.length ? null : alert("warn", h("div", {}, "It has no contact to send to. Add one on the third party's Due diligence tab.")),
        who.node, due.node, days.node);
      body.append(form, sent);
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function concludeBox(review, onDone) {
  openOverlay({
    title: "Conclude the review",
    subtitle: `${review.ref} · ${review.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const choice = select("Conclusion", [["", "Choose…"], ...Object.entries(CONCLUSIONS).map(([key, [text]]) => [key, text])], { required: true });
      const note = field("What was decided", { type: "textarea", rows: 4, hint: "Needed for conditions, and for one not approved: what must change, and by when." });
      const go = button("Conclude", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { conclusion: choice, note },
          run: () => post(`/api/v1/reviews/${review.ref}/conclude`, { conclusion: choice.input.value, note: note.input.value || null }) });
        if (!done) return;
        close();
        toast("Concluded.");
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, choice.node, note.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function answersCard(review) {
  const found = review.answers;
  if (!found) {
    return card({ title: "Answers" }, h("p", { class: "muted" }, review.status === "draft"
      ? "Nothing has been sent yet." : "Nothing has come back yet."));
  }
  if (found.status !== "submitted") {
    return card({ title: "Answers" }, h("p", { class: "muted" }, `${found.by} has saved some answers and not yet sent them.`));
  }
  const flagged = new Set(found.concerns.items.map((each) => each.key));
  const sections = found.as_asked.map((section) => ({ ...section, questions: section.questions.map((q) =>
    (flagged.has(q.key) ? { ...q, said: `${Array.isArray(q.said) ? q.said.join(", ") : q.said}  ⚑ a concern` } : q)) }));
  return card({ title: `Answers, sent by ${found.by} ${relative(found.submitted_at)}` }, asAsked(sections));
}

function concernsCard(review) {
  const found = review.answers?.concerns;
  if (!found) return null;
  return card({ title: "Concerns" },
    h("p", {}, found.count ? `${plural(found.count, "answer")} of ${found.scored} the questionnaire marks are concerns.`
      : `None of the ${found.scored} answers the questionnaire marks is a concern.`),
    found.items.length ? h("ul", { class: "plain-list stack-sm reasons" }, found.items.map((each) => h("li", {},
      h("span", { class: "subtle" }, `${each.section}: `), each.label, " ", h("strong", {}, each.said)))) : null);
}

function overview(review, ctx) {
  const link = review.link;
  const glance = [
    ["Third party", review.third_party ? recordChip(review.third_party) : null],
    ["Questionnaire", review.questionnaire ? `${review.questionnaire.title}, version ${review.questionnaire.version}` : null],
    ["Tier when started", review.tier_label],
    ["Sent to", review.contact ? `${review.contact.name} · ${review.contact.email}` : null],
    ["Answers wanted by", review.due_on ? date(review.due_on) : null],
    ["The link", link ? `${LINK[link.state]}${link.state === "live" ? `, until ${date(link.expires_at)}` : ""}` : null],
    ["Last opened", link?.last_used_at ? dateTime(link.last_used_at) : null],
  ];
  const conclusion = review.status === "concluded" ? card({ title: "Conclusion" },
    h("div", { class: "row wrap" }, pill(...CONCLUSIONS[review.conclusion])), review.conclusion_note ? h("p", {}, review.conclusion_note) : null,
    h("p", { class: "subtle" }, `By ${review.concluded_by}, ${relative(review.concluded_at)}.`)) : null;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" }, conclusion,
      review.status === "cancelled" ? alert("info", h("div", {}, `Cancelled${review.cancelled_note ? `: ${review.cancelled_note}` : "."}`)) : null,
      concernsCard(review), answersCard(review)),
    h("div", { class: "stack-lg" }, card({ title: "At a glance" }, facts(glance)), ownersCard(review, ctx)));
}

export function reviewPage(main, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/reviews/${params.ref}`;
      const record = (await get(base, null, { fresh: true })).data;
      const [party, entries, vocab] = await Promise.all([
        record.can.send && record.third_party ? get(`/api/v1/third-parties/${record.third_party.ref}`, null, { fresh: true }) : null,
        tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null, vocabularies()]);
      return { record: { ...record, contacts: party?.data?.contacts ?? [] }, history: entries?.data ?? [], vocab };
    },
    view: (data, reload) => {
      const review = data.record;
      document.title = `${review.name} · ${review.ref}`;
      const can = review.can;
      const actions = h("div", { class: "row-sm wrap" },
        can.conclude ? button("Conclude", { kind: "btn-primary", onclick: () => concludeBox(review, reload) }) : null,
        can.send ? button(review.status === "sent" ? "Send it again" : "Send it", { kind: review.status === "draft" ? "btn-primary" : "", iconName: "upload",
          onclick: () => sendReview(review, { onDone: reload }) }) : null,
        can.withdraw ? button("Withdraw the link", { kind: "btn-ghost", onclick: () => confirmAction({ title: "Withdraw the link?",
          text: "It stops opening the questionnaire at once. Answers already saved with it are kept, and a new link carries on from them.",
          confirmLabel: "Withdraw it", run: async () => {
            await post(`/api/v1/reviews/${review.ref}/withdraw`);
            toast("Withdrawn.");
            reload();
          } }) }) : null,
        can.cancel ? button("Cancel the review", { kind: "btn-ghost", onclick: () => confirmAction({ title: `Cancel ${review.ref}?`,
          text: "Its link stops working, and nothing more is asked.", confirmLabel: "Cancel it", danger: true, run: async () => {
            await post(`/api/v1/reviews/${review.ref}/cancel`, {});
            toast("Cancelled.");
            reload();
          } }) }) : null);
      return h("div", { class: "stack" },
        recordHeader(review, { badges: [reviewStatus(review)], actions }),
        tabBar([["overview", "Overview"], ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history)) : overview(review, { reload, vocab: data.vocab }));
    },
  });
}

export function reviewList(main) {
  return show(main, {
    title: "Due diligence",
    load: async () => (await get("/api/v1/reviews", Object.fromEntries(query()), { fresh: true })),
    view: (page) => {
      const rows = page.data;
      const search = searchBox("Search reviews");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("status", [["", "Any status"], ["open", "Not yet concluded"], ...Object.entries(STATUS).map(([key, [text]]) => [key, text])], "Status"),
        mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Review", "name"), h("th", { scope: "col" }, "Third party"), h("th", { scope: "col" }, "Owner"),
          sortHeader("Status", "status"), sortHeader("Answers wanted by", "due_on"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/reviews/${row.ref}` }, row.name),
            h("div", { class: "cell-sub" }, [row.ref, row.questionnaire, row.tier_label].filter(Boolean).join(" · "))),
          h("td", {}, row.third_party ? recordChip(row.third_party) : null),
          ownerCell(row),
          h("td", {}, reviewStatus(row)),
          h("td", { class: "nowrap" }, row.due_on ? date(row.due_on) : h("span", { class: "subtle" }, "Not set")))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "file", title: "No reviews yet", text: "A review sends a third party's contact the questionnaire its tier asks, through a link that needs no account. Start one from the third party's Due diligence tab." });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Third parties", title: "Due diligence",
          lede: "Questionnaires sent to third parties through a link, the concerns among their answers, and what was concluded." }),
        bar, card({ title: plural(page.meta.total, "review"), flush: true, footer: pager(page.meta, rows.length) }, body));
    },
  });
}

