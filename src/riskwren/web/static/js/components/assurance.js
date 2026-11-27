// A third party's Assurance tab: its reports and certificates, how each stands, and what a
// careful reading of each found. Fetched when the tab is first opened.

import { get, post, upload } from "../core/api.js";
import { button, h, uid } from "../core/dom.js";
import { date, relative } from "../core/format.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { recordChip } from "./record.js";
import { toast } from "./toast.js";
import { alert, card, pill } from "./ui.js";

const STATE = { current: ["In date", "ok"], expiring: ["Expiring", "warn"], stale: ["Expired: no longer counts", "danger"] };
const RELIANCE = { relies: ["Can be relied on", "ok"], partly: ["Relied on, with gaps", "warn"], cannot: ["Cannot be relied on", "danger"] };

function addReport(record, kinds, onDone) {
  openOverlay({
    title: "Add a report or certificate",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const name = field("Name", { required: true, hint: "For example: SOC 2 Type II report, 2026." });
      const file = h("input", { type: "file", class: "input", "aria-label": "The file" });
      const from = field("The period it covers, from", { type: "date" });
      const to = field("to", { type: "date" });
      const received = field("Received on", { type: "date", value: new Date().toISOString().slice(0, 10) });
      const until = field("Holds until", { type: "date", required: true,
        hint: "After this it stops counting. A report is usually relied on for a year after its period ends; a certificate until it expires." });
      const go = button("Add", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { name, covers_from: from, covers_to: to, collected_on: received, valid_until: until },
          run: async () => {
            const made = await post(`/api/v1/third-parties/${record.ref}/assurance`, { name: name.input.value,
              covers_from: from.input.value || null, covers_to: to.input.value || null,
              collected_on: received.input.value || null, valid_until: until.input.value || null });
            const chosen = file.files?.[0];
            if (chosen) await upload(`/api/v1/evidence/${made.data.ref}/file`, chosen, { name: chosen.name });
            return made;
          } });
        if (!done) return;
        close();
        toast(`${done.data.ref} was added. Review it to say what it covers.`);
        onDone();
      });
      body.append(h("div", { class: "stack-lg" }, problem, name.node,
        h("div", { class: "field" }, h("div", { class: "label" }, "The file"), file, h("div", { class: "hint" }, "A PDF, up to 25 MB. It is only ever downloaded, never opened in the app.")),
        h("div", { class: "grid-2" }, from.node, to.node), h("div", { class: "grid-2" }, received.node, until.node)));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Rows that can be added and taken away: each a few fields. */
function rows(title, make, initial) {
  const list = h("div", { class: "stack" });
  const items = [];
  const add = (value = {}) => {
    const made = make(value);
    const remove = button("Remove", { kind: "btn-sm btn-ghost", onclick: () => {
      items.splice(items.indexOf(made), 1);
      node.remove();
    } });
    const node = h("fieldset", { class: "repeat" }, h("legend", { class: "sr-only" }, title), made.node, h("div", { class: "row" }, remove));
    items.push(made);
    list.append(node);
  };
  for (const value of initial) add(value);
  return { node: h("div", { class: "stack" }, list, button(`Add ${title.toLowerCase()}`, { kind: "btn-sm", iconName: "plus", onclick: () => add() })),
    values: () => items.map((item) => item.value()) };
}

