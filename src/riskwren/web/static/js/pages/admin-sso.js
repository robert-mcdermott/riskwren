// Admin → Single sign-on: whether it is set up, how, and which of the provider's application
// roles or groups give which roles here. Single sign-on is optional; local accounts always work.

import { get, post, put } from "../core/api.js";
import { button, h, icon, iconButton } from "../core/dom.js";
import { unitOptions, units } from "../core/lookups.js";
import { banner, submit } from "../components/form.js";
import { toast } from "../components/toast.js";
import { alert, card, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

// role, what it is called, whether it is for a unit ("unit"), may be ("optional"), or never is
const ROLES = [
  ["member", "Works in a unit", "unit"], ["steward", "Steward of a unit", "unit"], ["leader", "Leader of a unit", "unit"],
  ["assessor", "Assessor", "optional"], ["manager", "Manager", "optional"],
  ["auditor", "Auditor", "never"], ["admin", "Administrator", "never"],
];
const LIMITS = [["", "The lowest rating that needs acceptance"], ["moderate", "Accepts up to Moderate"], ["high", "Accepts up to High"], ["critical", "Accepts up to Critical"]];
const scopeOf = (role) => ROLES.find(([key]) => key === role)?.[2] ?? "never";

function connection(data) {
  if (!data.enabled) {
    return card({ title: "Connection", actions: pill("Not set up") },
      h("div", { class: "stack" },
        h("p", {}, "People sign in with an email address and a password that RiskWren keeps. Nothing more is needed. To let them also sign in with the account your organization already gives them, connect an OpenID Connect provider such as Microsoft Entra ID."),
        h("ol", { class: "steps-list" },
          h("li", {}, "Register RiskWren with your identity provider as a web application, with this redirect address:",
            h("div", {}, h("code", { class: "copyable" }, data.redirect_uri))),
          h("li", {}, "Put the provider's issuer address and the client ID it gives you in the ", h("code", {}, "[sso]"), " section of ", h("code", {}, "riskwren.toml"), "."),
          h("li", {}, "Put the client secret in the ", h("code", {}, data.secret_env), " environment variable, and restart RiskWren."),
          h("li", {}, "Come back here to check the connection and to say which of the provider's roles give which roles here."))));
  }
  const rows = [["Issuer", data.issuer], ["Client ID", data.client_id], ["Redirect address", data.redirect_uri],
    ["Roles are read from", `the “${data.roles_claim}” claim`],
    ["The button says", data.label],
    ["Passwords", data.local_sign_in ? "Anyone with a password may still use it" : "Kept for administrators only"],
    ["First sign-in", data.create_accounts ? "Makes an account" : "Only for people who already have an account"],
    ["Joining existing accounts", data.trust_email ? "By the address the provider sends" : "Only by an address the provider marks as verified"]];
  const result = h("div", { class: "stack", "aria-live": "polite" });
  const check = button("Check the connection");
  check.addEventListener("click", async () => {
    check.disabled = true;
    try {
      const found = (await post("/api/v1/sso/check", {})).data;
      result.replaceChildren(...found.steps.map((step) => alert(step.ok ? "ok" : "danger", icon(step.ok ? "check" : "alert"),
        h("div", {}, h("strong", {}, step.name), h("div", {}, step.detail)))));
    } catch (error) {
      result.replaceChildren(alert("danger", icon("alert"), h("div", {}, error.detail ?? error.message)));
    }
    check.disabled = false;
  });
  return card({ title: "Connection", actions: pill("Set up", "ok"),
    footer: h("div", { class: "row" }, check, h("span", { class: "subtle" }, "These are set in riskwren.toml on the server, not here.")) },
  h("div", { class: "stack" },
    h("dl", { class: "dl" }, rows.map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)])),
    result));
}

function mappings(data, reload) {
  const body = h("tbody");
  const rows = [];
  const add = (mapping = { claim_value: "", role: "member", org_unit_id: "", accept_limit: "" }) => {
    const value = h("input", { class: "input", value: mapping.claim_value, "aria-label": "Application role or group", placeholder: "As the provider sends it" });
    const role = h("select", { class: "select", "aria-label": "Role in RiskWren" },
      ROLES.map(([key, text]) => h("option", { value: key, selected: key === mapping.role }, text)));
    const choices = (blank) => unitOptions(data.units.tree, { blank }).map(([key, text]) =>
      h("option", { value: key, selected: String(key) === String(mapping.org_unit_id ?? "") }, text));
    const unit = h("select", { class: "select", "aria-label": "Unit" });
    const limit = h("select", { class: "select", "aria-label": "What a leader may accept" },
      LIMITS.map(([key, text]) => h("option", { value: key, selected: key === (mapping.accept_limit ?? "") }, text)));
    const scope = h("td");
    const sync = () => {
      const kind = scopeOf(role.value);
      unit.replaceChildren(...choices(kind === "optional" ? "The whole organization" : "Choose a unit"));
      scope.replaceChildren(...(kind === "never" ? [h("span", { class: "subtle" }, "The whole organization")]
        : role.value === "leader" ? [h("div", { class: "stack" }, unit, limit)] : [unit]));
    };
    role.addEventListener("change", sync);
    sync();
    const row = { value, role, unit, limit };
    const tr = h("tr", {}, h("td", {}, value), h("td", {}, role), scope,
      h("td", { class: "cell-actions" }, iconButton("trash", "Remove this mapping", { onclick: () => {
        rows.splice(rows.indexOf(row), 1);
        tr.remove();
      } })));
    rows.push(row);
    body.append(tr);
  };
  data.mappings.forEach((mapping) => add(mapping));
  const problem = banner();
  const save = button("Save", { kind: "btn-primary" });
  save.addEventListener("click", async () => {
    const done = await submit({ button: save, banner: problem, run: () => put("/api/v1/sso/mappings", {
      mappings: rows.filter((row) => row.value.value.trim()).map((row) => ({
        claim_value: row.value.value.trim(), role: row.role.value,
        org_unit_id: scopeOf(row.role.value) !== "never" && row.unit.value ? Number(row.unit.value) : null,
        accept_limit: row.role.value === "leader" ? row.limit.value || null : null })) }) });
    if (done) {
      toast("Saved. The roles apply the next time each person signs in.");
      reload();
    }
  });
  return card({ title: "Roles from the provider",
    footer: h("div", { class: "row" }, save, button("Add a mapping", { iconName: "plus", onclick: () => add() })) },
  h("div", { class: "stack" },
    h("p", { class: "muted" }, "Each line gives a role here to everyone the provider says holds an application role or is in a group. Roles given this way are set again at every sign-in, so taking the role away at the provider takes it away here. Roles given by hand under People are left alone, and the last administrator is never removed."),
    problem,
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Application role or group"), h("th", { scope: "col" }, "Role in RiskWren"),
        h("th", { scope: "col" }, "For"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Remove")))),
      body))));
}

export function adminSso(main) {
  return show(main, {
    title: "Single sign-on",
    load: async () => {
      const [sso, unitIndex] = await Promise.all([get("/api/v1/sso", null, { fresh: true }), units()]);
      return { ...sso.data, units: unitIndex };
    },
    view: (data, reload) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Admin", title: "Single sign-on", lede: "Optional. Let people sign in with the account your organization already gives them, beside the accounts RiskWren keeps." }),
      connection(data),
      data.enabled ? mappings(data, reload)
        : alert("info", icon("info"), h("div", {}, "Which of the provider's roles give which roles here can be set once the connection is in place."))),
  });
}
