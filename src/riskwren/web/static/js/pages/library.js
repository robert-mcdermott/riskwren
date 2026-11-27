// Policies → Library: the published documents that apply to the reader, to read and, where
// a document asks, to say they have read. Made for a phone as much as a desk.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, dateTime, plural } from "../core/format.js";
import { query, setQuery } from "../core/router.js";
import { documentText, KINDS } from "../components/document.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { keepSearchFocus, searchBox } from "./records.js";

function standing(row) {
  if (!row.acknowledge) return null;
  return row.acknowledged ? pill(`Acknowledged ${date(row.acknowledged_at)}`, "ok") : pill("To acknowledge", "warn");
}

export function libraryList(main) {
  const everything = query().get("all") === "true";
  const words = query().get("q") ?? "";
  return show(main, {
    title: "Policy library",
    load: async () => (await get("/api/v1/library", { q: words || undefined, all: everything || undefined }, { fresh: true })).data,
    view: (rows) => {
      const search = searchBox("Search the library");
      keepSearchFocus(search);
      const owed = rows.filter((row) => row.acknowledge && !row.acknowledged).length;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Policies", title: "Policy library",
          lede: everything ? "Every published policy, standard, procedure, and guideline you may read." : "The policies, standards, procedures, and guidelines that apply to you, as they are in force today." }),
        owed && !words ? alert("warn", h("div", {}, h("strong", {}, `${plural(owed, "document")} to read and acknowledge. `), "They are at the top.")) : null,
        h("div", { class: "filters" }, h("div", { class: "filter-search wide" }, search),
          h("div", { class: "segmented", role: "group", "aria-label": "Which documents" },
            h("button", { type: "button", "aria-pressed": String(!everything), onclick: () => setQuery({ all: null }) }, "What applies to me"),
            h("button", { type: "button", "aria-pressed": String(everything), onclick: () => setQuery({ all: "true" }) }, "Everything published"))),
        rows.length
          ? card({ flush: true }, h("ul", { class: "plain-list rows library" }, rows.map((row) => h("li", {},
            h("div", { class: "row wrap" },
              h("a", { class: "cell-main grow", href: `/library/${row.ref}` }, row.name), standing(row)),
            h("div", { class: "cell-sub" }, [KINDS[row.kind], row.ref, `version ${row.number}`, `in force since ${date(row.published_at)}`].join(" · ")),
            row.summary ? h("p", { class: "muted" }, row.summary) : null))))
          : card({}, emptyState({ iconName: "document", title: words ? `Nothing matches “${words}”` : "Nothing here yet",
            text: words ? "Every word has to be in the title, the summary, or the text." : "When a document that applies to you is published, it appears here." })));
    },
  });
}

export function libraryReading(main, params) {
  return show(main, {
    title: params.ref,
    load: async () => (await get(`/api/v1/library/${params.ref}`, null, { fresh: true })).data,
    view: (doc, reload) => {
      document.title = `${doc.name} · ${doc.ref}`;
      const version = doc.version;
      const acknowledge = async (event) => {
        event.currentTarget.disabled = true;
        try {
          await post(`/api/v1/library/${doc.ref}/acknowledge`);
          toast("Thank you. That is recorded.");
          reload();
        } catch (error) {
          toast(error.detail ?? "That did not work.");
          event.currentTarget.disabled = false;
        }
      };
      const owed = doc.acknowledge && !doc.acknowledged;
      const ask = owed ? card({ title: "Read it, then say you have" }, h("div", { class: "stack" },
        h("p", {}, doc.acknowledged_version ? `You acknowledged version ${doc.acknowledged_version}. Version ${doc.required.number} changed enough that everyone is asked again.` : "This document asks everyone it applies to to read it and say they have."),
        h("div", {}, button("I have read it and understand it", { kind: "btn-primary", onclick: acknowledge }))))
        : null;
      const content = version.form === "link"
        ? card({}, h("div", { class: "stack-sm" }, h("p", {}, "It is kept elsewhere."),
          h("p", {}, h("a", { class: "btn", href: version.url, target: "_blank", rel: "noopener noreferrer" }, icon("external", "icon icon-sm"), "Open it where it is kept"))))
        : version.form === "file"
          ? card({}, h("div", { class: "row wrap" }, icon("file"), h("span", { class: "grow cell-main" }, version.file?.name ?? "The file"),
            h("a", { class: "btn", href: `/api/v1/documents/${doc.ref}/versions/${version.id}/file`, download: "" }, icon("download", "icon icon-sm"), "Download")))
          : card({}, h("article", { class: "doc-body", "aria-label": doc.name }, documentText(version.body)));
      return h("div", { class: "stack-lg reading" },
        h("a", { class: "back-link", href: "/library" }, icon("chevron-left", "icon icon-sm"), "Policy library"),
        pageHeader({ eyebrow: `${KINDS[doc.kind]} · ${doc.ref}`, title: doc.name, lede: doc.summary,
          actions: doc.can_manage ? h("a", { class: "btn", href: `/documents/${doc.ref}` }, "Manage it") : null }),
        h("div", { class: "doc-meta" }, `Version ${version.number}, in force since ${date(version.published_at)}`,
          version.approved_by.length ? `; approved by ${version.approved_by.join(", ")}` : "",
          doc.next_review_on ? `; next reviewed by ${date(doc.next_review_on)}` : ""),
        doc.acknowledge && doc.acknowledged ? alert("info", `You acknowledged version ${doc.acknowledged_version} on ${dateTime(doc.acknowledged_at)}.`) : null,
        owed ? alert("warn", "Please read this document and say you have. The button is at the end.") : null,
        version.change_note && version.number > 1 ? card({ title: `What changed in version ${version.number}` }, h("p", {}, version.change_note)) : null,
        content,
        doc.parent ? h("p", {}, "It puts into practice ", h("a", { href: `/library/${doc.parent.ref}` }, doc.parent.name), ".") : null,
        doc.children.length ? card({ title: "What puts it into practice" }, h("ul", { class: "plain-list stack-sm" }, doc.children.map((child) => h("li", {},
          h("a", { href: `/library/${child.ref}` }, child.name), h("span", { class: "cell-sub" }, ` ${KINDS[child.kind]}`))))) : null,
        ask);
    },
  });
}
