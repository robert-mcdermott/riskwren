// Admin → Other systems: tokens another system uses to read or act as a role, and webhooks
// that tell an address what has happened. A token or a secret is shown once, when it is made.

import { del, get, patch, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime } from "../core/format.js";
import { unitOptions, units } from "../core/lookups.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { toast } from "../components/toast.js";
import { alert, card, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const ROLE_LABELS = {
  auditor: "Auditor: reads everything", manager: "Manager: runs the program",
  assessor: "Assessor: tests and reviews", steward: "Steward of a unit", member: "Member: reads what everyone may",
};
const STATE_TONES = { active: "ok", expired: "warn", withdrawn: "" };
const DELIVERY_TONES = { sent: "ok", queued: "info", failed: "danger" };
const FORMAT_LABELS = { plain: "The plain message", ticket: "A ticket", chat: "A chat message" };

function shownOnce(title, value, note) {
  return alert("warn", h("div", { class: "stack-sm" },
    h("strong", {}, title),
    h("code", { class: "copyable", tabindex: "0" }, value),
    h("span", {}, note)));
}

function tokensCard(data, unitTree, reload, reveal) {
  const rows = data.tokens.length ? data.tokens.map((token) => h("tr", {},
    h("td", {}, h("div", { class: "cell-main" }, token.name), h("div", { class: "cell-sub" }, h("code", {}, `${token.prefix}…`))),
    h("td", {}, ROLE_LABELS[token.role] ?? token.role, token.org_unit_id ? h("div", { class: "cell-sub" }, unitTree.byId.get(token.org_unit_id)?.name ?? "") : null),
    h("td", {}, token.read_only ? "Reads only" : "Reads and changes"),
    h("td", {}, date(token.expires_at)),
    h("td", {}, token.last_used_at ? dateTime(token.last_used_at) : h("span", { class: "subtle" }, "Never")),
    h("td", {}, pill(token.state === "active" ? "In force" : token.state === "expired" ? "Ended" : "Withdrawn", STATE_TONES[token.state])),
    h("td", {}, token.state === "active" ? button("Withdraw", { kind: "btn-ghost btn-sm", onclick: async () => {
      if (!window.confirm(`Withdraw the token for ${token.name}? Whatever uses it stops at once.`)) return;
      await post(`/api/v1/admin/tokens/${token.id}/revoke`, {});
      toast("The token was withdrawn.");
      reload();
    } }) : null)))
    : [h("tr", {}, h("td", { colspan: 7, class: "subtle" }, "No token has been made."))];

  const name = field("What will use it", { maxlength: 80, hint: "For example: the ticketing system." });
  const role = select("Acts as", data.roles.map((key) => [key, ROLE_LABELS[key] ?? key]), { value: "auditor" });
  const unit = select("Unit", unitOptions(unitTree.tree, { blank: "The whole organization" }), { value: "",
    hint: "A manager's or an assessor's token may be for one unit; a steward's must be." });
  const readOnly = checkbox("It may only read", { checked: true });
  const days = field("Lasts, in days", { type: "number", value: "90", min: 1, max: 366 });
  const problem = banner();
  const make = button("Make a token", { kind: "btn-primary", type: "submit" });
  const form = h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const done = await submit({ button: make, banner: problem, fields: { name, role, org_unit_id: unit, days },
      run: () => post("/api/v1/admin/tokens", { name: name.input.value, role: role.input.value,
        org_unit_id: unit.input.value ? Number(unit.input.value) : null, read_only: readOnly.input.checked,
        days: Number(days.input.value) }) });
    if (!done) return;
    reveal(shownOnce(`The token for ${done.data.name}`, done.meta.token,
      "Copy it now: it is not shown again, and only a fingerprint of it is kept. Send it as Authorization: Bearer, and keep it as you would a password."));
  } }, problem, h("div", { class: "grid-2" }, name.node, role.node), h("div", { class: "grid-2" }, unit.node, days.node), readOnly.node,
  h("div", { class: "form-actions" }, make));

  return card({ title: "Tokens", flush: true },
    h("div", { class: "card-pad" }, h("p", { class: "muted" }, "A token lets another system use the API as a role, never as a person: an auditor's token reads everything, a steward's works within one unit. What it changes is in the history under its name. It ends on its date or when it is withdrawn.")),
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["Token", "Acts as", "May", "Ends", "Last used", "State"].map((text) => h("th", { scope: "col" }, text)),
        h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Withdraw")))),
      h("tbody", {}, rows))),
    h("div", { class: "card-pad" }, form));
}

