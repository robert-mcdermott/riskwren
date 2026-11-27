// Framework updates: loading a framework, what changed from one version to the next, moving
// a scope across, a new version of one's own, and the crosswalks a publisher's mapping suggests.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural } from "../core/format.js";
import { navigate, query, setQuery } from "../core/router.js";
import { segments } from "../components/charts.js";
import { comparison } from "../components/document.js";
import { banner, field, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const api = (key, rest = "") => `/api/v1/frameworks/${encodeURIComponent(key)}${rest}`;
const HOW = { moved_to: "Moved to", incorporated_into: "Incorporated into" };

/** Load a framework that ships, or a pack from a file. */
export function loadFramework() {
  openOverlay({ title: "Load a framework", subtitle: "Beside those already here. Nothing that uses another changes.",
    render: async (body, footer, close) => {
      const shipped = (await get("/api/v1/framework-packs", undefined, { fresh: true })).data;
      const problem = banner();
      const loadOne = async (pack, done) => {
        const made = await submit({ button: done, banner: problem, run: () => post("/api/v1/framework-packs", pack) });
        if (!made) return;
        close();
        toast(`${made.data.title} is loaded.`);
        navigate(`/frameworks/${made.data.key}`);
      };
      const rows = shipped.map((row) => h("li", { class: "row wrap" },
        h("div", { class: "grow" }, h("div", { class: "cell-main" }, row.title), h("div", { class: "cell-sub" }, [row.version, row.summary].filter(Boolean).join(" · "))),
        row.loaded ? pill("Loaded", "ok") : (() => {
          const go = button("Load", { kind: "btn-sm" });
          go.addEventListener("click", () => loadOne({ key: row.key }, go));
          return go;
        })()));
      const file = h("input", { type: "file", class: "input", id: "pack-file", accept: ".json,application/json" });
      const fromFile = button("Load the file", { kind: "btn-sm" });
      fromFile.addEventListener("click", async () => {
        const chosen = file.files?.[0];
        if (!chosen) {
          problem.textContent = "Choose a pack file first.";
          problem.hidden = false;
          return;
        }
        let pack;
        try {
          pack = JSON.parse(await chosen.text());
        } catch {
          problem.textContent = "That file is not a pack: it could not be read as JSON.";
          problem.hidden = false;
          return;
        }
        await loadOne({ pack }, fromFile);
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("div", { class: "stack-sm" }, h("h3", {}, "That ship with RiskWren"), h("ul", { class: "plain-list stack" }, rows)),
        h("div", { class: "stack-sm" }, h("h3", {}, "From a pack file"),
          h("p", { class: "subtle" }, "A publisher's new version before RiskWren ships it, or a framework kept as a pack. A new version names the one it follows, so what changed can be listed."),
          h("div", { class: "field" }, h("label", { for: "pack-file" }, "Pack file"), file), h("div", {}, fromFile))));
      footer.replaceChildren(h("div", { class: "row" }, button("Close", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

/** Start a new version of a framework of the organization's own. */
export function startVersion(framework) {
  openOverlay({ title: "Start a new version", subtitle: `${framework.title}: copied beside it, to be edited. The old version stays as it is for whatever uses it.`,
    render: (body, footer, close) => {
      const title = field("Title", { value: `${framework.title} (new version)`, required: true, maxlength: 200 });
      const version = field("Version", { hint: "Such as “Renewed March 2027”." });
      const problem = banner();
      const go = button("Start it", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const made = await submit({ button: go, fields: { title, version }, banner: problem,
          run: () => post(api(framework.key, "/versions"), { title: title.input.value, version: version.input.value || null }) });
        if (!made) return;
        close();
        toast(`${made.data.title} is started. Change its requirements, then move scopes to it.`);
        navigate(`/frameworks/${made.data.key}`);
      });
      body.append(h("div", { class: "stack" }, problem, title.node, version.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    } });
}

/** Move a scope from one version to a later one. */
export function moveScope({ scope, from, to, onDone }) {
  confirmAction({
    title: `Move ${scope.name} to ${to.title}?`,
    text: `It is held to ${to.title} in place of ${from.title}. Its decisions about requirements, and exceptions to them, go with it where the code is unchanged. Crosswalks and documents mapped to ${from.title} are carried across for everyone. What was withdrawn is left behind, and the history keeps it.`,
    confirmLabel: "Move it",
    run: async () => {
      const done = (await post(`/api/v1/scopes/${scope.ref}/frameworks/${encodeURIComponent(from.key)}/move`, { to: to.key })).data.moved;
      toast(`Moved. ${plural(done.decisions, "decision")} and ${plural(done.exceptions, "exception")} carried, ${plural(done.crosswalks, "crosswalk")} brought across.`);
      onDone?.(done);
    },
  });
}

function changedItem(framework, earlier, row, labels) {
  const holder = h("div", { class: "change-detail", hidden: true });
  const show = button("Show the difference", { kind: "btn-ghost btn-sm", "aria-expanded": "false", onclick: async () => {
    const opening = holder.hidden;
    holder.hidden = !opening;
    show.setAttribute("aria-expanded", String(opening));
    show.textContent = opening ? "Hide the difference" : "Show the difference";
    if (opening && !holder.childElementCount) {
      const found = (await get(api(framework, "/change"), { from: earlier, code: row.code })).data;
      holder.replaceChildren(comparison(found, labels));
    }
  } });
  return h("li", { class: "stack-sm" },
    h("div", { class: "row" }, h("span", { class: "requirement-code" }, row.code), h("span", { class: "grow" }, row.title || row.excerpt || ""), show),
    row.retitled ? h("div", { class: "cell-sub" }, `Was titled “${row.title_before ?? ""}”`) : null,
    holder);
}

const PAGE = 60;

export function frameworkChanges(main, params) {
  const earlier = query().get("from");
  const tab = ["added", "changed", "withdrawn"].includes(query().get("show")) ? query().get("show") : "changed";
  const shown = Number(query().get("more") ?? 1);
  return show(main, {
    title: "What changed",
    load: async () => (await get(api(params.key, "/changes"), { from: earlier }, { fresh: true })).data,
    view: (found, reload) => {
      const { counts, affects } = found;
      const rows = found[tab];
      const visible = rows.slice(0, PAGE * shown);
      const list = visible.length ? h("ul", { class: "plain-list stack change-list" }, visible.map((row) => tab === "changed" ? changedItem(params.key, earlier, row, { before: found.from.version ?? found.from.title, after: found.to.version ?? found.to.title })
        : h("li", { class: "stack-sm" },
          h("div", { class: "row wrap" }, h("span", { class: "requirement-code" }, row.code), h("span", { class: "grow" }, row.title || row.excerpt || "")),
          tab === "withdrawn" ? h("div", { class: "cell-sub" }, row.went.length
            ? row.went.map((went) => `${HOW[went.how]} ${went.code}`).join("; ")
            : "Withdrawn, with nothing named in its place") : null)))
        : emptyState({ iconName: "framework", title: `Nothing ${tab}`, text: "Nothing of this kind differs between the two." });
      const tabs = [["changed", `Changed (${counts.changed})`], ["added", `Added (${counts.added})`], ["withdrawn", `Withdrawn (${counts.withdrawn})`]];
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: `/frameworks/${params.key}` }, icon("chevron-left", "icon icon-sm"), found.to.title),
        pageHeader({ eyebrow: "What changed", title: `From ${found.from.version ?? found.from.title} to ${found.to.version ?? found.to.title}`,
          lede: `${found.from.title} and ${found.to.title}, requirement by requirement, by code. Nothing that uses the earlier version changes until its scope is moved.` }),
        card({ title: `${counts.same + counts.changed + counts.added} requirements in the new version` }, segments([
          { label: "the same", value: counts.same, tone: "ok" }, { label: "changed", value: counts.changed, tone: "warn" },
          { label: "added", value: counts.added, tone: "info" }, { label: "withdrawn", value: counts.withdrawn, tone: "gap" }],
        { label: `${counts.same} the same, ${counts.changed} changed, ${counts.added} added, ${counts.withdrawn} withdrawn` })),
        h("div", { class: "split" },
          card({ flush: true },
            h("div", { class: "tabs pad-x", role: "tablist" }, tabs.map(([key, text]) => h("button", { type: "button", class: "tab", role: "tab", "aria-selected": String(tab === key),
              onclick: () => setQuery({ show: key === "changed" ? null : key, more: null }, { replace: false }) }, text))),
            h("div", { class: "card-pad stack" }, list,
              rows.length > visible.length ? h("div", {}, button(`Show ${Math.min(PAGE, rows.length - visible.length)} more`, { onclick: () => setQuery({ more: String(shown + 1) }) })) : null)),
          h("div", { class: "stack-lg" }, affectsCards(found, reload))));
    },
  });
}

function affectsCards(found, reload) {
  const { affects } = found;
  return [
    card({ title: `Scopes on ${found.from.version ?? found.from.title}` },
      affects.scopes.length ? h("ul", { class: "plain-list stack" }, affects.scopes.map((scope) => h("li", { class: "stack-sm" },
        h("div", { class: "row wrap" }, h("a", { class: "cell-main grow", href: `/scopes/${scope.ref}?tab=requirements&framework=${found.from.key}` }, scope.name),
          scope.can_move ? button(`Move to ${found.to.version ?? found.to.title}`, { kind: "btn-sm", onclick: () => moveScope({ scope, from: found.from, to: found.to, onDone: reload }) }) : null),
        h("div", { class: "cell-sub" }, [scope.ref, scope.baseline, scope.by_agreement ? "imposed by an agreement: name the new version as its terms" : null].filter(Boolean).join(" · ")))))
        : h("p", { class: "muted" }, "No scope is held to it.")),
    card({ title: "Crosswalks" }, h("p", {}, `${plural(affects.crosswalks.carried, "crosswalk")} would be carried across when a scope moves`,
      affects.crosswalks.left ? `; ${affects.crosswalks.left} are to requirements withdrawn with nothing in their place, and stay with the old version.` : "."),
    affects.controls.length ? h("div", { class: "stack-sm" }, h("div", { class: "label" }, "Controls mapped to what changed or was withdrawn"),
      h("ul", { class: "plain-list stack-sm" }, affects.controls.slice(0, 20).map((control) => h("li", {}, recordChip(control), h("span", { class: "cell-sub" }, ` ${control.codes.join(", ")}`)))),
      affects.controls.length > 20 ? h("p", { class: "subtle" }, `And ${affects.controls.length - 20} more.`) : null) : null),
    affects.exceptions.length ? card({ title: "Exceptions to its requirements" }, h("ul", { class: "plain-list stack-sm" }, affects.exceptions.map((item) => h("li", {},
      recordChip(item), h("span", { class: "cell-sub" }, ` ${item.code} · ${item.carries ? "goes with its scope" : "its requirement is withdrawn"}`))))) : null,
    affects.documents.length ? card({ title: "Documents that answer its requirements" }, h("ul", { class: "plain-list stack-sm" }, affects.documents.map((doc) => h("li", {},
      recordChip(doc), h("span", { class: "cell-sub" }, ` ${doc.code}`))))) : null,
  ];
}

export function frameworkSuggestions(main, params) {
  return show(main, {
    title: "Suggested crosswalks",
    load: async () => {
      const [framework, found] = await Promise.all([get(api(params.key), undefined, { fresh: true }), get(api(params.key, "/suggestions"), undefined, { fresh: true })]);
      return { framework: framework.data, found: found.data };
    },
    view: ({ framework, found }, reload) => {
      const act = (path, control, code, said) => async (event) => {
        event.currentTarget.disabled = true;
        await post(api(framework.key, `/suggestions/${path}`), { control, code });
        toast(said);
        reload();
      };
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: `/frameworks/${framework.key}` }, icon("chevron-left", "icon icon-sm"), framework.title),
        pageHeader({ eyebrow: "Suggested crosswalks", title: framework.title,
          lede: found.sources.length ? `From the publisher's mapping between ${framework.title} and ${found.sources.join(" and ")}: a control mapped to one side is suggested for the requirement the publisher relates to it on this side. Nothing is mapped until a person confirms it.` : "No publisher's mapping relates this framework to another." }),
        found.controls.length ? h("div", { class: "stack" }, found.controls.map((group) => card({ title: group.control.name, flush: true, actions: h("a", { class: "btn btn-sm", href: `/controls/${group.control.ref}?tab=requirements` }, "Open the control") },
          h("ul", { class: "plain-list rows" }, group.suggestions.map((each) => h("li", { class: "row wrap" },
            h("div", { class: "grow" }, h("span", { class: "requirement-code" }, each.code), " ", each.title || each.excerpt || "",
              h("div", { class: "cell-sub" }, `Because it is mapped to ${each.because.map((b) => `${b.code} of ${b.framework}`).join(", ")}`)),
            group.can_edit ? h("div", { class: "row-sm" },
              button("Map it", { kind: "btn-sm btn-primary", onclick: act("confirm", group.control.ref, each.code, `${group.control.ref} is mapped to ${each.code}, in part.`) }),
              button("Not this one", { kind: "btn-sm btn-ghost", onclick: act("set-aside", group.control.ref, each.code, "Set aside. It will not be suggested again.") })) : null))))))
          : card({}, emptyState({ iconName: "check", title: "Nothing to suggest", text: "Every crosswalk the publisher's mapping suggests is mapped already, or set aside." })),
        alert("info", icon("info"), h("div", {}, "A suggestion is mapped as answering in part, and is yours once confirmed. Set one aside and it is not suggested again.")));
    },
  });
}
