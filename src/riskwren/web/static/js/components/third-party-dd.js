// A third party's Due diligence tab: the people there who can be asked, and its reviews.
// Fetched when the tab is first opened.

import { get, patch, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { navigate } from "../core/router.js";
import { banner, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { card, pill } from "./ui.js";

const STATUS = {
  draft: ["Not sent", ""], sent: ["Waiting for answers", "info"], answered: ["Answers to review", "warn"],
  concluded: ["Concluded", "ok"], cancelled: ["Cancelled", ""],
};
const CONCLUSIONS = { approved: ["Approved", "ok"], conditions: ["Approved with conditions", "warn"], declined: ["Not approved", "danger"] };

function statusOf(row) {
  if (row.status === "concluded" && row.conclusion) return pill(...CONCLUSIONS[row.conclusion]);
  if (row.status === "sent" && row.late) return pill("Answers late", "danger");
  return pill(...(STATUS[row.status] ?? [row.status, ""]));
}

function contactForm(record, contact, onDone) {
  openOverlay({
    title: contact ? "Edit the contact" : "Add a contact",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const name = field("Name", { value: contact?.name ?? "", required: true });
      const email = field("Email address", { type: "email", value: contact?.email ?? "", required: true,
        hint: "Where questionnaires are sent. A link sent here lets whoever holds it answer as them." });
      const role = field("Role there", { value: contact?.role ?? "" });
      const phone = field("Phone", { value: contact?.phone ?? "" });
      const status = contact ? select("Status", [["active", "Active"], ["left", "Has left"]], { value: contact.status }) : null;
      const go = button(contact ? "Save" : "Add", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const values = { name: name.input.value, email: email.input.value, role: role.input.value || null, phone: phone.input.value || null,
          ...(status ? { status: status.input.value } : {}) };
        const done = await submit({ button: go, banner: problem, fields: { name, email, role, phone, ...(status ? { status } : {}) },
          run: () => (contact ? patch(`/api/v1/contacts/${contact.id}`, values) : post(`/api/v1/third-parties/${record.ref}/contacts`, values)) });
        if (!done) return;
        close();
        toast(contact ? "Saved." : `${done.data.name} was added.`);
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, name.node, email.node, h("div", { class: "grid-2" }, role.node, phone.node), status?.node ?? null));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Start a review: the questionnaire its tier asks for, or another chosen here. A third party
 *  whose tier asks for none, or that has no tier, is reviewed with the one chosen. */
async function startReview(record) {
  const listed = (await get("/api/v1/questionnaires", null, { fresh: true })).data.questionnaires
    .filter((each) => each.status === "active" && each.current_version);
  const dueDiligence = listed.filter((each) => each.purpose === "due_diligence");
  const others = listed.filter((each) => each.purpose !== "due_diligence");
  openOverlay({
    title: "Start a review",
    subtitle: record.name,
    render: (body, footer, close) => {
      const choices = [
        ...(record.tier ? [["", "The one its tier asks for"]] : [["", "Choose…"]]),
        ...dueDiligence.map((each) => [each.key, each.title]),
        ...others.map((each) => [each.key, `${each.title} (${each.purpose.replace("_", " ")})`]),
      ];
      const questionnaire = select("Questionnaire", choices, { value: "",
        hint: record.tier ? "Its tier sets one; choose another only for a reason." : "It has no tier yet, so choose what to ask. Tiering it first sets the right one." });
      const problem = banner();
      const go = button("Start it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const chosen = questionnaire.input.value;
        const done = await submit({ button: go, banner: problem, fields: { questionnaire },
          run: () => post(`/api/v1/third-parties/${record.ref}/reviews`, chosen ? { questionnaire: chosen } : {}) });
        if (!done) return;
        close();
        toast(`${done.data.ref} was started.`);
        navigate(`/reviews/${done.data.ref}`);
      });
      body.append(h("div", { class: "stack" }, problem, questionnaire.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function dueDiligenceTab(record, ctx) {
  const canKeep = record.can_tier;
  const people = record.contacts;
  const contactsCard = people === null ? null : card({ title: "Contacts",
    actions: canKeep ? button("Add a contact", { kind: "btn-sm", iconName: "plus", onclick: () => contactForm(record, null, ctx.reload) }) : null },
    people.length ? h("ul", { class: "plain-list stack" }, people.map((person) => h("li", { class: "row wrap" },
      h("div", { class: "grow" }, h("div", { class: "cell-main" }, person.name, person.status === "left" ? h("span", { class: "subtle" }, " · has left") : null),
        h("div", { class: "cell-sub" }, [person.role, person.email, person.phone].filter(Boolean).join(" · "))),
      canKeep ? button("Edit", { kind: "btn-sm btn-ghost", "aria-label": `Edit ${person.name}`, onclick: () => contactForm(record, person, ctx.reload) }) : null)))
      : h("p", { class: "muted" }, "Nobody there is on record. A questionnaire is sent to a contact, who answers through a link without an account."));
  const rows = record.reviews ?? [];
  const reviewsCard = card({ title: "Reviews", flush: rows.length > 0,
    actions: canKeep ? button("Start a review", { kind: "btn-sm", iconName: "plus", onclick: () => startReview(record) }) : null },
    rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Review"), h("th", { scope: "col" }, "Status"), h("th", { scope: "col" }, "Concluded or due"))),
      h("tbody", {}, rows.map((row) => h("tr", {},
        h("td", {}, h("a", { class: "cell-main", href: `/reviews/${row.ref}` }, row.name), h("div", { class: "cell-sub" }, [row.ref, row.questionnaire].filter(Boolean).join(" · "))),
        h("td", {}, statusOf(row)),
        h("td", { class: "nowrap" }, row.concluded_at ? date(row.concluded_at) : row.due_on ? date(row.due_on) : h("span", { class: "subtle" }, "Not set")))))))
      : h("p", { class: "muted" }, `No review yet. ${record.tiering ? "Its tier names the questionnaire it is asked." : "Tier it first: its tier names the questionnaire it is asked."}`));
  return h("div", { class: "split" }, h("div", { class: "stack-lg" }, reviewsCard), h("div", { class: "stack-lg" }, contactsCard));
}
