// The app shell: sidebar, top bar, and the place pages are drawn.

import { del, get } from "../core/api.js";
import { h, icon, iconButton } from "../core/dom.js";
import { wren } from "../core/icons.js";
import { onNavigate } from "../core/router.js";
import { can, session } from "../core/session.js";
import { mode, setMode } from "../core/prefs.js";
import { openAppearance } from "./appearance.js";
import { openPalette } from "./cmdk.js";

const quickFind = async (text) => (await import("../pages/find.js")).quickFind(text);
import { avatar } from "./ui.js";

// Each entry appears only for people who can use it. Sections arrive as the product grows.
export const NAV = [
  { items: [{ href: "/", label: "Home", iconName: "home", exact: true }] },
  {
    heading: "Risks",
    items: [
      { href: "/risks", label: "Register", iconName: "risk" },
      { href: "/heat-map", label: "Heat map", iconName: "grid" },
      { href: "/indicators", label: "Indicators", iconName: "chart" },
      { href: "/risk-analyses", label: "Analyses", iconName: "scope" },
      { href: "/plans", label: "Treatment plans", iconName: "plan" },
      { href: "/acceptances", label: "Acceptances", iconName: "accept" },
      { href: "/actions", label: "Actions", iconName: "check" },
    ],
  },
  {
    heading: "Controls",
    items: [
      { href: "/controls", label: "Library", iconName: "control" },
    ],
  },
  {
    heading: "Compliance",
    items: [
      { href: "/frameworks", label: "Frameworks", iconName: "framework" },
      { href: "/scopes", label: "Scopes", iconName: "scope" },
      { href: "/evidence", label: "Evidence", iconName: "evidence" },
      { href: "/assessments", label: "Assessments", iconName: "assessment" },
      { href: "/issues", label: "Issues", iconName: "issue" },
      { href: "/exceptions", label: "Exceptions", iconName: "exception" },
      { href: "/campaigns", label: "Campaigns", iconName: "bell", when: ["assess", "read_all"] },
    ],
  },
  {
    heading: "Policies",
    items: [
      { href: "/library", label: "Policy library", iconName: "document" },
      { href: "/documents", label: "Documents", iconName: "edit", when: ["steward", "lead", "assess", "read_all"] },
    ],
  },
  {
    heading: "Inventory",
    items: [
      { href: "/processes", label: "Processes", iconName: "process" },
      { href: "/systems", label: "Systems", iconName: "system" },
      { href: "/third-parties", label: "Third parties", iconName: "third_party" },
      { href: "/information", label: "Information", iconName: "information" },
    ],
  },
  {
    heading: "Reports",
    items: [
      { href: "/compliance", label: "Compliance", iconName: "shield-check" },
      { href: "/dashboard", label: "Risk", iconName: "chart" },
      { href: "/tidy", label: "Tidy", iconName: "check" },
      { href: "/history", label: "History", iconName: "history", when: "read_all" },
    ],
  },
  {
    heading: "Admin",
    items: [
      { href: "/admin/program", label: "Program", iconName: "program", when: "configure" },
      { href: "/questionnaires", label: "Questionnaires", iconName: "file", when: "configure" },
      { href: "/admin/people", label: "People", iconName: "people", when: "admin" },
      { href: "/admin/units", label: "Units", iconName: "units", when: "admin" },
      { href: "/admin/appearance", label: "Appearance", iconName: "appearance", when: "admin" },
      { href: "/admin/sso", label: "Single sign-on", iconName: "key", when: "admin" },
      { href: "/admin/scheduled-work", label: "Scheduled work", iconName: "history", when: "admin" },
    ],
  },
];

export function visibleNav() {
  return NAV.map((group) => ({ ...group, items: group.items.filter((item) => !item.when || [item.when].flat().some((need) => can(need))) }))
    .filter((group) => group.items.length);
}

export function brand(meta, { large = false } = {}) {
  const b = meta.branding;
  const name = b.product_name;
  if (b.logo_light) {
    return [
      h("img", { class: "brand-logo only-light", src: b.logo_light, alt: name }),
      h("img", { class: "brand-logo only-dark", src: b.logo_dark || b.logo_light, alt: "" }),
    ];
  }
  // "RiskWren" is set as Risk + Wren; any other name is shown as it is.
  const words = name === "RiskWren" ? ["Risk", h("strong", {}, "Wren")] : [h("strong", {}, name)];
  return [wren(large ? "brand-mark" : "brand-mark"), h("span", { class: "brand-name" }, words)];
}

export async function signOut() {
  try {
    await del("/api/v1/session");
  } finally {
    window.location.assign("/");
  }
}

export function commands(meta) {
  const pages = visibleNav().flatMap((group) => group.items.map((item) => ({
    label: item.label, hint: group.heading ?? "Page", iconName: item.iconName, href: item.href,
  })));
  return [
    ...pages,
    { label: "Search", hint: "Page", iconName: "search", href: "/search", keywords: "find look" },
    { label: "Your account", hint: "Page", iconName: "user", href: "/account", keywords: "profile password" },
    { label: "Appearance…", hint: "Action", iconName: "appearance", run: () => openAppearance(meta), keywords: "theme palette colors" },
    { label: mode() === "dark" ? "Switch to light" : "Switch to dark", hint: "Action",
      iconName: mode() === "dark" ? "sun" : "moon", run: () => setMode(mode() === "dark" ? "light" : "dark"), keywords: "theme mode" },
    { label: "Sign out", hint: "Action", iconName: "logout", run: signOut },
  ];
}

