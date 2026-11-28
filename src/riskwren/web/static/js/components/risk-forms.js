// The forms of the risk register: raising and editing a risk, and assessing one.

import { similarHint } from "./tidy.js";
import { get, patch, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { categoryOptions, unitOptions } from "../core/lookups.js";
import { navigate } from "../core/router.js";
import { overallImpact, rating as ratingFor } from "../core/scoring.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { recordChip, TYPES } from "./record.js";
import { section } from "./form.js";
import { ownUnits } from "../core/session.js";
import { levelPicker, rating, suggestionView } from "./risk.js";
import { toast } from "./toast.js";

/** Raise a risk, or edit the one given. A new risk can be started from the library. */
export function editRisk({ record = null, draft = null, program, units, onDone }) {
  const from = draft?.values ?? {};
  openOverlay({
    title: record ? "Edit risk" : "Raise a risk",
    subtitle: record ? record.ref : "Something that could happen, and would matter.",
    render: (body, footer, close) => {
      const name = field("Title", { value: record?.name ?? from.name ?? "", required: true,
        hint: "A few words that name it. For example: Loss of irreplaceable specimens." });
      const category = select("Category", categoryOptions(program, { blank: record ? null : "Choose…" }),
        { value: record?.category ?? from.category ?? "", required: true, hint: "Its category sets the appetite it is held to." });
      const unit = select("Unit", unitOptions(units.tree, { only: ownUnits(), blank: record ? null : "Choose…" }),
        { value: record?.org_unit_id ?? draft?.org_unit?.id ?? "", required: true, hint: "The unit that owns the risk." });
      const cause = field("Cause", { type: "textarea", value: record?.cause ?? from.cause ?? "", hint: "What makes it possible." });
      const event = field("Event", { type: "textarea", value: record?.event ?? from.event ?? "", hint: "What would happen." });
      const consequence = field("Consequence", { type: "textarea", value: record?.consequence ?? from.consequence ?? "", hint: "What it would mean for the organization." });
      const restricted = checkbox("Restricted", { checked: record?.restricted ?? false,
        hint: "Known only to its owners, its unit's stewards and leaders, managers, and auditors." });
      let libraryKey = null;

      // Starting from the library fills the statement in; it is then made specific.
      const found = h("div", { class: "pick-results", role: "listbox", "aria-label": "Library risks found" });
      const search = h("input", { class: "input", type: "search", placeholder: "Search the library: freezer, ransomware, award…", "aria-label": "Search the risk library" });
      let latest = 0;
      const look = async () => {
        const mine = ++latest;
        const words = search.value.trim();
        if (words.length < 2) {
          found.replaceChildren();
          return;
        }
        const entries = (await get("/api/v1/risk-library", { q: words })).data.slice(0, 6);
        if (mine !== latest) return;
        found.replaceChildren(...(entries.length ? entries.map((entry) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
          name.input.value = entry.title;
          category.input.value = entry.category;
          cause.input.value = entry.cause;
          event.input.value = entry.event;
          consequence.input.value = entry.consequence;
          libraryKey = entry.key;
          search.value = "";
          found.replaceChildren();
          name.input.focus();
        } }, icon("risk"), h("span", {}, h("span", { class: "cell-main" }, entry.title), h("span", { class: "cell-sub" }, ` ${entry.category_label ?? ""}`))))
          : [h("div", { class: "subtle pick-none" }, "Nothing in the library matches. Write it below.")]));
      };
      let timer = null;
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(look, 180);
      });

      const problem = banner();
      const saveButton = button(record ? "Save" : "Raise", { kind: "btn-primary" });
      const fields = { name, category, org_unit_id: unit, cause, event, consequence };
      const values = () => ({
        name: name.input.value, category: category.input.value || null,
        org_unit_id: unit.input.value ? Number(unit.input.value) : null,
        cause: cause.input.value, event: event.input.value, consequence: consequence.input.value,
        restricted: restricted.input.checked, ...(record ? {} : { library_key: libraryKey }),
      });
      const save = async () => {
        const done = await submit({ button: saveButton, fields, banner: problem,
          run: () => (record ? patch(`/api/v1/risks/${record.ref}`, { version: record.version, ...values() }) : post("/api/v1/risks", values())) });
        if (!done) return;
        close();
        if (record) {
          toast("Saved.");
          onDone?.(done.data);
        } else {
          if (draft) await post(`/api/v1/drafts/${draft.id}/use`, { ref: done.data.ref }).catch(() => toast("It was made, but the draft could not be marked as used."));
          toast(`${done.data.ref} was raised. Assess it next.`);
          navigate(`/risks/${done.data.ref}`);
        }
      };
      body.append(h("form", { class: "stack-lg", novalidate: true, onsubmit: (submitted) => {
        submitted.preventDefault();
        save();
      } }, problem,
      record ? null : section("Start from the library", h("div", { class: "field" }, search, found),
        h("p", { class: "hint subtle" }, "Optional. Choosing one fills in the statement, which you then make your own.")),
      section("What could go wrong", name.node, similarHint("risk", name.input, { unit: () => unit.input.value, apartFrom: record?.ref }), cause.node, event.node, consequence.node),
      section("Where it belongs", h("div", { class: "grid-2" }, category.node, unit.node), restricted.node)));
      saveButton.addEventListener("click", save);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

