// Admin → People: accounts, roles, and the units people work in.

import { get, patch, post, put } from "../core/api.js";
import { button, h, uid } from "../core/dom.js";
import { plural, titleCase } from "../core/format.js";
import { query, setQuery } from "../core/router.js";
import { session } from "../core/session.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { openImport } from "../components/importer.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { avatar, card, emptyState, pageHeader, pill, statusPill } from "../components/ui.js";
import { show } from "./page.js";

const GLOBAL_ROLES = ["admin", "auditor"];
// Roles that may be held for the whole organization or for chosen units.
const WIDE_ROLES = ["manager", "assessor"];
// Until the scoring method arrives with its own rating names, the limits a leader may be given.
const LIMITS = [["", "The lowest rating that needs acceptance"], ["moderate", "Up to Moderate"], ["high", "Up to High"], ["critical", "Up to Critical"]];

function describe(grant, unitsById) {
  const unit = grant.org_unit_id == null ? null : unitsById.get(grant.org_unit_id)?.name ?? "a unit";
  if (grant.role === "steward") return `Steward of ${unit}`;
  if (grant.role === "leader") return `Leader of ${unit}${grant.accept_limit ? `, accepts up to ${titleCase(grant.accept_limit)}` : ""}`;
  if (WIDE_ROLES.includes(grant.role) && unit) return `${titleCase(grant.role)} for ${unit}`;
  return titleCase(grant.role);
}

function unitPicker(label, units, chosen, hint) {
  const id = uid("units");
  const boxes = units.map((unit) => checkbox(unit.name, { checked: chosen.includes(unit.id), value: unit.id }));
  const node = h("fieldset", { "aria-describedby": hint ? id : null },
    h("legend", {}, label),
    hint ? h("p", { class: "hint subtle", id }, hint) : null,
    units.length ? h("div", { class: "stack-sm" }, boxes.map((box) => box.node)) : h("p", { class: "muted" }, "Add units first, under Admin → Units."));
  return { node, values: () => boxes.filter((box) => box.input.checked).map((box) => Number(box.input.value)) };
}

function rolesEditor(account, roles, units) {
  const local = account.roles.filter((grant) => grant.source === "local");
  const has = (role) => local.some((grant) => grant.role === role);
  const about = (role) => roles.find((r) => r.role === role)?.description;
  const globals = GLOBAL_ROLES.map((role) => ({ role, box: checkbox(titleCase(role), { checked: has(role), hint: about(role) }) }));
  // A manager or assessor covers the whole organization, or only the units ticked.
  const wide = WIDE_ROLES.map((role) => {
    const everywhere = checkbox(`${titleCase(role)} for the whole organization`,
      { checked: local.some((g) => g.role === role && g.org_unit_id == null), hint: about(role) });
    const some = unitPicker(`${titleCase(role)} for`, units,
      local.filter((g) => g.role === role && g.org_unit_id != null).map((g) => g.org_unit_id),
      "Or only for these units and every unit within them.");
    return { role, everywhere, some };
  });
  const stewardOf = unitPicker("Steward of", units, local.filter((g) => g.role === "steward").map((g) => g.org_unit_id),
    "A steward keeps the records of these units, and every unit within them, complete and current.");
  const leads = local.filter((g) => g.role === "leader");
  const leaderOf = unitPicker("Leader of", units, leads.map((g) => g.org_unit_id),
    "A leader sees these units and every unit within them, and may accept their risks.");
  const limit = select("May accept risks", LIMITS, { value: leads[0]?.accept_limit ?? "",
    hint: "The highest rating this person may accept as a leader. Nobody may accept a risk they own." });
  const fromProvider = account.roles.filter((grant) => grant.source !== "local");
  const node = h("div", { class: "stack-lg" },
    h("fieldset", {}, h("legend", {}, "Roles across the organization"), h("div", { class: "stack" }, globals.map((g) => g.box.node))),
    wide.map((w) => h("div", { class: "stack" }, w.everywhere.node, w.some.node)),
    stewardOf.node,
    h("div", { class: "stack" }, leaderOf.node, limit.node),
    fromProvider.length ? h("p", { class: "subtle" }, "Also, from your sign-in service: ",
      fromProvider.map((g) => titleCase(g.role)).join(", "), ". Those are managed there.") : null);
  const values = () => [
    ...globals.filter((g) => g.box.input.checked).map((g) => ({ role: g.role })),
    ...wide.flatMap((w) => (w.everywhere.input.checked ? [{ role: w.role }]
      : w.some.values().map((id) => ({ role: w.role, org_unit_id: id })))),
    ...stewardOf.values().map((id) => ({ role: "steward", org_unit_id: id })),
    ...leaderOf.values().map((id) => ({ role: "leader", org_unit_id: id, accept_limit: limit.input.value || null })),
  ];
  return { node, values };
}