function userMenu(meta) {
  const me = session();
  const anchor = h("div", { class: "menu-anchor" });
  let menu = null;
  const close = () => {
    menu?.remove();
    menu = null;
    toggle.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", outside, true);
    document.removeEventListener("keydown", onKey, true);
  };
  const outside = (event) => {
    if (!anchor.contains(event.target)) close();
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      close();
      toggle.focus();
    }
  };
  const item = (label, iconName, attrs) => h(attrs.href ? "a" : "button",
    { class: "menu-item", role: "menuitem", ...(attrs.href ? {} : { type: "button" }), ...attrs,
      onclick: (event) => {
        close();
        attrs.onclick?.(event);
      } }, icon(iconName), label);
  const toggle = h("button", { type: "button", class: "icon-button", "aria-haspopup": "menu", "aria-expanded": "false",
    "aria-label": `Account menu for ${me.account.name}`, title: me.account.name,
    onclick: () => {
      if (menu) {
        close();
        return;
      }
      menu = h("div", { class: "menu", role: "menu" },
        h("div", { class: "menu-head" }, h("div", { class: "cell-main" }, me.account.name),
          h("div", { class: "cell-sub" }, me.account.email)),
        h("div", { class: "menu-sep" }),
        item("Your account", "user", { href: "/account" }),
        item("Appearance…", "appearance", { onclick: () => openAppearance(meta) }),
        h("div", { class: "menu-sep" }),
        item("Sign out", "logout", { onclick: signOut }));
      anchor.append(menu);
      toggle.setAttribute("aria-expanded", "true");
      document.addEventListener("click", outside, true);
      document.addEventListener("keydown", onKey, true);
      menu.querySelector(".menu-item")?.focus();
    } }, avatar(me.account.name));
  anchor.append(toggle);
  return anchor;
}

/** Draw the shell into root and return the element pages are drawn in. */
export function mountShell(root, meta) {
  const main = h("main", { id: "main", tabindex: "-1" });
  const nav = h("nav", { class: "nav", "aria-label": "Main" });
  const brandLink = h("a", { class: "brand", href: "/", "aria-label": `${meta.branding.product_name} home` }, brand(meta));
  const shell = h("div", { class: "shell" });

  const drawNav = () => {
    const path = window.location.pathname;
    nav.replaceChildren(...visibleNav().map((group) => h("div", { class: "nav-group" },
      group.heading ? h("div", { class: "nav-heading" }, group.heading) : null,
      h("ul", {}, group.items.map((item) => {
        const here = item.exact ? path === item.href : path === item.href || path.startsWith(`${item.href}/`);
        return h("li", {}, h("a", { class: "nav-link", href: item.href, "aria-current": here ? "page" : null },
          icon(item.iconName), item.label));
      })))));
  };
  // How many notices are unread, beside the bell. Asked for again whenever the page changes.
  const count = h("span", { class: "bell-count", "aria-hidden": "true", hidden: true });
  const bell = h("a", { class: "icon-button notice-bell", href: "/notices", "aria-label": "Notices" }, icon("bell"), count);
  const showUnread = (unread) => {
    count.hidden = !unread;
    count.textContent = unread > 99 ? "99+" : String(unread);
    bell.setAttribute("aria-label", unread ? `Notices, ${unread} unread` : "Notices");
  };
  const askUnread = async () => {
    try {
      showUnread((await get("/api/v1/notices/count", null, { fresh: true })).data.unread);
    } catch {
      // The bell is a convenience: if the count cannot be had, it shows none.
    }
  };
  document.addEventListener("notices", (event) => showUnread(event.detail.unread));
  onNavigate(() => {
    drawNav();
    shell.removeAttribute("data-nav");
    askUnread();
  });
  drawNav();
  askUnread();

  const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
  const search = h("button", { type: "button", class: "search-button", "aria-label": "Open the command palette",
    onclick: () => openPalette(commands(meta), { find: quickFind }) },
  icon("search", "icon icon-sm"), h("span", {}, "Find or go to…"), h("kbd", {}, isMac ? "⌘K" : "Ctrl K"));

  const powered = meta.branding.show_powered_by && meta.branding.product_name !== "RiskWren"
    ? h("div", { class: "powered" }, "Powered by ", h("a", { href: "https://github.com/robert-mcdermott/riskwren", target: "_blank", rel: "noopener" }, "RiskWren"))
    : h("div", { class: "powered" }, meta.branding.organization_name || `Version ${meta.version}`);

  shell.append(
    h("aside", { class: "sidebar" }, brandLink, nav, h("div", { class: "sidebar-foot" }, powered)),
    h("div", { class: "main-column" },
      h("header", { class: "topbar" },
        iconButton("menu", "Menu", { class: "icon-button menu-toggle", onclick: () => {
          shell.setAttribute("data-nav", shell.getAttribute("data-nav") === "open" ? "" : "open");
        } }),
        search,
        h("div", { class: "spacer row-sm" },
          meta.demo ? h("span", { class: "demo-flag", title: "A fictional organization. Nothing here is real." }, "Demo data") : null,
          bell,
          iconButton("appearance", "Appearance", { onclick: () => openAppearance(meta) }),
          userMenu(meta))),
      main));
  shell.addEventListener("click", (event) => {
    if (event.target === shell) shell.removeAttribute("data-nav"); // the dimmed area beside the open menu
  });
  root.replaceChildren(shell);
  return { main, redrawBrand: (next) => brandLink.replaceChildren(...brand(next)) };
}
