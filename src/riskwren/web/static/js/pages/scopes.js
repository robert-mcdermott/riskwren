// Scopes: a boundary, what it must meet, and how each control is done inside it. The list,
// and one scope with its requirements (the statement of applicability) and its controls.

import { del, get, patch, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural, relative } from "../core/format.js";
import { units, vocabularies } from "../core/lookups.js";
import { navigate, query, setQuery } from "../core/router.js";
import { can } from "../core/session.js";
import { statusPill as assessmentStatus } from "../components/assessment.js";
import { segments } from "../components/charts.js";
import { statePill } from "../components/control.js";
import { evidenceCard } from "../components/evidence.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { recordChip, TYPES } from "../components/record.js";
import { section } from "../components/form.js";
import { ownUnits } from "../core/session.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill, statusPill } from "../components/ui.js";
import { unitOptions } from "../core/lookups.js";
import { exportButton } from "../components/exchange.js";
import { show } from "./page.js";
import { facts, ownersCard, prose, recordHeader, tabBar, timeline } from "./record.js";
import { clearFilters, filterSelect, isFiltering, keepSearchFocus, mineToggle, ownerCell, pager, searchBox, sortHeader } from "./records.js";

const TABS = [["overview", "Overview"], ["requirements", "Requirements"], ["controls", "Controls"], ["plan", "Plan of action"], ["history", "History"]];
const STANDING = { planned: ["Planned", ""], partly: ["Partly in place", "warn"], in_place: ["In place", "ok"], not_applicable: ["Not applicable here", ""] };
const STATUS_CHOICES = Object.entries(STANDING).map(([key, [text]]) => [key, text]);
// Readiness, weakest first: a word, a tone for the pill, and a tone for the bar.
const STATES = { failing: ["Failing", "danger", "danger"], gap: ["Gap", "danger", "gap"], planned: ["Planned", "warn", "warn"], excepted: ["Excepted", "accent", "excepted"],
  in_place: ["In place", "info", "info"], verified: ["Verified", "ok", "ok"], excluded: ["Not applicable", "", "none"] };
const READY = ["verified", "in_place", "excepted", "planned", "gap", "failing"];
const WEAK = ["failing", "gap", "planned"];
const INHERITED = { inherited: "Inherited", shared: "Shared" };

const standingPill = (key) => pill(STANDING[key]?.[0] ?? key, STANDING[key]?.[1] ?? "");
const statePillOf = (key) => pill(STATES[key][0], STATES[key][1]);

// ---- Forms ----

