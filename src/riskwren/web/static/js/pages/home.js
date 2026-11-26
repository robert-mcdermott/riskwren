// Home: what you owe, and, for administrators of a new installation, how to set it up.

import { get } from "../core/api.js";
import { h, icon } from "../core/dom.js";
import { date, greeting, titleCase } from "../core/format.js";
import { can, session } from "../core/session.js";
import { listHref, statTile } from "../components/charts.js";
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

const KINDS = {
  assess: ["risk", "Assess"], review: ["risk", "Review"], decide: ["alert", "Decide"], action: ["check", "Do"],
  rate: ["control", "Rate"], acceptance: ["accept", "Renew"], orphan: ["user", "Assign"],
};

function owed(listing) {
  if (!listing.items.length) {
    return emptyState({ iconName: "check", title: "Nothing needs your attention",
      text: "Reviews, actions, and decisions that are yours appear here, overdue first." });
  }
  return h("ul", { class: "owed" }, listing.items.map((item) => {
    const [iconName, verb] = KINDS[item.kind] ?? ["dot", ""];
    return h("li", {}, h("a", { class: "owed-item", href: item.href },
      h("span", { class: "owed-icon", "data-kind": item.kind }, icon(iconName)),
      h("span", { class: "grow" }, h("span", { class: "cell-main" }, item.title), h("span", { class: "cell-sub owed-detail" }, item.detail)),
      item.due_on ? h("span", { class: `nowrap${item.overdue ? " overdue" : " muted"}` }, item.overdue ? "Was due " : "Due ", date(item.due_on)) : h("span", { class: "muted" }, verb)));
  }));
}

function summary(figures) {
  const tile = (figure, label, path, tone) => statTile({ value: figure.count, label, href: listHref(path, figure.filters), tone });
  return h("div", { class: "tiles" },
    tile(figures.needs_decision, "Risks need a decision", "/risks", "danger"),
    tile(figures.above_appetite, "Risks above appetite", "/risks", ""),
    tile(figures.review_overdue, "Reviews overdue", "/risks", "warn"),
    tile(figures.actions_overdue, "Actions overdue", "/actions", "danger"));
}

export function home(main, meta) {
  const me = session();
  return show(main, {
    title: "Home",
    load: async () => {
      const listing = (await get("/api/v1/home", null, { fresh: true })).data;
      if (!can("admin")) return { listing, setup: null };
      const [units, accounts] = await Promise.all([get("/api/v1/units"), get("/api/v1/accounts")]);
      return { listing, setup: { units: units.data.units, accounts: accounts.data } };
    },
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ title: `${greeting()}, ${me.account.name.split(" ")[0]}`,
        lede: meta.branding.organization_name ? `Risk and compliance at ${meta.branding.organization_name}.` : null }),
      data.setup ? setup(data.setup, meta) : null,
      data.listing.summary ? summary(data.listing.summary) : null,
      h("div", { class: "split" },
        card({ title: data.listing.overdue ? `Waiting on you: ${data.listing.overdue} overdue` : "Waiting on you", flush: true }, owed(data.listing)),
        card({ title: "Your access" },
          h("div", { class: "stack" },
            h("div", { class: "row" }, avatar(me.account.name, true), h("div", {},
              h("div", { class: "cell-main" }, me.account.name), h("div", { class: "cell-sub" }, me.account.email))),
            h("div", { class: "row-sm wrap" }, me.roles.map((role) => pill(titleCase(role), role === "member" ? "" : "accent"))),
            h("a", { href: "/account" }, "Your account"))))),
  });
}