const KINDS = [
  ["inherent", "Inherent", "How likely, and how bad, if the controls were not there or did not work?"],
  ["residual", "Residual", "How likely, and how bad, given the controls as they actually are?"],
  ["target", "Target", "Where should this be once treatment is complete?"],
];

/** Record a judgment of a risk: likelihood, impact on each dimension that applies, and why. */
export function assessRisk({ risk, program, kind = null, onDone }) {
  const method = program.method;
  const start = kind ?? (risk.ratings.inherent.rating ? "residual" : "inherent");
  openOverlay({
    title: "Assess",
    subtitle: `${risk.ref} · ${risk.name}`,
    render: async (body, footer, close) => {
      const { meta } = await get(`/api/v1/risks/${risk.ref}/assessments`, null, { fresh: true });
      const problem = banner();
      const which = select("Which rating", KINDS.map(([key, text]) => [key, text]), { value: start });
      const question = h("p", { class: "muted" });
      const holder = h("div", { class: "stack-lg" });
      const live = h("div", { class: "live-rating", "aria-live": "polite" });
      const rationale = field("Why", { type: "textarea", required: true,
        hint: "A sentence or two. A rating is a judgment, and this is what makes it one someone else can follow." });
      let likelihood = null;
      let pickers = {};

      const levels = () => Object.fromEntries(Object.entries(pickers).map(([key, picker]) => [key, picker.value()]));
      const drawLive = () => {
        const impact = overallImpact(levels());
        const chosen = likelihood?.value();
        if (!chosen || !impact) {
          live.replaceChildren(h("span", { class: "muted" }, "Choose a likelihood and at least one impact to see the rating."));
          return;
        }
        const key = ratingFor(method, chosen, impact);
        const impactLabel = method.impact_levels.find((item) => item.level === impact).label;
        live.replaceChildren(rating(program, key),
          h("span", { class: "muted" }, `Likelihood ${chosen} × impact ${impact} (${impactLabel}, the highest rated)`));
      };
      const draw = () => {
        const current = which.input.value;
        question.textContent = KINDS.find(([key]) => key === current)[2];
        const before = risk.assessments?.[current];
        likelihood = levelPicker({ legend: "Likelihood", levels: method.likelihood, value: before?.likelihood ?? null, onChange: drawLive });
        pickers = {};
        const dims = method.dimensions.map((dimension) => {
          const was = before?.dimensions.find((d) => d.key === dimension.key)?.level ?? null;
          const picker = levelPicker({ legend: dimension.label, hint: dimension.question, allowNone: true, value: was, onChange: drawLive,
            levels: method.impact_levels.map((item) => ({ ...item, definition: dimension.levels[String(item.level)] })) });
          pickers[dimension.key] = picker;
          return picker.node;
        });
        const suggestion = current === "residual" && meta.suggestion
          ? h("div", { class: "card" }, h("div", { class: "card-header" }, h("h2", { class: "grow" }, "What the controls suggest")),
            h("div", { class: "card-body" }, suggestionView(program, meta.suggestion))) : null;
        const hint = current === "residual" && !meta.suggestion
          ? h("p", { class: "subtle" }, "Assess the inherent risk first, and the controls linked to this risk will suggest a residual rating.") : null;
        holder.replaceChildren(...[suggestion, hint, section("How likely", likelihood.node),
          section("How bad", h("p", { class: "hint subtle" }, "Rate the dimensions that apply. The overall impact is the highest of them."), dims)].filter(Boolean));
        drawLive();
      };
      which.input.addEventListener("change", draw);
      draw();

      const saveButton = button("Record the assessment", { kind: "btn-primary" });
      saveButton.addEventListener("click", async () => {
        const done = await submit({ button: saveButton, banner: problem, fields: { rationale },
          run: () => post(`/api/v1/risks/${risk.ref}/assessments`, { kind: which.input.value, likelihood: likelihood.value() ?? 0,
            impact_levels: levels(), rationale: rationale.input.value }) });
        if (done) {
          close();
          toast("The assessment was recorded.");
          onDone?.(done.data);
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, h("div", { class: "stack-sm" }, which.node, question), live, holder,
        section("The reasoning", rationale.node,
          h("p", { class: "subtle" }, "An assessment is never edited. If things change, record a new one: it supersedes this, and both stay on the record."))));
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Say which processes, systems, and third parties a risk concerns. */
export function editSubjects({ risk, onDone }) {
  const chosen = risk.subjects.records.map((record) => ({ ...record }));
  openOverlay({
    title: "What this risk concerns",
    subtitle: `${risk.ref} · ${risk.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const list = h("div", { class: "stack-sm" });
      const search = h("input", { class: "input", type: "search", placeholder: "Find a process, system, or third party", "aria-label": "Find a record" });
      const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Records found" });
      const draw = () => {
        list.replaceChildren(...(chosen.length ? chosen.map((record, index) => h("div", { class: "owner-row" },
          h("div", { class: "grow" }, recordChip(record, { link: false })),
          button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${record.name}`, onclick: () => {
            chosen.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "Nothing yet. A risk is easier to act on when it is attached to what it threatens.")]));
      };
      let latest = 0;
      const look = async () => {
        const mine = ++latest;
        const words = search.value.trim();
        if (words.length < 2) {
          results.replaceChildren();
          return;
        }
        const pages = await Promise.all(["process", "system", "third_party", "information"].map((type) =>
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
      let timer = null;
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(look, 180);
      });
      draw();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/risks/${risk.ref}/subjects`, { subjects: chosen.map((record) => record.ref) }) });
        if (done) {
          close();
          toast("Saved.");
          onDone?.(done.data);
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, list, h("div", { class: "field" }, h("div", { class: "label" }, "Add"), search, results),
        risk.subjects.hidden ? h("p", { class: "subtle" }, `It also concerns ${risk.subjects.hidden} that you do not have access to. They stay as they are.`) : null));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Raise a risk to a unit above its own, with a reason, or take it back down. */
export function escalateRisk({ risk, units, onDone }) {
  const above = [];
  for (let unit = units.byId.get(units.byId.get(risk.org_unit_id)?.parent_id); unit; unit = units.byId.get(unit.parent_id)) above.push(unit);
  openOverlay({
    title: "Escalate",
    subtitle: `${risk.ref} · ${risk.name}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const problem = banner();
      const to = select("Escalate to", above.map((unit) => [unit.id, unit.name]), { value: risk.escalated_to_unit_id ?? above[0]?.id ?? "" });
      const reason = field("Why", { type: "textarea", required: true, value: risk.escalation_reason ?? "",
        hint: "What the unit above needs to decide or provide." });
      const send = (payload, message) => async (clicked) => {
        const done = await submit({ button: clicked.currentTarget, banner: problem, fields: { unit_id: to, reason },
          run: () => put(`/api/v1/risks/${risk.ref}/escalation`, payload()) });
        if (done) {
          close();
          toast(message);
          onDone?.(done.data);
        }
      };
      body.append(h("div", { class: "stack" }, problem,
        above.length ? [to.node, reason.node] : h("p", { class: "muted" }, "This risk already belongs to the top of the organization.")));
      footer.replaceChildren(h("div", { class: "row wrap" },
        above.length ? button("Escalate", { kind: "btn-primary", onclick: send(() => ({ unit_id: Number(to.input.value), reason: reason.input.value }), "The risk was escalated.") }) : null,
        risk.escalated_to_unit_id ? button("Take it back down", { onclick: send(() => ({ unit_id: null }), "The risk is no longer escalated.") }) : null,
        button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** Close a risk that no longer applies, with the reason. It stays on the record. */
export function closeRisk({ risk, onDone }) {
  openOverlay({
    title: "Close this risk?",
    subtitle: `${risk.ref} · ${risk.name}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const problem = banner();
      const reason = field("Why it no longer applies", { type: "textarea", required: true,
        hint: "For example: the activity has stopped, or the system has been retired. A risk that has only been reduced stays open." });
      const go = button("Close the risk", { kind: "btn-primary" });
      go.addEventListener("click", async () => {
        const done = await submit({ button: go, banner: problem, fields: { closed_reason: reason },
          run: () => patch(`/api/v1/risks/${risk.ref}`, { version: risk.version, status: "closed", closed_reason: reason.input.value }) });
        if (done) {
          close();
          toast("The risk was closed. It stays on the record.");
          onDone?.(done.data);
        }
      });
      body.append(h("div", { class: "stack" }, problem, reason.node));
      footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