function addPerson({ reload }) {
  openOverlay({
    title: "Add a person",
    subtitle: "They can be named on records straight away.",
    render: (body, footer, close) => {
      const name = field("Name", { required: true, autocomplete: "off" });
      const email = field("Email address", { type: "email", required: true, autocomplete: "off" });
      const title = field("Title", {});
      const password = field("Password", { type: "password", autocomplete: "new-password",
        hint: "Leave empty to add them as invited: they sign in once you set a password for them, or through your sign-in service." });
      const problem = banner();
      const save = button("Add", { kind: "btn-primary" });
      const form = h("form", { class: "stack", novalidate: true, onsubmit: (event) => event.preventDefault() },
        problem, name.node, email.node, title.node, password.node);
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { display_name: name, email, title, password }, banner: problem,
          run: () => post("/api/v1/accounts", { display_name: name.input.value, email: email.input.value,
            title: title.input.value || null, password: password.input.value || null }) });
        if (done) {
          close();
          toast(`${done.data.display_name} was added. Give them roles and units next.`);
          await reload();
          setQuery({ person: done.data.id });
        }
      });
      body.append(form);
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function editPerson({ account, roles, units, reload }) {
  const mine = account.id === session().account.id;
  openOverlay({
    title: account.display_name,
    subtitle: account.email,
    render: (body, footer, close) => {
      const name = field("Name", { value: account.display_name, required: true });
      const title = field("Title", { value: account.title ?? "" });
      const worksIn = unitPicker("Works in", units, account.units.map((u) => u.org_unit_id),
        "The first unit ticked is their main one. It sets the default unit on the records they add.");
      const editor = rolesEditor(account, roles, units);
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { display_name: name, title }, banner: problem, run: async () => {
          await patch(`/api/v1/accounts/${account.id}`, { display_name: name.input.value, title: title.input.value });
          await put(`/api/v1/accounts/${account.id}/units`, { unit_ids: worksIn.values() });
          return put(`/api/v1/accounts/${account.id}/roles`, { roles: editor.values() });
        } });
        if (done) {
          close();
          toast("Saved.");
          reload();
        }
      });
      const setPassword = button(account.has_password ? "Reset password" : "Set a password", { iconName: "key", onclick: () => {
        const next = field("New password", { type: "password", autocomplete: "new-password", hint: "At least 12 characters. Tell them what it is; they can change it once signed in." });
        const bad = banner();
        openOverlay({ title: `Password for ${account.display_name}`, kind: "dialog", render: (b, f, shut) => {
          const go = button("Set password", { kind: "btn-primary" });
          go.addEventListener("click", async () => {
            const ok = await submit({ button: go, fields: { new_password: next, password: next }, banner: bad,
              run: () => post(`/api/v1/accounts/${account.id}/password`, { new_password: next.input.value }) });
            if (ok) {
              shut();
              toast("The password was set, and their sessions were signed out.");
              reload();
            }
          });
          b.append(h("div", { class: "stack" }, bad, next.node));
          f.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: shut })));
          f.hidden = false;
        } });
      } });
      const toggle = account.status === "disabled"
        ? button("Let them sign in again", { onclick: async () => {
          await patch(`/api/v1/accounts/${account.id}`, { status: "active" });
          close();
          toast(`${account.display_name} can sign in again.`);
          reload();
        } })
        : button("Disable", { kind: "btn-danger", onclick: () => confirmAction({
          title: `Disable ${account.display_name}?`,
          text: "They will be signed out and unable to sign in. Their records and everything they did stay in the history.",
          confirmLabel: "Disable", danger: true,
          run: async () => {
            try {
              await patch(`/api/v1/accounts/${account.id}`, { status: "disabled" });
              toast(`${account.display_name} was disabled.`);
              reload();
            } catch (error) {
              toast(error.detail || "That did not work.");
            }
          } }) });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("div", { class: "row" }, statusPill(account.status),
          account.has_password ? null : pill("No password", "warn")),
        name.node, title.node, worksIn.node, editor.node,
        h("div", { class: "stack-sm" }, h("div", { class: "label" }, "Sign-in"),
          h("div", { class: "row wrap" }, mine ? null : setPassword, mine || account.status === "invited" ? null : toggle),
          mine ? h("p", { class: "subtle" }, "This is you. Change your own password from your account page.") : null)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function adminPeople(main) {
  return show(main, {
    title: "People",
    load: async () => {
      const [accounts, roles, units] = await Promise.all([
        get("/api/v1/accounts", null, { fresh: true }), get("/api/v1/roles"), get("/api/v1/units", null, { fresh: true })]);
      return { accounts: accounts.data, roles: roles.data, units: units.data.units };
    },
    view: (data, reload) => {
      const unitsById = new Map(data.units.map((unit) => [unit.id, unit]));
      const context = { roles: data.roles, units: data.units, reload };
      const open = Number(query().get("person"));
      const chosen = data.accounts.find((account) => account.id === open);
      if (chosen) queueMicrotask(() => editPerson({ account: chosen, ...context }));
      const search = h("input", { class: "input", type: "search", placeholder: "Filter by name or email", "aria-label": "Filter people" });
      const rows = h("tbody");
      const draw = () => {
        const words = search.value.toLowerCase().trim();
        const shown = data.accounts.filter((a) => !words || `${a.display_name} ${a.email}`.toLowerCase().includes(words));
        rows.replaceChildren(...shown.map((account) => h("tr", {},
          h("td", {}, h("div", { class: "row" }, avatar(account.display_name),
            h("div", {}, h("button", { type: "button", class: "btn-ghost cell-main link-button", onclick: () => editPerson({ account, ...context }) }, account.display_name),
              h("div", { class: "cell-sub" }, account.email)))),
          h("td", {}, account.title ?? ""),
          h("td", {}, account.units.map((u) => unitsById.get(u.org_unit_id)?.name).filter(Boolean).join(", ")),
          h("td", {}, h("div", { class: "row-sm wrap" }, account.roles.length
            ? account.roles.map((grant) => pill(describe(grant, unitsById), "accent")) : pill("Member"))),
          h("td", {}, statusPill(account.status)),
          h("td", { class: "actions" }, button("Edit", { kind: "btn-sm", onclick: () => editPerson({ account, ...context }) })))));
        if (!shown.length) rows.replaceChildren(h("tr", {}, h("td", { colspan: 6 }, emptyState({ iconName: "search", title: "Nobody matches" }))));
      };
      search.addEventListener("input", draw);
      draw();
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "People",
          lede: "Everyone who can sign in, or be named on a record, and what their roles let them do.",
          actions: [
            button("Import", { iconName: "upload", onclick: () => openImport({
              kind: "people", title: "Import people",
              intro: "People are matched by email address. New people are added as invited.",
              sample: "email,name,title,unit_codes,roles\npriya.nair@northmere.example,Priya Nair,Lab Manager,HALE,steward=unit:HALE\nwei.chen@northmere.example,Wei Chen,Division Director,NMI,\"leader=unit:IMM,limit:high\"",
              onDone: reload }) }),
            button("Add a person", { kind: "btn-primary", iconName: "plus", onclick: () => addPerson(context) })] }),
        card({ title: plural(data.accounts.length, "person", "people"), flush: true, actions: h("div", { class: "search-slot" }, search) },
          h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, ["Name", "Title", "Works in", "Roles", "Status", ""].map((label) =>
              h("th", { scope: "col" }, label || h("span", { class: "sr-only" }, "Actions"))))),
            rows))));
    },
  });
}