function editScope({ scope = null, unitIndex, onDone }) {
  openOverlay({
    title: scope ? "Edit the scope" : "Add a scope",
    subtitle: scope ? `${scope.ref} · ${scope.name}` : "A boundary that must meet one or more frameworks.",
    render: (body, footer, close) => {
      const name = field("Name", { value: scope?.name ?? "", required: true, maxlength: 200, hint: scope ? null : "For example: Clinical systems, or The data enclave." });
      const unit = select("Unit", unitOptions(unitIndex.tree, { only: ownUnits(), blank: scope ? null : "Choose…" }), { value: scope?.org_unit_id ?? "", required: true, hint: "The unit that answers for it." });
      const summary = field("What it is for", { type: "textarea", rows: 2, value: scope?.summary ?? "" });
      const boundary = field("Boundary", { type: "textarea", rows: 3, value: scope?.boundary ?? "", hint: "Where it begins and ends, in words. What is inside it is listed once it is saved." });
      const offers = checkbox("Offers its controls to other scopes", { checked: scope?.offers_controls ?? false,
        hint: "For a provider, such as central computing. Other scopes can then inherit its controls instead of describing their own." });
      const restricted = checkbox("Restricted", { checked: scope?.restricted ?? false });
      const status = scope ? select("Status", [["active", "Active"], ["retired", "Retired"]], { value: scope.status }) : null;
      const problem = banner();
      const saveButton = button(scope ? "Save" : "Add", { kind: "btn-primary" });
      const save = async () => {
        const values = { name: name.input.value, org_unit_id: unit.input.value ? Number(unit.input.value) : null, summary: summary.input.value,
          boundary: boundary.input.value, offers_controls: offers.input.checked, restricted: restricted.input.checked, ...(status ? { status: status.input.value } : {}) };
        const done = await submit({ button: saveButton, fields: { name, org_unit_id: unit, summary, boundary, ...(status ? { status } : {}) }, banner: problem,
          run: () => (scope ? patch(`/api/v1/scopes/${scope.ref}`, { version: scope.version, ...values }) : post("/api/v1/scopes", values)) });
        if (!done) return;
        close();
        toast(scope ? "Saved." : `${done.data.ref} was added.`);
        if (onDone) onDone(done.data);
        else navigate(`/scopes/${done.data.ref}`);
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem, section("What it is", name.node, unit.node, summary.node, boundary.node), section("How it is used", offers.node, restricted.node, status?.node ?? null)));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** What is inside the boundary: units, and records from the inventory. */
function editMembers(scope, unitIndex, reload) {
  const chosen = scope.members.records.map((record) => ({ ...record }));
  const chosenUnits = new Set(scope.members.units.map((unit) => unit.id));
  openOverlay({
    title: "What is inside the boundary",
    subtitle: `${scope.ref} · ${scope.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const list = h("div", { class: "stack-sm" });
      const search = h("input", { class: "input", type: "search", placeholder: "Find a process, system, information asset, or third party", "aria-label": "Find a record" });
      const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Records found" });
      const draw = () => {
        list.replaceChildren(...(chosen.length ? chosen.map((record, index) => h("div", { class: "owner-row" },
          h("div", { class: "grow" }, recordChip(record, { link: false })),
          button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${record.name}`, onclick: () => {
            chosen.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "Nothing from the inventory yet.")]));
      };
      let latest = 0;
      let timer = null;
      const look = async () => {
        const mine = ++latest;
        const words = search.value.trim();
        if (words.length < 2) {
          results.replaceChildren();
          return;
        }
        const pages = await Promise.all(["process", "system", "information", "third_party"].map((type) =>
          get(`/api/v1/${TYPES[type].path}`, { q: words, sort: "name", limit: 5, status: "active" }, { fresh: true })));
        if (mine !== latest) return;
        const offered = pages.flatMap((page) => page.data).filter((r) => !chosen.some((c) => c.ref === r.ref));
        results.replaceChildren(...(offered.length ? offered.map((record) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
          chosen.push(record);
          search.value = "";
          results.replaceChildren();
          draw();
        } }, icon(TYPES[record.type].iconName), h("span", {}, h("span", { class: "cell-main" }, record.name), h("span", { class: "cell-sub" }, ` ${record.ref}`))))
          : [h("div", { class: "subtle pick-none" }, "Nothing matches. Add it to the inventory first.")]));
      };
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(look, 180);
      });
      const unitBoxes = unitOptions(unitIndex.tree).map(([id, text]) => {
        const box = checkbox(text.trim(), { checked: chosenUnits.has(id) });
        box.input.addEventListener("change", () => (box.input.checked ? chosenUnits.add(id) : chosenUnits.delete(id)));
        box.node.style.setProperty("padding-left", `${(text.length - text.trimStart().length) * 12}px`);
        return box.node;
      });
      draw();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/scopes/${scope.ref}/members`, { records: chosen.map((record) => record.ref), units: [...chosenUnits] }) });
        if (done) {
          close();
          toast("Saved.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        section("From the inventory", list, h("div", { class: "field" }, h("div", { class: "label" }, "Add"), search, results),
          scope.members.hidden ? h("p", { class: "subtle" }, `It also holds ${scope.members.hidden} that you do not have access to. They stay as they are.`) : null),
        section("Units", h("div", { class: "unit-checks stack-sm" }, unitBoxes))));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Hold the scope to a framework, starting from a baseline if it has one. */
function holdTo(scope, reload) {
  openOverlay({
    title: "Hold it to a framework",
    subtitle: `${scope.ref} · ${scope.name}`,
    render: async (body, footer, close) => {
      const all = (await get("/api/v1/frameworks")).data.filter((item) => !scope.held_to.some((held) => held.key === item.key));
      if (!all.length) {
        body.append(h("p", { class: "muted" }, "This scope is already held to every framework on record."));
        return;
      }
      const framework = select("Framework", all.map((item) => [item.key, item.title]));
      const baselineHolder = h("div", {});
      let baseline = null;
      const drawBaseline = () => {
        const chosen = all.find((item) => item.key === framework.input.value);
        baseline = chosen.baselines.length ? select("Start from", [["", `Every requirement (${chosen.citable_count})`], ...chosen.baselines.map((b) => [b.key, `${b.title} (${b.count})`])],
          { hint: "A baseline is the publisher's own selection. Requirements can be added to it or left out afterwards, with a reason." }) : null;
        baselineHolder.replaceChildren(baseline ? baseline.node : h("p", { class: "subtle" }, `Every one of its ${chosen.citable_count} requirements applies until you say otherwise.`));
      };
      framework.input.addEventListener("change", drawBaseline);
      drawBaseline();
      const problem = banner();
      const save = button("Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { framework, ...(baseline ? { baseline } : {}) }, banner: problem,
          run: () => put(`/api/v1/scopes/${scope.ref}/frameworks`, { framework: framework.input.value, baseline: baseline?.input.value || null }) });
        if (done) {
          close();
          toast("Added.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, framework.node, baselineHolder));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Leave a requirement out of the scope, with the reason, or bring it back. */
function decide(scope, framework, row, reload) {
  const leavingOut = row.applicable;
  openOverlay({
    kind: "dialog",
    title: leavingOut ? `Leave ${row.code} out?` : `Bring ${row.code} back?`,
    subtitle: row.title,
    render: (body, footer, close) => {
      const reason = field(leavingOut ? "Why it does not apply here" : "Note", { type: "textarea", rows: 3, required: leavingOut,
        hint: leavingOut ? "It is given in the statement of applicability, with your name and the date." : "Optional." });
      const problem = banner();
      const save = button(leavingOut ? "Leave it out" : "Bring it back", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { reason }, banner: problem,
          run: () => put(`/api/v1/scopes/${scope.ref}/requirements`, { framework, code: row.code, applicable: !leavingOut, reason: reason.input.value || null }) });
        if (done) {
          close();
          toast(leavingOut ? `${row.code} is left out.` : `${row.code} applies again.`);
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, reason.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Say where a control stands in this scope, who answers for it, and how it is done here. */
function editImplementation(scope, item, reload) {
  const whole = item.inheritance === "inherited";
  openOverlay({
    title: item.id ? "How it is done here" : "Use this control",
    subtitle: `${item.control.ref} · ${item.control.name}`,
    render: (body, footer, close) => {
      const status = whole ? null : select("Where it stands", STATUS_CHOICES, { value: item.status ?? "planned" });
      const who = field("Who answers for it here", { value: item.responsibility ?? "", maxlength: 200, hint: "A role or a team." });
      const how = field(item.inheritance === "shared" ? "What this scope does as its part" : "How it is done here", { type: "textarea", rows: 4, value: item.statement ?? "" });
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { ...(status ? { status } : {}), responsibility: who, statement: how }, banner: problem,
          run: () => put(`/api/v1/scopes/${scope.ref}/controls`, { control: item.control.ref, status: status?.input.value ?? null, responsibility: who.input.value || null, statement: how.input.value || null }) });
        if (done) {
          close();
          toast("Saved.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        whole ? alert("info", `Inherited whole from ${item.provider.scope.name}: it stands where theirs does.`) : status.node, who.node, how.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Controls that answer this scope's requirements and are not used in it yet. */
function addControls(scope, reload) {
  openOverlay({
    title: "Add controls",
    subtitle: "Controls you may see that answer this scope's requirements.",
    render: async (body, footer, close) => {
      const offered = (await get(`/api/v1/scopes/${scope.ref}/controls/candidates`, undefined, { fresh: true })).data;
      if (!offered.length) {
        body.append(emptyState({ iconName: "control", title: "Nothing to add",
          text: "No control that you may see is mapped to a requirement of this scope and not already used in it. Map controls to requirements from the control, or inherit what another scope offers." }));
        return;
      }
      const rows = offered.map((control) => {
        const box = checkbox(control.name, { hint: `${control.ref} · answers ${plural(control.answers, "requirement")} here` });
        const status = select("Where it stands", STATUS_CHOICES, { value: "in_place", "aria-label": `Where ${control.name} stands` });
        return { control, box, status, node: h("div", { class: "add-control" }, h("div", { class: "grow" }, box.node), statePill(control.state), status.input) };
      });
      const problem = banner();
      const save = button("Add the ones ticked", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const picked = rows.filter((row) => row.box.input.checked);
        if (!picked.length) {
          problem.textContent = "Tick at least one.";
          problem.hidden = false;
          return;
        }
        const done = await submit({ button: save, banner: problem, run: async () => {
          for (const row of picked) await put(`/api/v1/scopes/${scope.ref}/controls`, { control: row.control.ref, status: row.status.input.value });
          return true;
        } });
        if (done) {
          close();
          toast(`${plural(picked.length, "control")} added.`);
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, h("p", { class: "muted" }, "Tick the ones this scope uses, and say where each stands. How each is done here can be written afterwards."), rows.map((row) => row.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Rely on a control another scope offers: whole, or sharing the work. */
function inheritControl(scope, reload) {
  openOverlay({
    title: "Inherit a control",
    subtitle: "What other scopes offer that this one does not use yet.",
    render: async (body, footer, close) => {
      const offered = (await get(`/api/v1/scopes/${scope.ref}/controls/offered`, undefined, { fresh: true })).data;
      if (!offered.length) {
        body.append(emptyState({ iconName: "scope", title: "Nothing is on offer",
          text: "A scope offers its controls when its owner says so, on the scope itself. A provider such as central computing would." }));
        return;
      }
      const which = select("Control", offered.map((item) => [item.id, `${item.control.name} · from ${item.scope.name}`]));
      const how = select("How", [["inherited", "Inherited whole: they do all of it"], ["shared", "Shared: they do part, and this scope does the rest"]]);
      const status = select("Where this scope's part stands", STATUS_CHOICES.filter(([key]) => key !== "not_applicable"), { value: "planned" });
      const part = field("What this scope does as its part", { type: "textarea", rows: 3 });
      const theirs = h("div", { class: "subtle" });
      const own = h("div", { class: "stack", hidden: true }, status.node, part.node);
      const drawTheirs = () => {
        const item = offered.find((entry) => String(entry.id) === which.input.value);
        theirs.replaceChildren(`${item.scope.name} has it ${STANDING[item.status][0].toLowerCase()}`, item.responsibility ? `, answered for by ${item.responsibility}.` : ".", item.statement ? ` ${item.statement}` : "");
      };
      which.input.addEventListener("change", drawTheirs);
      how.input.addEventListener("change", () => {
        own.hidden = how.input.value !== "shared";
      });
      drawTheirs();
      const problem = banner();
      const save = button("Inherit", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const shared = how.input.value === "shared";
        const done = await submit({ button: save, fields: { implementation: which, inheritance: how, status, statement: part }, banner: problem,
          run: () => post(`/api/v1/scopes/${scope.ref}/controls/inherited`, { implementation: Number(which.input.value), inheritance: how.input.value,
            status: shared ? status.input.value : null, statement: shared ? part.input.value : null }) });
        if (done) {
          close();
          toast("Inherited.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, which.node, theirs, how.node, own));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

// ---- Tabs ----

function overview(scope, ctx) {
  const edit = scope.can.edit && scope.status === "active";
  const m = scope.members;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      scope.summary || scope.boundary ? card({ title: "What it is" }, prose(scope.summary),
        scope.boundary ? h("div", {}, h("div", { class: "label" }, "Boundary"), prose(scope.boundary)) : null) : null,
      card({ title: "Held to", actions: edit ? button("Add a framework", { kind: "btn-sm", iconName: "plus", onclick: () => holdTo(scope, ctx.reload) }) : null,
        flush: scope.held_to.length > 0 },
      scope.held_to.length ? h("div", {}, scope.held_to.map((held) => h("div", { class: "list-row" },
        h("div", { class: "grow" }, h("a", { class: "cell-main", href: `/scopes/${scope.ref}?tab=requirements&framework=${held.key}` }, held.title),
          h("div", { class: "cell-sub" }, [held.version, held.baseline ? held.baseline.title : "Every requirement"].filter(Boolean).join(" · ")),
          held.agreement ? h("div", { class: "cell-sub" }, "Because ", h("a", { href: `/agreements/${held.agreement.ref}` }, `${held.agreement.ref} ${held.agreement.name}`), " covers what it holds") : null,
          (held.later ?? []).map((later) => h("div", { class: "cell-sub" }, "A later version is loaded: ",
            h("a", { href: `/frameworks/${later.key}/changes?from=${held.key}` }, `see what changed in ${later.title}, and move to it`)))),
        edit && !held.agreement ? button("Remove", { kind: "btn-sm btn-ghost", "aria-label": `Remove ${held.title}`, onclick: () => confirmAction({
          title: `Take ${held.title} off this scope?`, text: "The decisions made about which of its requirements apply here go with it. The history keeps them.",
          confirmLabel: "Remove", danger: true,
          run: async () => {
            await del(`/api/v1/scopes/${scope.ref}/frameworks/${held.key}`);
            toast("Removed.");
            ctx.reload();
          } }) }) : null)))
        : h("p", { class: "muted" }, "Not held to any framework yet. Add the ones this scope must meet.")),
      card({ title: "Inside the boundary", actions: edit ? button("Edit", { kind: "btn-sm", onclick: () => editMembers(scope, ctx.units, ctx.reload) }) : null },
        m.units.length || m.records.length ? h("div", { class: "stack" },
          m.units.length ? h("div", {}, h("div", { class: "label" }, "Units"), h("p", {}, m.units.map((unit) => unit.name).join(", "))) : null,
          m.records.length ? h("div", { class: "chips" }, m.records.map((record) => recordChip(record))) : null)
          : h("p", { class: "muted" }, "Nothing listed yet: the units, processes, systems, and information this scope covers."),
        m.hidden ? h("p", { class: "subtle" }, `And ${m.hidden} more that you do not have access to.`) : null),
      card({ title: "Assessments", flush: ctx.assessments.length > 0,
        actions: can("assess") && scope.status === "active" ? button("Start an assessment", { kind: "btn-sm", iconName: "plus", onclick: async () => (await import("./assessments.js")).editAssessment({ scope }) }) : null },
      ctx.assessments.length ? h("div", {}, ctx.assessments.map((item) => h("div", { class: "list-row" },
        h("div", { class: "grow" }, h("a", { class: "cell-main", href: `/assessments/${item.ref}` }, item.name),
          h("div", { class: "cell-sub" }, [item.ref, item.tests ? `${item.counted} of ${plural(item.tests, "test")} counted` : "No tests planned", item.failing ? `${item.failing} failing` : null].filter(Boolean).join(" · "))),
        assessmentStatus(item.status))))
        : h("p", { class: "muted" }, "Not assessed yet. An assessment tests the controls this scope does itself; a requirement is verified once its controls have been tested and found effective.")),
      evidenceCard(scope, ctx)),
    h("div", { class: "stack-lg" },
      card({ title: "At a glance" }, facts([
        ["Unit", ctx.units.byId.get(scope.org_unit_id)?.name],
        ["Controls", String(scope.controls)],
        ["Offers its controls", scope.offers_controls ? "Yes: other scopes can inherit them" : "No"],
      ])),
      ownersCard(scope, ctx)));
}

function requirementsTab(scope, found, reload) {
  if (!scope.held_to.length) return card({}, emptyState({ iconName: "framework", title: "Not held to a framework yet", text: "Add one on the Overview tab. Its requirements then appear here, each applicable or left out with a reason." }));
  const chosen = found.framework.key;
  const search = searchBox("Search this framework's requirements");
  keepSearchFocus(search);
  const counts = found.counts;
  const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
    scope.held_to.length > 1 ? filterSelect("framework", scope.held_to.map((held) => [held.key === scope.held_to[0].key ? "" : held.key, held.title]), "Framework") : null,
    filterSelect("state", [["", `Every requirement (${found.applicable + counts.excluded})`], ...Object.entries(STATES).map(([key, [text]]) => [key, `${text} (${counts[key]})`])], "State"),
    button("Print", { class: "btn no-print", onclick: () => window.print() }),
    h("span", { class: "no-print" }, exportButton("statement", { scope: scope.ref, framework: chosen, state: query().get("state"), q: query().get("q") })),
    h("a", { class: "btn no-print", href: `/api/v1/scopes/${scope.ref}/security-plan`, download: "" }, icon("download", "icon icon-sm"), "Security plan"),
    h("a", { class: "btn no-print", href: `/api/v1/scopes/${scope.ref}/oscal/ssp?framework=${encodeURIComponent(chosen)}`, download: "" }, icon("download", "icon icon-sm"), "OSCAL"));
  const rows = found.requirements;
  const table = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Requirement"), h("th", { scope: "col" }, "Here"), h("th", { scope: "col" }, "Answered by"), h("th", { scope: "col", class: "no-print" }, h("span", { class: "sr-only" }, "Actions")))),
    h("tbody", {}, rows.map((row) => h("tr", {},
      h("td", {}, h("a", { class: "cell-main", href: `/frameworks/${chosen}?r=${encodeURIComponent(row.code)}` }, h("span", { class: "requirement-code" }, row.code), " ", row.title ?? ""),
        h("div", { class: "cell-sub" }, row.title ? null : row.excerpt, !row.in_baseline && row.applicable ? " Added to the baseline." : null)),
      h("td", {}, statePillOf(row.state), row.reason ? h("div", { class: "cell-sub" }, row.reason, row.decided_by ? ` (${row.decided_by}, ${date(row.decided_at)})` : "") : null,
        row.exception ? h("div", { class: "cell-sub" }, "By ", h("a", { href: `/exceptions/${row.exception.ref}` }, row.exception.ref), `, until ${date(row.exception.expires_on)}. Underneath: ${STATES[row.underlying][0].toLowerCase()}.`) : null,
        !row.exception && row.state === "excepted" ? h("div", { class: "cell-sub" }, `Underneath: ${STATES[row.underlying][0].toLowerCase()}.`) : null),
      h("td", {}, row.controls.length ? row.controls.map((control) => h("div", { class: "answered-by" },
        control.open ? h("a", { href: `/controls/${control.ref}` }, control.name) : h("span", {}, control.name),
        control.provider ? h("span", { class: "subtle" }, ` from ${control.provider.name}`) : null,
        h("div", { class: "cell-sub" }, `${control.why}.`)))
        : row.applicable ? h("span", { class: "subtle" }, "No control used here answers it") : null),
      h("td", { class: "nowrap no-print" }, h("div", { class: "row-actions" },
        WEAK.includes(row.state) ? button("Raise an issue", { kind: "btn-sm btn-ghost", "aria-label": `Raise an issue about ${row.code}`, onclick: async () => (await import("./scope-plan.js")).raiseIssue(scope, { requirement: { framework: chosen, code: row.code, title: row.title },
          name: row.state === "gap" ? `${row.code}: nothing answers it in ${scope.name}` : "", from: row.state === "gap" ? "gap" : "observation" }) }) : null,
        found.can_edit && WEAK.includes(row.state) ? button("Ask for an exception", { kind: "btn-sm btn-ghost", "aria-label": `Ask for an exception to ${row.code}`,
          onclick: async () => (await import("./exceptions.js")).requestException({ scope, requirement: { framework: chosen, code: row.code, title: row.title } }) }) : null,
        found.can_edit ? button(row.applicable ? "Leave out" : "Bring back", { kind: "btn-sm btn-ghost", "aria-label": `${row.applicable ? "Leave out" : "Bring back"} ${row.code}`,
          onclick: () => decide(scope, chosen, row, reload) }) : null)))))))
    : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or every requirement.", action: button("Clear", { onclick: () => setQuery({ q: null, state: null }) }) }
      : { iconName: "framework", title: "No requirements apply", text: "Nothing in this framework applies to this scope as it stands." });
  return h("div", { class: "stack-lg" },
    h("div", { class: "statement-head" },
      h("h2", {}, `Statement of applicability: ${found.framework.title}`),
      h("p", { class: "muted" }, [found.framework.version, found.baseline ? `starting from the ${found.baseline.title.toLowerCase()}` : "every requirement"].filter(Boolean).join(", "), `. ${found.applicable} apply here: `,
        `${counts.verified} verified, ${counts.in_place} in place, ${counts.planned} planned, ${counts.gap} with no control, ${counts.failing} failing`,
        counts.excepted ? `, ${counts.excepted} excepted` : "", `. ${counts.excluded} left out, each with its reason.`),
      found.applicable ? segments(READY.map((key) => ({ label: STATES[key][0].toLowerCase(), value: counts[key], tone: STATES[key][2] })),
        { label: `Readiness: ${READY.map((key) => `${counts[key]} ${STATES[key][0].toLowerCase()}`).join(", ")}` }) : null,
      h("p", { class: "subtle" }, "A requirement is as ready as the weakest control that answers it. In place: used here and said to be in place. ",
        "Verified: also tested and found effective, with evidence that still counts. Failing: a test found a control not to work as described. ",
        "Excepted: an approved exception covers it until a date, after which it is whatever lies underneath.")),
    bar,
    card({ title: plural(rows.length, "requirement"), flush: true }, table));
}

function controlsTab(scope, held, reload) {
  const actions = held.can_edit ? [
    button(held.candidates ? `Add controls (${held.candidates})` : "Add controls", { kind: "btn-primary", iconName: "plus", onclick: () => addControls(scope, reload) }),
    button("Inherit a control", { iconName: "link", onclick: () => inheritControl(scope, reload) })] : null;
  if (!held.controls.length) {
    return card({}, emptyState({ iconName: "control", title: "No controls yet",
      text: "Add the controls this scope uses, and inherit the ones another scope provides. Each then says where it stands here, who answers for it, and how it is done.",
      action: actions ? h("div", { class: "row" }, actions) : null }));
  }
  return h("div", { class: "stack-lg" },
    h("div", { class: "row wrap" }, h("p", { class: "muted grow" }, `${plural(held.controls.length, "control")} used in this scope.`), actions),
    card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Control"), h("th", { scope: "col" }, "Here"), h("th", { scope: "col" }, "Known to be"), h("th", { scope: "col" }, "Who and how"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Actions")))),
      h("tbody", {}, held.controls.map((item) => h("tr", {},
        h("td", {}, item.control.open ? h("a", { class: "cell-main", href: `/controls/${item.control.ref}` }, item.control.name) : h("span", { class: "cell-main" }, item.control.name),
          h("div", { class: "cell-sub" }, item.control.ref, item.relied_on_by ? ` · inherited by ${plural(item.relied_on_by, "scope")}` : "")),
        h("td", {}, standingPill(item.standing),
          item.provider ? h("div", { class: "cell-sub" }, `${INHERITED[item.inheritance]} from `, h("a", { href: `/scopes/${item.provider.scope.ref}` }, item.provider.scope.name),
            item.inheritance === "shared" ? ` · our part: ${STANDING[item.status][0].toLowerCase()}` : "") : null),
        h("td", {}, statePill(item.control.state)),
        h("td", {}, item.responsibility ?? (item.provider?.responsibility ? h("span", { class: "subtle" }, item.provider.responsibility) : h("span", { class: "subtle" }, "Not said")),
          item.statement ? h("div", { class: "cell-sub" }, item.statement) : null),
        h("td", { class: "nowrap" }, held.can_edit ? h("div", { class: "row-sm" },
          button("Edit", { kind: "btn-sm btn-ghost", "aria-label": `Edit ${item.control.name}`, onclick: () => editImplementation(scope, item, reload) }),
          button("Exception", { kind: "btn-sm btn-ghost", "aria-label": `Ask for an exception to ${item.control.name}`,
            onclick: async () => (await import("./exceptions.js")).requestException({ scope, control: item.control }) }),
          button("Remove", { kind: "btn-sm btn-ghost", "aria-label": `Remove ${item.control.name}`, onclick: () => confirmAction({
            title: `Stop using ${item.control.name} here?`, text: "The control itself stays as it is. This scope no longer counts it.",
            confirmLabel: "Remove", danger: true,
            run: async () => {
              try {
                await del(`/api/v1/scopes/${scope.ref}/controls/${item.id}`);
                toast("Removed.");
                reload();
              } catch (error) {
                toast(error.detail || "That could not be removed.");
              }
            } }) })) : null))))))));
}

export function scopePage(main, params) {
  const wanted = query().get("tab");
  const tab = TABS.some(([key]) => key === wanted) ? wanted : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/scopes/${params.ref}`;
      const [scope, vocab, unitIndex] = await Promise.all([get(base, null, { fresh: true }), vocabularies(), units()]);
      let extra = null;
      const assessed = tab === "overview" ? (await get("/api/v1/assessments", { scope: params.ref, limit: 10 }, { fresh: true })).data : [];
      if (tab === "history") extra = (await get(`${base}/history`, null, { fresh: true })).data;
      if (tab === "controls") extra = (await get(`${base}/controls`, null, { fresh: true })).data;
      // The plan of action is drawn by its own module, loaded when the tab is opened.
      if (tab === "plan") extra = { plan: (await get(`${base}/plan-of-action`, null, { fresh: true })).data, draw: (await import("./scope-plan.js")).planTab };
      if (tab === "requirements" && scope.data.held_to.length) {
        const asked = query();
        const framework = scope.data.held_to.find((held) => held.key === asked.get("framework"))?.key ?? scope.data.held_to[0].key;
        extra = (await get(`${base}/requirements`, { framework, state: asked.get("state") ?? undefined, q: asked.get("q") ?? undefined }, { fresh: true })).data;
      }
      return { scope: { ...scope.data, type: "scope" }, vocab, units: unitIndex, extra, assessments: assessed };
    },
    view: (data, reload) => {
      const scope = data.scope;
      document.title = `${scope.name} · ${scope.ref}`;
      const ctx = { vocab: data.vocab, units: data.units, reload, assessments: data.assessments };
      const edit = scope.can.edit ? button("Edit", { iconName: "edit", onclick: () => editScope({ scope, unitIndex: data.units, onDone: reload }) }) : null;
      return h("div", { class: "stack" },
        recordHeader(scope, { badges: [scope.status === "retired" ? pill("Retired") : null, scope.offers_controls ? pill("Offers its controls", "info") : null], actions: edit }),
        tabBar(TABS, tab),
        tab === "history" ? card({ flush: true }, timeline(data.extra)) : tab === "controls" ? controlsTab(scope, data.extra, reload)
          : tab === "plan" ? data.extra.draw(scope, data.extra.plan)
          : tab === "requirements" ? requirementsTab(scope, data.extra, reload) : overview(scope, ctx));
    },
  });
}

