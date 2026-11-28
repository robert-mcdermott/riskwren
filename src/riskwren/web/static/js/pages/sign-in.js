// The sign-in page, shown whenever nobody is signed in.

import { post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { wren } from "../core/icons.js";
import { brand, footerLinks } from "../components/shell.js";
import { banner, field, submit } from "../components/form.js";
import { avatar } from "../components/ui.js";
import { setTitle } from "./page.js";

const POINTS = [
  "One connected register of risks, controls, and obligations",
  "Effort in proportion to what is at stake",
  "A record of every judgment, and the reasons for it",
];

const SSO_PROBLEMS = {
  cancelled: "Sign-in was cancelled at your organization's sign-in page.",
  expired: "That sign-in took too long or was already used. Please try again.",
  unavailable: "Your organization's sign-in service could not be reached. Try again in a few minutes.",
  refused: "Your organization account could not be used here. Ask whoever looks after RiskWren to check your access.",
  failed: "Sign-in did not complete. Please try again.",
};

function safeNext() {
  // Only a path inside this site. A backslash or a control character can make a browser read
  // "/\\evil.example" as another site, so the address is resolved and its origin compared.
  const next = new URLSearchParams(window.location.search).get("next") || "/";
  if (!next.startsWith("/") || next.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(next)) return "/";
  try {
    const target = new URL(next, window.location.origin);
    return target.origin === window.location.origin ? target.pathname + target.search + target.hash : "/";
  } catch {
    return "/";
  }
}

export function signIn(root, meta) {
  setTitle("Sign in");
  const email = field("Email address", { type: "email", autocomplete: "username", required: true, name: "email" });
  const password = field("Password", { type: "password", autocomplete: "current-password", required: true, name: "password" });
  const problem = banner();
  const go = button("Sign in", { kind: "btn-primary btn-block", type: "submit" });
  const form = h("form", { class: "stack", novalidate: true, onsubmit: async (event) => {
    event.preventDefault();
    const done = await submit({ button: go, fields: { email, password }, banner: problem,
      run: () => post("/api/v1/session", { email: email.input.value, password: password.input.value }) });
    if (done) window.location.assign(safeNext());
    else password.input.select();
  } }, problem, email.node, password.node, go);

  const sample = meta.demo ? h("section", { class: "demo-people", "aria-labelledby": "demo-people-title" },
    h("h2", { id: "demo-people-title" }, "Explore the demo"),
    h("p", { class: "muted" }, "This is a fictional organization. Choose someone to sign in as; no password is needed."),
    h("ul", {}, meta.demo.accounts.map((person) => h("li", {},
      h("button", { type: "button", class: "demo-person", onclick: async (event) => {
        const chosen = event.currentTarget;
        chosen.disabled = true;
        try {
          await post("/api/v1/session/demo", { email: person.email });
          window.location.assign(safeNext());
        } catch (error) {
          chosen.disabled = false;
          problem.textContent = error.detail || "That did not work.";
          problem.hidden = false;
        }
      } },
      avatar(person.name),
      h("span", { class: "grow" },
        h("span", { class: "cell-main" }, person.role, h("span", { class: "subtle" }, ` · ${person.name}, ${person.title}`)),
        h("span", { class: "cell-sub" }, person.about)),
      icon("chevron-right", "icon icon-sm")))))) : null;

  // Single sign-on is offered only where it has been set up. The password form stays, for
  // everyone or for administrators, so there is always a way in.
  const failed = new URLSearchParams(window.location.search).get("sso");
  const sso = meta.sso && !sample ? h("div", { class: "stack" },
    failed ? h("div", { class: "alert alert-danger", role: "alert" }, SSO_PROBLEMS[failed] ?? SSO_PROBLEMS.failed) : null,
    h("a", { class: "btn btn-primary btn-block", href: `/api/v1/sso/start?next=${encodeURIComponent(safeNext())}` }, meta.sso.label)) : null;
  const local = !sso ? form : h("details", { class: "local-sign-in", open: failed === "refused" ? "" : null },
    h("summary", {}, meta.sso.local_sign_in ? "Sign in with a password instead" : "Administrator sign-in"),
    h("div", { class: "stack" }, h("div", {}), form));

  const organization = meta.branding.organization_name;
  root.replaceChildren(h("div", { class: "sign-in" },
    h("main", { class: "sign-in-form", id: "main" }, h("div", {},
      h("div", { class: "sign-in-brand" }, brand(meta)),
      h("h1", {}, "Sign in"),
      h("p", { class: "muted" }, organization ? `Risk and compliance at ${organization}.` : "Welcome back."),
      meta.branding.sign_in_message ? h("p", { class: "sign-in-message" }, meta.branding.sign_in_message) : null,
      sample ? h("div", { class: "stack-lg" }, h("div", {}), problem, sample)
        : h("div", { class: "stack-lg" }, h("div", {}), sso, local),
      h("p", { class: "sign-in-foot" }, sample ? `Demo data, built ${meta.demo.built_on}. Nothing here is real.`
        : sso ? "Trouble signing in? Ask whoever looks after RiskWren in your organization."
          : "Trouble signing in? Ask an administrator to reset your password."),
      footerLinks(meta),
      meta.report_without_name ? h("p", { class: "sign-in-foot" }, "Something to report, and rather not give your name? ",
        h("a", { href: "/report" }, "Report it without signing in"), ".") : null)),
    meta.branding.sign_in_image ? h("aside", { class: "sign-in-art sign-in-picture", "aria-hidden": "true" },
      h("img", { src: meta.branding.sign_in_image, alt: "" }))
    : h("aside", { class: "sign-in-art", "aria-hidden": "true" },
      wren("wren"),
      h("blockquote", {}, "What could go wrong, and what are we doing about it?"),
      h("p", {}, "The least that proves it: a short task for each owner, and a register leadership can rely on."),
      h("ul", {}, POINTS.map((point) => h("li", {}, icon("check"), point))))));
  if (!sample && !sso) email.input.focus();
}
