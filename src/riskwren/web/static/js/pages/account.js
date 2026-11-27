// Your account: your details and your password.

import { get, patch, post, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { titleCase } from "../core/format.js";
import { session } from "../core/session.js";
import { banner, field, select, submit } from "../components/form.js";
import { toast } from "../components/toast.js";
import { card, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

function details(account, reload) {
  const name = field("Name", { value: account.display_name, autocomplete: "name", required: true });
  const title = field("Title", { value: account.title ?? "", hint: "Your role at the organization, such as Lab Manager." });
  const problem = banner();
  const save = button("Save", { kind: "btn-primary", type: "submit" });
  return card({ title: "Your details" }, h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const done = await submit({ button: save, fields: { display_name: name, title }, banner: problem,
      run: () => patch(`/api/v1/accounts/${account.id}`, { display_name: name.input.value, title: title.input.value }) });
    if (done) {
      toast("Your details were saved.");
      reload();
    }
  } }, problem, name.node, title.node,
  h("div", { class: "field" }, h("div", { class: "label" }, "Email address"), h("div", { class: "muted" }, account.email)),
  h("div", { class: "form-actions" }, save)));
}

function password(account) {
  if (!account.has_password) {
    return card({ title: "Password" }, h("p", { class: "muted" },
      "You sign in through your organization's sign-in service, so there is no password to change here."));
  }
  const current = field("Current password", { type: "password", autocomplete: "current-password", required: true });
  const next = field("New password", { type: "password", autocomplete: "new-password", required: true,
    hint: "At least 12 characters. A few unrelated words make a good one." });
  const problem = banner();
  const save = button("Change password", { kind: "btn-primary", type: "submit" });
  return card({ title: "Password" }, h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const done = await submit({ button: save, fields: { current_password: current, new_password: next, password: next }, banner: problem,
      run: () => post("/api/v1/session/password", { current_password: current.input.value, new_password: next.input.value }) });
    if (done) {
      current.input.value = "";
      next.input.value = "";
      toast("Your password was changed. Your other sessions were signed out.");
    }
  } }, problem, current.node, next.node, h("div", { class: "form-actions" }, save)));
}

const EMAIL_CHOICES = { immediate: "Each notice as it happens", digest: "One summary a day", none: "No email" };

/** How notices reach you by email. Shown only where email has been set up. */
function emailChoice(preferences) {
  if (!preferences.email) return null;
  const choice = select("Send me", preferences.choices.map((key) => [key, EMAIL_CHOICES[key] ?? key]), { value: preferences.email_notices,
    hint: `To ${preferences.address}. Everything is always listed under the bell as well.` });
  const problem = banner();
  const save = button("Save", { kind: "btn-primary", type: "submit" });
  return card({ title: "Email" }, h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const done = await submit({ button: save, fields: { email_notices: choice }, banner: problem,
      run: () => put("/api/v1/session/preferences", { email_notices: choice.input.value }) });
    if (done) toast("Saved.");
  } }, problem, choice.node, h("div", {}, save)));
}

export function account(main) {
  const me = session();
  return show(main, {
    title: "Your account",
    narrow: true,
    load: async () => {
      const [own, preferences] = await Promise.all([get(`/api/v1/accounts/${me.account.id}`, null, { fresh: true }),
        get("/api/v1/session/preferences", null, { fresh: true })]);
      return { ...own.data, preferences: preferences.data };
    },
    view: (data, reload) => h("div", { class: "stack-lg" },
      pageHeader({ title: "Your account" }),
      details(data, reload),
      password(data),
      emailChoice(data.preferences),
      card({ title: "Your roles" }, h("div", { class: "stack" },
        h("div", { class: "row-sm wrap" }, me.roles.map((role) => pill(titleCase(role), role === "member" ? "" : "accent"))),
        h("p", { class: "muted" }, "Roles are given by an administrator. They decide what you can see and do.")))),
  });
}
