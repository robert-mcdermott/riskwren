// Frameworks: what the organization is held to. The list, and one framework's tree of
// requirements with search, baselines, and each requirement in full.

import { del, get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural } from "../core/format.js";
import { navigate, query } from "../core/router.js";
import { can } from "../core/session.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { statePill } from "../components/control.js";
import { coveragePill, mapCrosswalk } from "../components/crosswalk.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { section } from "../components/record-forms.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { facts } from "./record.js";
import { clearFilters, filterSelect, keepSearchFocus, pager, searchBox } from "./records.js";

const KINDS = [["agreement", "Agreement"], ["internal", "Internal standard"], ["standard", "Standard"], ["regulation", "Regulation"]];
const api = (key, rest = "") => `/api/v1/frameworks/${encodeURIComponent(key)}${rest}`;
const one = (key, code) => api(key, `/requirement?code=${encodeURIComponent(code)}`);

// ---- Forms ----

/** Enter a framework of the organization's own, or change what one says about itself. */
function editFramework(framework = null) {
  openOverlay({
    title: framework ? "Edit the framework" : "Add a framework of your own",
    subtitle: framework ? framework.title : "An agreement's terms, a sponsor's requirements, an internal standard.",
    render: (body, footer, close) => {
      const title = field("Name", { value: framework?.title ?? "", required: true, maxlength: 200,
        hint: framework ? null : "For example: Data use agreement with the cohort trust." });
      const kind = select("Kind", KINDS, { value: framework?.kind ?? "agreement" });
      const version = field("Version or date", { value: framework?.version ?? "", maxlength: 120 });
      const publisher = field("Who it comes from", { value: framework?.publisher ?? "", maxlength: 200, hint: "The sponsor, the other party, or the office that sets it." });
      const summary = field("What it covers", { type: "textarea", rows: 3, value: framework?.summary ?? "" });
      const source = field("Where the document is kept", { type: "url", value: framework?.source_url ?? "", placeholder: "https://" });
      const problem = banner();
      const saveButton = button(framework ? "Save" : "Add", { kind: "btn-primary" });
      const fields = { title, kind, version, publisher, summary, source_url: source };
      const save = async () => {
        const values = { title: title.input.value, kind: kind.input.value, version: version.input.value,
          publisher: publisher.input.value, summary: summary.input.value, source_url: source.input.value };
        const done = await submit({ button: saveButton, fields, banner: problem,
          run: () => (framework ? patch(api(framework.key), values) : post("/api/v1/frameworks", values)) });
        if (!done) return;
        close();
        toast(framework ? "Saved." : "Added. Now add its requirements.");
        navigate(`/frameworks/${done.data.key}`, { replace: Boolean(framework) });
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem,
      section("What it is", title.node, h("div", { class: "grid-2" }, kind.node, version.node)),
      section("Where it comes from", publisher.node, source.node, summary.node),
      framework ? null : h("p", { class: "hint subtle" }, "Its requirements are added next, one at a time or pasted in.")));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Add a requirement to a framework of the organization's own, or change one. */
function editRequirement(framework, reload, { requirement = null, parent = null } = {}) {
  openOverlay({
    title: requirement ? `Edit ${requirement.code}` : "Add a requirement",
    subtitle: parent ? `Under ${parent}` : framework.title,
    render: (body, footer, close) => {
      const code = field("Code", { value: requirement?.code ?? "", required: true, maxlength: 120,
        hint: "A short, stable reference, such as 4.2 or DUA-7. It is how controls and evidence stay attached." });
      const title = field("Title", { value: requirement?.title ?? "", maxlength: 300 });
      const text = field("What is required", { type: "textarea", rows: 6, value: requirement?.text ?? "" });
      const guidance = field("Guidance", { type: "textarea", rows: 3, value: requirement?.guidance ?? "", hint: "Optional. How it is read here, or what the other party has said about it." });
      const heading = checkbox("This is a heading", { checked: requirement ? !requirement.is_citable : false,
        hint: "It groups the requirements beneath it and is not itself something to meet." });
      const problem = banner();
      const saveButton = button(requirement ? "Save" : "Add", { kind: "btn-primary" });
      const save = async () => {
        const values = { code: code.input.value, title: title.input.value, text: text.input.value,
          guidance: guidance.input.value, is_citable: !heading.input.checked, ...(parent && !requirement ? { parent } : {}) };
        const done = await submit({ button: saveButton, fields: { code, title, text, guidance }, banner: problem,
          run: () => (requirement ? patch(one(framework.key, requirement.code), values) : post(api(framework.key, "/requirements"), values)) });
        if (!done) return;
        close();
        toast(requirement ? "Saved." : `${done.data.code} was added.`);
        reload();
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem, section("The requirement", code.node, title.node, text.node, guidance.node, heading.node)));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Add many requirements from pasted lines: checked first, added only if every line can be. */
function pasteRequirements(framework, reload) {
  openOverlay({
    title: "Paste requirements",
    subtitle: framework.title,
    render: (body, footer, close) => {
      const text = field("One requirement to a line", { type: "textarea", rows: 12, class: "textarea mono",
        placeholder: "4.1 Data are stored only on systems the institute manages.\n4.2 Access is limited to named study staff.",
        hint: "A code, a space, then what it requires. A line that starts with a space continues the one above." });
      const report = h("div", { class: "stack-sm", "aria-live": "polite" });
      const check = button("Check", { kind: "btn-primary" });
      const load = button("Add them", { kind: "btn-primary", hidden: true });
      const run = async (dryRun) => {
        const active = dryRun ? check : load;
        active.disabled = true;
        try {
          const done = (await post(api(framework.key, `/requirements/paste?dry_run=${dryRun}`), { text: text.input.value })).data;
          if (done.applied) {
            close();
            toast(`${plural(done.would_add, "requirement")} added.`);
            reload();
            return;
          }
          load.hidden = done.problems.length > 0;
          report.replaceChildren(done.problems.length
            ? alert("danger", h("div", {}, h("strong", {}, "Nothing would be added. "), "Put these right and check again:",
              h("ul", {}, done.problems.slice(0, 12).map((p) => h("li", {}, p.row ? `Line ${p.row}: ${p.message}` : p.message)))))
            : alert("ok", `${plural(done.would_add, "requirement")} would be added, starting with ${done.sample.join(", ")}.`));
        } catch (error) {
          report.replaceChildren(alert("danger", error.detail || "That did not work."));
        } finally {
          active.disabled = false;
        }
      };
      text.input.addEventListener("input", () => {
        load.hidden = true;
      });
      check.addEventListener("click", () => run(true));
      load.addEventListener("click", () => run(false));
      body.append(h("div", { class: "stack-lg" }, text.node, report));
      footer.replaceChildren(h("div", { class: "row" }, check, load, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

// ---- One requirement, in full ----

/** Say in the address which requirement is open, without drawing the page again. */
function remember(code) {
  const params = query();
  if (code) params.set("r", code);
  else params.delete("r");
  const search = params.toString();
  history.replaceState({}, "", window.location.pathname + (search ? `?${search}` : ""));
}

function openRequirement(framework, code, reload) {
  openOverlay({
    title: code,
    subtitle: framework.title,
    onClose: () => remember(null),
    render: async (body, footer, close) => {
      let item;
      try {
        item = (await get(one(framework.key, code), undefined, { fresh: true })).data;
      } catch (error) {
        body.append(alert("danger", error.detail || "That requirement could not be shown."));
        return;
      }
      const trail = item.trail.map((step) => [step.code, step.title].filter(Boolean).join(" ")).join(" › ");
      body.append(h("div", { class: "stack-lg" },
        h("div", { class: "stack-sm" },
          trail ? h("div", { class: "subtle" }, trail) : null,
          item.title ? h("h3", {}, item.title) : null,
          h("div", { class: "row-sm wrap" },
            item.is_citable ? null : pill("Heading"),
            item.baselines.map((baseline) => pill(baseline.title, "info")))),
        item.text ? h("div", { class: "prose" }, item.text) : h("p", { class: "subtle" }, "This entry has no text of its own."),
        item.guidance ? h("details", { class: "disclosure" }, h("summary", {}, "Guidance from the source"), h("div", { class: "prose muted" }, item.guidance)) : null,
        item.is_citable ? h("div", { class: "stack-sm" },
          h("div", { class: "row" }, h("h3", { class: "grow" }, item.controls.length ? `Controls (${item.controls.length})` : "Controls"),
            can("steward") ? button("Map a control", { kind: "btn-sm", iconName: "link",
              onclick: () => mapCrosswalk({ framework, requirement: item, onDone: () => openRequirement(framework, item.code, reload) }) }) : null),
          item.controls.length ? h("ul", { class: "requirement-list stack-sm" }, item.controls.map((mapping) => h("li", { class: "mapped-control" },
            h("div", { class: "grow" }, h("a", { class: "cell-main", href: `/controls/${mapping.control.ref}?tab=requirements` }, mapping.control.name),
              h("div", { class: "cell-sub" }, [mapping.control.ref, mapping.note].filter(Boolean).join(" · "))),
            statePill(mapping.control.state), coveragePill(mapping.coverage))))
            : h("p", { class: "subtle" }, item.hidden ? "None that you have access to." : "No control is mapped to this requirement yet."),
          item.hidden && item.controls.length ? h("p", { class: "subtle" }, `And ${item.hidden} more that you do not have access to.`) : null) : null,
        item.children_list.length ? h("div", { class: "stack-sm" }, h("h3", {}, `Beneath it (${item.children_list.length})`),
          h("ul", { class: "requirement-list" }, item.children_list.map((child) => h("li", {},
            h("button", { type: "button", class: "requirement-row", onclick: () => openRequirement(framework, child.code, reload) },
              h("span", { class: "requirement-code" }, child.code), h("span", { class: "grow" }, child.title || child.excerpt || "")))))) : null));
      if (framework.can.edit) {
        footer.replaceChildren(h("div", { class: "row wrap" },
          button("Edit", { iconName: "edit", onclick: () => editRequirement(framework, reload, { requirement: item }) }),
          button("Add one beneath it", { iconName: "plus", onclick: () => editRequirement(framework, reload, { parent: item.code }) }),
          button("Remove", { kind: "btn-ghost", onclick: () => confirmAction({
            title: `Remove ${item.code}?`, text: "It is taken out of the framework. The change is kept in the history.",
            confirmLabel: "Remove", danger: true,
            run: async () => {
              try {
                await del(one(framework.key, item.code));
                toast(`${item.code} was removed.`);
                reload();
              } catch (error) {
                toast(error.detail || "That could not be removed.");
              }
            } }) })));
        footer.hidden = false;
      }
      void close;
    },
  });
  remember(code);
}

// ---- The tree ----

function requirementRow(framework, item, { nested, reload }) {
  const open = () => openRequirement(framework, item.code, reload);
  const label = h("button", { type: "button", class: "requirement-row", onclick: open },
    h("span", { class: "requirement-code" }, item.code),
    h("span", { class: "grow" },
      item.title ? h("span", { class: item.is_citable ? "" : "cell-main" }, item.title) : null,
      !item.title && item.excerpt ? h("span", {}, item.excerpt) : null,
      item.title && item.excerpt && !nested ? h("span", { class: "cell-sub" }, item.excerpt) : null));
  const mapped = item.controls ? h("span", { class: "mapped-count", title: `${item.controls} mapped` }, icon("control", "icon icon-sm"), String(item.controls)) : null;
  if (!nested || !item.children) return h("li", {}, h("div", { class: "requirement-line" }, h("span", { class: "requirement-toggle" }), label, mapped));
  const beneath = h("ul", { class: "requirement-list", hidden: true });
  let loaded = false;
  const toggle = h("button", { type: "button", class: "requirement-toggle", "aria-expanded": "false",
    "aria-label": `Show what is beneath ${item.code}`, onclick: async () => {
      const opening = beneath.hidden;
      if (opening && !loaded) {
        toggle.disabled = true;
        try {
          const rows = (await get(api(framework.key, "/requirements"), { parent: item.code, limit: 200 })).data;
          beneath.replaceChildren(...rows.map((row) => requirementRow(framework, row, { nested: true, reload })));
          loaded = true;
        } catch (error) {
          toast(error.detail || "That could not be loaded.");
          return;
        } finally {
          toggle.disabled = false;
        }
      }
      beneath.hidden = !opening;
      toggle.setAttribute("aria-expanded", String(opening));
    } }, icon("chevron-right", "icon icon-sm"));
  return h("li", {}, h("div", { class: "requirement-line" }, toggle, label, mapped,
    h("span", { class: "subtle numeric" }, String(item.children))), beneath);
}

export function frameworkPage(main, params) {
  const key = params.key;
  return show(main, {
    title: "Framework",
    load: async () => {
      const asked = query();
      const filter = { q: asked.get("q") ?? undefined, baseline: asked.get("baseline") ?? undefined,
        mapped: asked.get("mapped") ?? undefined, cursor: asked.get("cursor") ?? undefined };
      const flat = Boolean(filter.q || filter.baseline || filter.mapped);
      const [framework, page, coverage] = await Promise.all([
        get(api(key), undefined, { fresh: true }),
        get(api(key, "/requirements"), { ...filter, limit: flat ? 50 : 200 }, { fresh: true }),
        get(api(key, "/coverage"), undefined, { fresh: true })]);
      return { framework: framework.data, page, flat, coverage: coverage.data };
    },
    view: ({ framework, page, flat, coverage }, reload) => {
      document.title = document.title.replace(/^Framework/, framework.title);
      const rows = page.data;
      const search = searchBox("Search codes, titles, and text");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        framework.baselines.length ? filterSelect("baseline", [["", "The whole framework"], ...framework.baselines.map((b) => [b.key, `${b.title} (${b.count})`])], "Baseline") : null,
        filterSelect("mapped", [["", "With or without a control"], ["true", "With a control"], ["false", "With no control"]], "Controls"));
      const list = rows.length
        ? h("ul", { class: "requirement-list requirement-tree" }, rows.map((row) => requirementRow(framework, row, { nested: !flat, reload })))
        : emptyState(flat
          ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or the whole framework.", action: button("Clear", { onclick: clearFilters }) }
          : { iconName: "framework", title: "No requirements yet", text: "Add them one at a time, or paste a list.",
            action: framework.can.edit ? button("Add a requirement", { kind: "btn-primary", onclick: () => editRequirement(framework, reload) }) : null });
      const actions = [
        framework.can.edit ? button("Add a requirement", { kind: "btn-primary", iconName: "plus", onclick: () => editRequirement(framework, reload) }) : null,
        framework.can.edit ? button("Paste", { iconName: "upload", onclick: () => pasteRequirements(framework, reload) }) : null,
        framework.can.edit ? button("Edit", { iconName: "edit", onclick: () => editFramework(framework) }) : null,
        framework.can.retire ? button(framework.status === "active" ? "Retire" : "Restore", { kind: "btn-ghost", onclick: () => confirmAction({
          title: framework.status === "active" ? `Retire ${framework.title}?` : `Restore ${framework.title}?`,
          text: framework.status === "active" ? "It is kept, with everything attached to it, and is offered to nothing new." : "It is offered again wherever frameworks are chosen.",
          confirmLabel: framework.status === "active" ? "Retire" : "Restore",
          run: async () => {
            await patch(api(framework.key), { status: framework.status === "active" ? "retired" : "active" });
            toast(framework.status === "active" ? "Retired." : "Restored.");
            reload();
          } }) }) : null,
      ].filter(Boolean);
      queueMicrotask(() => {
        for (const fill of document.querySelectorAll(".coverage-fill")) fill.style.setProperty("width", `${Math.round(Number(fill.dataset.share) * 100)}%`);
      });
      const wanted = query().get("r");
      if (wanted) queueMicrotask(() => openRequirement(framework, wanted, reload));
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: "/frameworks" }, icon("chevron-left", "icon icon-sm"), "Frameworks"),
        pageHeader({ eyebrow: [framework.kind_label, framework.version].filter(Boolean).join(" · "), title: framework.title,
          lede: framework.summary, actions: actions.length ? actions : null }),
        framework.status === "retired" ? alert("info", "This framework is retired. It is kept, and is offered to nothing new.") : null,
        h("div", { class: "split" },
          h("div", { class: "stack" }, bar,
            card({ title: flat ? plural(page.meta.total, "match", "matches") : "Requirements", flush: true, footer: flat ? pager(page.meta, rows.length) : null }, list)),
          h("div", { class: "stack-lg" },
            card({ title: "Coverage" },
              h("div", { class: "coverage" },
                h("div", { class: "coverage-bar", role: "img", "aria-label": `${coverage.mapped} of ${coverage.citable} requirements have a control` },
                  h("span", { class: "coverage-fill", "data-share": String(coverage.citable ? coverage.mapped / coverage.citable : 0) })),
                h("p", {}, h("strong", {}, `${coverage.mapped} of ${coverage.citable}`), " requirements have a control mapped to them."),
                coverage.unmapped ? h("a", { href: `/frameworks/${framework.key}?mapped=false` }, `See the ${coverage.unmapped} with none`) : h("span", { class: "subtle" }, "Every requirement has at least one."),
                h("p", { class: "subtle" }, "Counted from the controls you may see. Whether they work is another question, answered by testing them."))),
            card({ title: "About" }, facts([
              ["Requirements", `${framework.citable_count} to meet, in ${plural(framework.requirement_count, "entry", "entries")}`],
              [framework.origin === "local" ? "From" : "Publisher", framework.publisher],
              ["Version", framework.version],
              ["License", framework.license],
              ["Its text", framework.text_policy_label],
              ["Attribution", framework.attribution],
              ["Source", framework.source_url ? h("a", { href: framework.source_url, target: "_blank", rel: "noopener" }, new URL(framework.source_url).hostname) : null],
              ["Built from", framework.built_from],
              ["Pack", framework.pack_version],
            ])),
            framework.baselines.length ? card({ title: "Baselines" },
              h("p", { class: "subtle" }, "A published selection from the framework, and the usual starting point for a scope."),
              h("ul", { class: "requirement-list stack-sm" }, framework.baselines.map((b) => h("li", { class: "row" },
                h("a", { class: "grow", href: `/frameworks/${framework.key}?baseline=${b.key}` }, b.title), h("span", { class: "muted numeric" }, String(b.count)))))) : null)));
    },
  });
}

// ---- The list ----

export function frameworkList(main) {
  return show(main, {
    title: "Frameworks",
    load: async () => (await get("/api/v1/frameworks", { retired: true }, { fresh: true })).data,
    view: (rows) => {
      const mayAdd = can("configure");
      const add = mayAdd ? button("Add a framework", { kind: "btn-primary", iconName: "plus", onclick: () => editFramework() }) : null;
      const table = h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Framework"), h("th", { scope: "col" }, "Kind"), h("th", { scope: "col" }, "From"),
          h("th", { scope: "col", class: "numeric" }, "Requirements"), h("th", { scope: "col" }, "Baselines"))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/frameworks/${row.key}` }, row.title), row.status === "retired" ? [" ", pill("Retired")] : null,
            h("div", { class: "cell-sub" }, row.version ?? "")),
          h("td", {}, row.kind_label, row.origin === "local" ? h("div", { class: "cell-sub" }, "Entered here") : null),
          h("td", { class: "muted" }, row.publisher ?? ""),
          h("td", { class: "numeric" }, String(row.citable_count)),
          h("td", { class: "muted" }, row.baselines.map((b) => b.title.replace(/ baseline$/, "")).join(", ")))))));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Compliance", title: "Frameworks",
          lede: "What the organization is held to: public standards and regulations, and the terms of its own agreements.", actions: add }),
        rows.length ? card({ title: plural(rows.length, "framework"), flush: true }, table)
          : card({}, emptyState({ iconName: "framework", title: "No frameworks yet",
            text: "The built-in ones are loaded with `riskwren frameworks load --builtin`. Your own are entered here.", action: add })));
    },
  });
}