function webhooksCard(data, reload, reveal) {
  const list = data.webhooks.length ? data.webhooks.map((hook) => card({ title: hook.name,
    actions: h("div", { class: "row-sm" }, pill(hook.active ? "Active" : "Paused", hook.active ? "ok" : ""),
      button("Send a test", { kind: "btn-ghost btn-sm", onclick: async () => {
        await post(`/api/v1/admin/webhooks/${hook.id}/test`, {});
        toast("A test message is queued; it is sent within a minute.");
        reload();
      } }),
      button(hook.active ? "Pause" : "Resume", { kind: "btn-ghost btn-sm", onclick: async () => {
        await patch(`/api/v1/admin/webhooks/${hook.id}`, { active: !hook.active });
        reload();
      } }),
      button("Remove", { kind: "btn-ghost btn-sm", onclick: async () => {
        if (!window.confirm(`Remove the webhook ${hook.name}? Its deliveries go with it.`)) return;
        await del(`/api/v1/admin/webhooks/${hook.id}`);
        toast("The webhook was removed.");
        reload();
      } })) },
    h("div", { class: "stack" },
      h("dl", { class: "dl" }, h("dt", {}, "Address"), h("dd", {}, h("code", {}, hook.url)),
        h("dt", {}, "Told of"), h("dd", {}, hook.events.join(", ")),
        h("dt", {}, "Sent as"), h("dd", {}, FORMAT_LABELS[hook.format] ?? hook.format)),
      hook.deliveries.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("caption", { class: "sr-only" }, `The latest messages to ${hook.name}`),
        h("thead", {}, h("tr", {}, ["Event", "Record", "Made", "Tries", "Result"].map((text) => h("th", { scope: "col" }, text)))),
        h("tbody", {}, hook.deliveries.map((delivery) => h("tr", {},
          h("td", {}, h("code", {}, delivery.event)), h("td", {}, delivery.record?.ref ?? "—"),
          h("td", {}, dateTime(delivery.created_at)), h("td", {}, String(delivery.attempts)),
          h("td", {}, pill(delivery.status === "sent" ? `Sent${delivery.response_code ? `, ${delivery.response_code}` : ""}` : delivery.status === "queued" ? "Waiting" : "Failed",
            DELIVERY_TONES[delivery.status]), delivery.error ? h("div", { class: "cell-sub" }, delivery.error) : null))))))
        : h("p", { class: "subtle" }, "No message has been sent yet."))))
    : [h("p", { class: "subtle" }, "No webhook has been registered.")];

  const name = field("What receives it", { maxlength: 80 });
  const url = field("Address", { type: "url", placeholder: "https://", hint: "Only https:// addresses." });
  const events = field("Told of", { value: "issue.*, incident.*",
    hint: `Separated by commas: * for everything; a family such as issue.*; or an event such as issue.close or risk.assess. The families: ${data.families.map((each) => `${each.key} (${each.label.toLowerCase()})`).join(", ")}.` });
  const shape = select("Sent as", Object.entries(FORMAT_LABELS), { value: "plain",
    hint: "A ticket gives a title, a description, and a link; a chat message is one line of text. Each still names only the event and the record." });
  const problem = banner();
  const make = button("Register it", { kind: "btn-primary", type: "submit" });
  const form = h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const done = await submit({ button: make, banner: problem, fields: { name, url, events, format: shape },
      run: () => post("/api/v1/admin/webhooks", { name: name.input.value, url: url.input.value, format: shape.input.value,
        events: events.input.value.split(",").map((each) => each.trim()).filter(Boolean) }) });
    if (!done) return;
    reveal(shownOnce(`The signing secret for ${done.data.name}`, done.meta.secret,
      "Copy it now: it is not shown again. Each message carries an X-RiskWren-Signature header, t=time,v1=HMAC-SHA256 of the time, a dot, and the body, made with this secret."));
  } }, problem, h("div", { class: "grid-2" }, name.node, url.node), h("div", { class: "grid-2" }, events.node, shape.node), h("div", { class: "form-actions" }, make));

  return h("div", { class: "stack-lg" },
    card({ title: "Webhooks" }, h("div", { class: "stack" },
      h("p", { class: "muted" }, "A webhook tells an address what has happened: that an issue was raised, a risk assessed, an incident reported. A message names the event and the record's reference, and never what the record says: the receiver asks the API, with a token, for what it may see. A restricted record is never named. Messages are signed, and tried again when the address does not answer."),
      form)),
    ...list);
}

export function adminIntegrations(main) {
  let revealed = null;
  return show(main, {
    title: "Other systems",
    load: async () => {
      const [tokenList, hookList, unitTree] = await Promise.all([
        get("/api/v1/admin/tokens", undefined, { fresh: true }), get("/api/v1/admin/webhooks", undefined, { fresh: true }), units()]);
      return { tokens: tokenList.data, roles: tokenList.meta.roles, webhooks: hookList.data, families: hookList.meta.families, unitTree };
    },
    view: (data, reload) => {
      const reveal = (node) => {
        revealed = node;
        reload();
      };
      const shown = revealed;
      revealed = null;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "Other systems",
          lede: "Let other systems use RiskWren: a token to read or to act through the API as a role, and webhooks to be told what has happened." }),
        shown,
        tokensCard(data, data.unitTree, reload, reveal),
        webhooksCard(data, reload, reveal));
    },
  });
}