// ---- The list ----

export function scopeList(main) {
  const meta = TYPES.scope;
  return show(main, {
    title: "Scopes",
    load: async () => {
      const [page, unitIndex] = await Promise.all([get("/api/v1/scopes", Object.fromEntries(query()), { fresh: true }), units()]);
      return { page, units: unitIndex };
    },
    view: (data, reload) => {
      const rows = data.page.data;
      const mayAdd = can("steward");
      const add = () => editScope({ unitIndex: data.units });
      const search = searchBox("Search scopes");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        filterSelect("status", [["", "Any status"], ["active", "Active"], ["retired", "Retired"]], "Status"), mineToggle());
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, sortHeader("Scope", "name"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Owner"), h("th", { scope: "col" }, "Held to"),
          h("th", { scope: "col", class: "numeric" }, "Controls"), sortHeader("Status", "status"), sortHeader("Updated", "updated_at"))),
        h("tbody", {}, rows.map((r) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/scopes/${r.ref}` }, r.name), r.offers_controls ? [" ", pill("Offers its controls", "info")] : null,
            h("div", { class: "cell-sub" }, [r.ref, r.restricted ? "Restricted" : null].filter(Boolean).join(" · "))),
          h("td", {}, data.units.byId.get(r.org_unit_id)?.name ?? ""),
          ownerCell(r),
          h("td", {}, r.frameworks.length ? r.frameworks.map((f) => h("div", {}, f.title)) : h("span", { class: "subtle" }, "Nothing yet")),
          h("td", { class: "numeric" }, String(r.controls)),
          h("td", {}, statusPill(r.status)),
          h("td", { class: "nowrap muted" }, relative(r.updated_at)))))))
        : emptyState(isFiltering() ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.", action: button("Clear filters", { onclick: clearFilters }) }
          : { iconName: "scope", title: "No scopes yet", text: meta.lede, action: mayAdd ? button("Add a scope", { kind: "btn-primary", onclick: add }) : null });
      void reload;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Compliance", title: "Scopes", lede: meta.lede, actions: [mayAdd ? button("Add a scope", { kind: "btn-primary", iconName: "plus", onclick: add }) : null, exportButton("scopes")] }),
        bar,
        card({ title: plural(data.page.meta.total, "scope"), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
