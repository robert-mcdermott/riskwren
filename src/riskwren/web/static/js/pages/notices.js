// Notices: what has been assigned to you or changed for you, newest first.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural, relative } from "../core/format.js";
import { navigate } from "../core/router.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const ICONS = { issue: "issue", closure: "issue", action: "check", exception: "exception", test: "assessment",
  reminder: "bell", overdue: "alert", escalated: "alert", campaign: "bell", attestation: "control", indicator: "chart" };

/** Tell the top bar how many are left unread. */
function announce(unread) {
  document.dispatchEvent(new CustomEvent("notices", { detail: { unread } }));
}

export function noticeList(main) {
  return show(main, {
    title: "Notices",
    load: async () => get("/api/v1/notices", null, { fresh: true }),
    view: (page, reload) => {
      const rows = page.data;
      const unread = page.meta.unread;
      announce(unread);
      const open = async (notice) => {
        if (!notice.read) announce((await post("/api/v1/notices/read", { ids: [notice.id] })).data.unread);
        navigate(notice.href);
      };
      const all = unread ? button("Mark all as read", { onclick: async () => {
        await post("/api/v1/notices/read", {});
        reload();
      } }) : null;
      return h("div", { class: "stack-lg" },
        pageHeader({ title: "Notices", lede: "What has been assigned to you or changed for you. What you still owe is on Home.", actions: all }),
        card({ title: unread ? `${unread} unread` : plural(rows.length, "notice"), flush: rows.length > 0 },
          rows.length ? h("ul", { class: "owed" }, rows.map((notice) => h("li", {}, h("a", { class: "owed-item", href: notice.href, "data-unread": String(!notice.read), onclick: (event) => {
            event.preventDefault();
            open(notice);
          } },
          h("span", { class: "owed-icon", "data-kind": notice.kind }, icon(ICONS[notice.kind] ?? "dot")),
          h("span", { class: "grow" }, h("span", { class: notice.read ? "" : "cell-main" }, notice.text), notice.read ? null : h("span", { class: "sr-only" }, " (unread)")),
          h("span", { class: "muted nowrap" }, relative(notice.created_at))))))
            : emptyState({ iconName: "bell", title: "Nothing yet", text: "When something is assigned to you, or something of yours is decided, sent back, or closed, it is listed here." })));
    },
  });
}
