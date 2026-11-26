// Home: what you owe, and, for administrators of a new installation, how to set it up.

import { get } from "../core/api.js";
import { h, icon } from "../core/dom.js";
import { greeting, titleCase } from "../core/format.js";
import { can, session } from "../core/session.js";
import { avatar, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

function setup(data, meta) {
  const steps = [
    { done: data.units.length > 0, title: "Describe your organization",
      text: "Add your divisions, departments, and labs, or import them from a spreadsheet.",
      href: "/admin/units", action: "Units" },
    { done: data.accounts.length > 1, title: "Add the people who will run the program",
      text: "Give manager, assessor, auditor, leader, and steward roles to the right people.",
      href: "/admin/people", action: "People" },
    { done: Boolean(meta.branding.organization_name || meta.branding.logo_light || meta.branding.accent),
      title: "Make it yours", text: "Set your organization's name, logo, and colors.",
      href: "/admin/appearance", action: "Appearance" },
  ];
  const left = steps.filter((step) => !step.done).length;
  return card({ title: left ? "Set up your installation" : "Your installation is set up", flush: true,
    actions: pill(left ? `${steps.length - left} of ${steps.length} done` : "All done", left ? "info" : "ok") },
  h("ul", { class: "checklist" }, steps.map((step) => h("li", { "data-done": String(step.done) },
    h("span", { class: "check-mark" }, icon("check", "icon icon-sm")),
    h("div", { class: "grow" }, h("div", { class: "cell-main" }, step.title), h("div", { class: "cell-sub" }, step.text)),
    h("a", { class: "btn btn-sm", href: step.href }, step.action)))));
}

export function home(main, meta) {
  const me = session();
  return show(main, {
    title: "Home",
    load: async () => {
      if (!can("admin")) return null;
      const [units, accounts] = await Promise.all([get("/api/v1/units"), get("/api/v1/accounts")]);
      return { units: units.data.units, accounts: accounts.data };
    },
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ title: `${greeting()}, ${me.account.name.split(" ")[0]}`,
        lede: meta.branding.organization_name ? `Risk and compliance at ${meta.branding.organization_name}.` : null }),
      data ? setup(data, meta) : null,
      h("div", { class: "split" },
        card({ title: "Waiting on you", flush: true },
          emptyState({ iconName: "check", title: "Nothing needs your attention",
            text: "Reviews, actions, and acceptances that are yours to act on will be listed here, overdue first." })),
        card({ title: "Your access" },
          h("div", { class: "stack" },
            h("div", { class: "row" }, avatar(me.account.name, true), h("div", {},
              h("div", { class: "cell-main" }, me.account.name), h("div", { class: "cell-sub" }, me.account.email))),
            h("div", { class: "row-sm wrap" }, me.roles.map((role) => pill(titleCase(role), role === "member" ? "" : "accent"))),
            h("a", { href: "/account" }, "Your account"))))),
  });
}