function reviewReport(record, document, kinds, onDone) {
  const before = document.review;
  openOverlay({
    title: before ? "Review it again" : "Review the report",
    subtitle: `${document.ref} · ${document.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const kind = select("What it is", [["", "Choose…"], ...Object.entries(kinds.kinds)], { value: before?.kind ?? "", required: true });
      const issuer = field("Issued by", { value: before?.issuer ?? "", hint: "The audit firm or certifying body." });
      const opinion = select("Opinion", Object.entries(kinds.opinions), { value: before?.opinion ?? "unqualified" });
      const services = (record.services ?? []).filter((service) => service.status === "active").map((service) => ({ service,
        box: checkbox(service.name, { checked: before ? before.covers.some((c) => c.ref === service.ref) : false }) }));
      const carved = field("Carved out", { type: "textarea", rows: 2, value: before?.carve_outs ?? "",
        hint: "Parts left to others it uses, which the report does not cover: a data centre, a hosting provider." });
      const exceptions = rows("An exception", (value) => {
        const where = field("Control or area", { value: value.control ?? "" });
        const what = field("What the auditor found", { type: "textarea", rows: 2, value: value.description ?? "" });
        const matters = checkbox("It matters here", { checked: value.matters ?? false });
        const response = field("What is done about it", { value: value.response ?? "" });
        return { node: h("div", { class: "stack-sm" }, where.node, what.node, matters.node, response.node),
          value: () => ({ control: where.input.value, description: what.input.value, matters: matters.input.checked, response: response.input.value }) };
      }, before?.exceptions ?? []);
      const duties = rows("A responsibility", (value) => {
        const what = field("What the organization must do", { type: "textarea", rows: 2, value: value.text ?? "" });
        const control = field("The control here that does it", { value: value.control?.ref ?? "", placeholder: "CTL-0001",
          hint: "Its reference, from the control library." });
        const state = select("Here", Object.entries(kinds.states), { value: value.status ?? "in_place" });
        return { node: h("div", { class: "stack-sm" }, what.node, h("div", { class: "grid-2" }, control.node, state.node)),
          value: () => ({ text: what.input.value, control: control.input.value.trim() || null, status: state.input.value }) };
      }, (before?.responsibilities ?? []).map((row) => ({ ...row })));
      const reliance = select("Can it be relied on?", [["", "Choose…"], ...Object.entries(kinds.reliance)], { value: before?.reliance ?? "", required: true });
      const note = field("What it cannot be relied on for, and why", { type: "textarea", rows: 3, value: before?.note ?? "",
        hint: "Needed unless it can be relied on as it is." });
      const go = button("Record the review", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { kind, issuer, opinion, carve_outs: carved, reliance, note },
          run: () => post(`/api/v1/third-parties/${record.ref}/assurance/${document.ref}/reviews`, {
            kind: kind.input.value, issuer: issuer.input.value || null, opinion: opinion.input.value,
            services: services.filter((each) => each.box.input.checked).map((each) => each.service.ref),
            carve_outs: carved.input.value || null, exceptions: exceptions.values(), responsibilities: duties.values(),
            reliance: reliance.input.value, note: note.input.value || null }) });
        if (!done) return;
        close();
        toast("The review was recorded.");
        onDone();
      });
      const id = uid("covers");
      body.append(h("div", { class: "stack-lg" }, problem,
        h("div", { class: "grid-2" }, kind.node, issuer.node), opinion.node,
        h("fieldset", { class: "field", "aria-describedby": id }, h("legend", { class: "label" }, "The services it covers"),
          h("div", { class: "hint", id }, "Those left unticked are services it does not cover."),
          services.length ? h("div", { class: "stack-sm" }, services.map((each) => each.box.node)) : h("p", { class: "muted" }, "No service of this third party is on record.")),
        carved.node,
        h("section", { class: "stack" }, h("h3", {}, "Exceptions the auditor noted"), exceptions.node),
        h("section", { class: "stack" }, h("h3", {}, "What it leaves to the organization"),
          h("p", { class: "muted" }, "In a SOC report, the complementary user entity controls: what the organization must do itself for the report to hold."), duties.node),
        reliance.node, note.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function reviewView(review) {
  const list = (items, draw) => (items.length ? h("ul", { class: "plain-list stack-sm" }, items.map(draw)) : h("p", { class: "muted" }, "None."));
  return h("div", { class: "stack" },
    h("div", { class: "row wrap" }, pill(...RELIANCE[review.reliance]), h("span", {}, review.kind_label),
      review.issuer ? h("span", { class: "subtle" }, `issued by ${review.issuer}`) : null),
    h("p", { class: "subtle" }, review.opinion_label),
    review.note ? h("p", {}, review.note) : null,
    h("dl", { class: "dl" },
      h("dt", {}, "Covers"), h("dd", {}, review.covers.length ? h("span", { class: "row-sm wrap" }, review.covers.map((c) => recordChip(c))) : h("span", { class: "subtle" }, "None of its services")),
      review.misses.length ? [h("dt", {}, "Does not cover"), h("dd", {}, h("span", { class: "row-sm wrap" }, review.misses.map((c) => recordChip(c))))] : null,
      review.carve_outs ? [h("dt", {}, "Carved out"), h("dd", {}, review.carve_outs)] : null),
    h("h3", {}, "Exceptions noted"),
    list(review.exceptions, (row) => h("li", { class: "reasons" }, h("div", {}, row.control ? h("strong", {}, `${row.control}: `) : null, row.description),
      h("div", { class: "subtle" }, row.matters ? "Matters here." : "Does not matter here.", row.response ? ` ${row.response}` : ""))),
    h("h3", {}, "What it leaves to the organization"),
    list(review.responsibilities, (row) => h("li", { class: "row wrap" }, h("span", { class: "grow" }, row.text),
      row.control ? recordChip(row.control) : null, pill(row.status_label, row.status === "not_in_place" ? "danger" : row.status === "in_place" ? "ok" : ""))),
    h("p", { class: "subtle" }, `Reviewed by ${review.by}, ${relative(review.at)}.`));
}

export async function assuranceTab(record, ctx) {
  const [found, kinds] = await Promise.all([get(`/api/v1/third-parties/${record.ref}/assurance`, null, { fresh: true }), get("/api/v1/assurance-kinds")]);
  const documents = found.data.documents;
  const may = found.data.can_add;
  const add = may ? button("Add a report", { kind: "btn-sm", iconName: "plus", onclick: () => addReport(record, kinds.data, ctx.reload) }) : null;
  const standing = found.data.standing;
  return h("div", { class: "stack-lg" },
    standing.current ? alert("ok", h("div", {}, `Independent assurance can be relied on until ${date(standing.until)}.`))
      : alert("warn", h("div", {}, "Nothing independent in date can be relied on for it. Ask for a report or certificate, or say why none is needed.")),
    card({ title: "Reports and certificates", actions: add },
      documents.length ? h("ul", { class: "plain-list stack-lg" }, documents.map((doc) => h("li", { class: "stack" },
        h("div", { class: "row wrap" }, h("a", { class: "cell-main grow", href: `/evidence/${doc.ref}` }, doc.name),
          pill(...STATE[doc.state]),
          may ? button(doc.review ? "Review it again" : "Review it", { kind: doc.review ? "btn-sm btn-ghost" : "btn-sm", onclick: () => reviewReport(record, doc, kinds.data, ctx.reload) }) : null),
        h("div", { class: "cell-sub" }, [doc.ref, doc.covers_from && doc.covers_to ? `covers ${date(doc.covers_from)} to ${date(doc.covers_to)}` : null,
          `holds until ${date(doc.valid_until)}`, doc.has_file ? null : "no file yet"].filter(Boolean).join(" · ")),
        doc.review ? reviewView(doc.review) : h("p", { class: "muted" }, "Not reviewed yet: what it covers, and what it leaves to the organization, is not known."))))
        : h("p", { class: "muted" }, "No report or certificate is on record. A SOC 2 report, an ISO/IEC 27001 certificate, or a penetration test summary says what someone independent found.")));
}
