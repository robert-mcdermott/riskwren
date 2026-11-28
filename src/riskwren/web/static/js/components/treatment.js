// What is done about a risk: its controls, its response, plans and their actions, and acceptance.

import { del, get, patch, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { session } from "../core/session.js";
import { editControl, REDUCES, reducesLabel, RELIANCE, statePill } from "./control.js";
import { banner, field, select, submit } from "./form.js";
import { confirmAction, openOverlay } from "./overlay.js";
import { personField } from "./people-picker.js";
import { recordChip } from "./record.js";
import { rating, ratingOptions, suggestionView } from "./risk.js";
import { toast } from "./toast.js";
import { alert, card, pill } from "./ui.js";

function me() {
  const account = session().account;
  return { account_id: account.id, name: account.name };
}

function footerOf(footer, primary, close) {
  footer.replaceChildren(h("div", { class: "row" }, primary, button("Cancel", { kind: "btn-ghost", onclick: close })));
  footer.hidden = false;
}

// --- Controls on a risk ---------------------------------------------------------------------

/** Link a control to a risk, or change how one already linked bears on it. */
export function linkControl({ risk, existing = null, onDone }) {
  openOverlay({
    title: existing ? "How this control bears on the risk" : "Link a control",
    subtitle: `${risk.ref} · ${risk.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      let target = existing?.control ?? null;
      const chosen = h("div", {});
      const search = h("input", { class: "input", type: "search", placeholder: "Find a control by name or reference", "aria-label": "Find a control" });
      const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Controls found" });
      const reduces = select("What it reduces", REDUCES, { value: existing?.reduces ?? "likelihood",
        hint: "A preventive control reduces how likely the event is; a corrective one reduces how bad it would be." });
      const reliance = select("How much the risk relies on it", RELIANCE, { value: existing?.reliance ?? "primary" });
      const note = field("Note", { value: existing?.note ?? "", hint: "Optional." });
      const drawChosen = () => {
        search.hidden = Boolean(target);
        chosen.replaceChildren(...(target ? [h("div", { class: "row" }, h("div", { class: "grow" }, recordChip(target, { link: false })),
          existing ? null : button("Change", { kind: "btn-ghost btn-sm", onclick: () => {
            target = null;
            drawChosen();
            look();
          } }))] : []));
      };
      let latest = 0;
      const look = async () => {
        const mine = ++latest;
        const found = (await get("/api/v1/controls", { q: search.value.trim(), sort: "name", limit: 8, status: "active" }, { fresh: true })).data;
        if (mine !== latest) return;
        results.replaceChildren(...(found.length ? found.map((control) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => {
          target = control;
          results.replaceChildren();
          drawChosen();
        } }, icon("control"), h("span", { class: "grow" }, h("span", { class: "cell-main" }, control.name), h("span", { class: "cell-sub" }, ` ${control.ref}`)), statePill(control.state)))
          : [h("div", { class: "subtle pick-none" }, "No control matches. Add it to the library first.")]));
      };
      let timer = null;
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(look, 180);
      });
      drawChosen();
      if (!existing) look();
      const save = button(existing ? "Save" : "Link", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        if (!target) {
          problem.textContent = "Choose the control to link.";
          problem.hidden = false;
          return;
        }
        const done = await submit({ button: save, banner: problem, fields: { reduces, reliance, note },
          run: () => put(`/api/v1/risks/${risk.ref}/controls`, { control: target.ref, reduces: reduces.input.value, reliance: reliance.input.value, note: note.input.value || null }) });
        if (done) {
          close();
          toast(existing ? "Saved." : "The control was linked.");
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("div", { class: "field" }, h("div", { class: "label" }, "Control"), chosen, search, results), reduces.node, reliance.node, note.node));
      footerOf(footer, save, close);
    },
  });
}

/** The Controls tab of a risk: what bears on it, how well each is known to work, and what they suggest. */
export function controlsTab(risk, data, ctx) {
  const { controls, hidden, suggestion } = data.controls;
  const canEdit = risk.can.edit && risk.status !== "closed";
  const linked = new Set(controls.map((item) => item.control.library_key));
  const row = (item) => h("tr", {},
    h("td", {}, recordChip(item.control), item.control.is_key ? [" ", pill("Key", "accent")] : null,
      h("div", { class: "cell-sub" }, item.note ?? item.control.statement)),
    h("td", {}, reducesLabel(item.reduces), h("div", { class: "cell-sub" }, item.reliance === "primary" ? "Primary" : "Supporting")),
    h("td", {}, statePill(item.control.state), h("div", { class: "cell-sub" }, item.control.rated_at ? `Rated ${date(item.control.rated_at)}` : "Never rated")),
    canEdit ? h("td", { class: "actions" },
      button("Change", { kind: "btn-ghost btn-sm", "aria-label": `Change how ${item.control.name} bears on the risk`, onclick: () => linkControl({ risk, existing: item, onDone: ctx.reload }) }),
      button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove ${item.control.name} from this risk`, onclick: () =>
        confirmAction({ title: "Take this control off the risk?", confirmLabel: "Remove",
          text: `${item.control.name} stays in the library. If the residual rating leaned on it, the risk will be flagged for a new assessment.`,
          run: async () => {
            await del(`/api/v1/risks/${risk.ref}/controls/${item.control.ref}`);
            toast("The control was removed from this risk.");
            ctx.reload();
          } }) })) : null);
  const offered = data.suggested.filter((entry) => !linked.has(entry.key) && !controls.some((item) => item.control.name === entry.title));
  const adopt = (entry) => editControl({ vocab: ctx.vocab, units: ctx.units, from: entry, unitId: risk.org_unit_id, onDone: async (control) => {
    await put(`/api/v1/risks/${risk.ref}/controls`, { control: control.ref, reduces: entry.reduces, reliance: "primary" });
    toast(`${control.ref} was added and linked. Rate it when you know how well it works.`);
    ctx.reload();
  } });
  return h("div", { class: "stack-lg" },
    card({ title: plural(controls.length, "control"), flush: controls.length > 0,
      actions: canEdit ? button("Link a control", { kind: "btn-sm", iconName: "link", onclick: () => linkControl({ risk, onDone: ctx.reload }) }) : null },
    controls.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Control"), h("th", { scope: "col" }, "How it bears"), h("th", { scope: "col" }, "Known to be"), canEdit ? h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Actions")) : null)),
      h("tbody", {}, controls.map(row))))
      : h("p", { class: "muted" }, "No control is linked yet. Link the things that are actually done about this risk; then rate how well each works."),
    hidden ? h("p", { class: "subtle" }, `And ${hidden} more that you do not have access to.`) : null),
    card({ title: "What the controls suggest" },
      suggestion ? suggestionView(ctx.program, suggestion)
        : h("p", { class: "muted" }, "Assess the inherent risk first. The controls will then suggest a residual rating, with the arithmetic shown.")),
    canEdit && offered.length ? card({ title: "Commonly used for a risk like this", flush: true },
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("tbody", {}, offered.map((entry) => h("tr", {},
        h("td", {}, h("div", { class: "cell-main" }, entry.title), h("div", { class: "cell-sub" }, entry.statement)),
        h("td", { class: "actions" }, button("Add and link", { kind: "btn-sm", onclick: () => adopt(entry) })))))))) : null);
}

// --- Treatment ------------------------------------------------------------------------------

const RESPONSES = [["reduce", "Reduce", "Bring it down through a treatment plan"], ["accept", "Accept", "Live with what remains, by a named decision"],
  ["transfer", "Transfer", "Pass the consequence to an insurer or another party"], ["avoid", "Avoid", "Stop the activity that gives rise to it"]];

function setResponse({ risk, care, onDone }) {
  openOverlay({
    title: "Response",
    subtitle: `${risk.ref} · ${risk.name}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const problem = banner();
      const response = select("What is to be done", RESPONSES.map(([key, text, hint]) => [key, `${text}: ${hint.toLowerCase()}`]), { value: care.response ?? "reduce" });
      const rationale = field("Why", { type: "textarea", required: true, value: care.response_rationale ?? "" });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { response, rationale },
          run: () => put(`/api/v1/risks/${risk.ref}/response`, { response: response.input.value, rationale: rationale.input.value }) });
        if (done) {
          close();
          toast("The response was recorded.");
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack" }, problem, response.node, rationale.node));
      footerOf(footer, save, close);
    },
  });
}

function openPlan({ risk, program, onDone }) {
  openOverlay({
    title: "Open a treatment plan",
    subtitle: `${risk.ref} · ${risk.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const objective = field("Objective", { type: "textarea", required: true, hint: "What the plan will achieve. For example: monitor the freezer alarm at all hours." });
      const target = select("Target rating", ratingOptions(program, "Not set"), { value: risk.ratings.target.rating ?? "" });
      const owner = personField("Who owns the plan", { value: me() });
      const due = field("Due", { type: "date", required: true, hint: "While the plan is on time, the risk is shown as being treated." });
      const save = button("Open the plan", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { objective, target_rating: target, owner_id: owner, due_on: due },
          run: () => post(`/api/v1/risks/${risk.ref}/plans`, { objective: objective.input.value, target_rating: target.input.value || null,
            owner_id: owner.value() ?? 0, due_on: due.input.value || "0001-01-01" }) });
        if (done) {
          close();
          toast(`${done.data.ref} was opened. Add its actions next.`);
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, objective.node, h("div", { class: "grid-2" }, target.node, due.node), owner.node));
      footerOf(footer, save, close);
    },
  });
}

function addAction({ plan, onDone }) {
  openOverlay({
    title: "Add an action",
    subtitle: `${plan.ref} · ${plan.objective}`,
    render: (body, footer, close) => {
      const problem = banner();
      const title = field("What is to be done", { required: true });
      const detail = field("Detail", { type: "textarea", hint: "Optional." });
      const owner = personField("Who will do it", { value: me() });
      const due = field("Due", { type: "date", required: true, value: plan.due_on });
      const save = button("Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { title, detail, owner_id: owner, due_on: due },
          run: () => post(`/api/v1/plans/${plan.ref}/actions`, { title: title.input.value, detail: detail.input.value || null,
            owner_id: owner.value() ?? 0, due_on: due.input.value || "0001-01-01" }) });
        if (done) {
          close();
          toast("The action was added.");
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, title.node, detail.node, h("div", { class: "grid-2" }, owner.node, due.node)));
      footerOf(footer, save, close);
    },
  });
}

/** Finish an action, with a note of what was done. */
export function finishAction({ action, onDone }) {
  openOverlay({
    title: "Mark as done",
    subtitle: `${action.ref} · ${action.title}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const problem = banner();
      const note = field("What was done", { type: "textarea", hint: "Optional, and worth a sentence: it is what the next person will read." });
      const save = button("Done", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { completion_note: note },
          run: () => patch(`/api/v1/actions/${action.ref}`, { status: "done", completion_note: note.input.value || null }) });
        if (done) {
          close();
          toast("Done.");
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack" }, problem, note.node));
      footerOf(footer, save, close);
    },
  });
}

/** Move an action's date, with the reason. The original date stays on the record. */
export function moveAction({ action, onDone }) {
  openOverlay({
    title: "Move the date",
    subtitle: `${action.ref} · ${action.title}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const problem = banner();
      const due = field("New date", { type: "date", required: true, value: action.due_on });
      const reason = field("Why it is moving", { type: "textarea", required: true });
      const save = button("Move", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { due_on: due, reason },
          run: () => patch(`/api/v1/actions/${action.ref}`, { due_on: due.input.value, reason: reason.input.value }) });
        if (done) {
          close();
          toast("The date was moved. The original stays on the record.");
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", { class: "muted" }, `Originally due ${date(action.original_due_on)}${action.extensions.length ? `, moved ${plural(action.extensions.length, "time")} since` : ""}.`),
        due.node, reason.node));
      footerOf(footer, save, close);
    },
  });
}

const ACTION_STATUS = { open: ["Open", ""], in_progress: ["In progress", "info"], done: ["Done", "ok"], cancelled: ["Cancelled", ""] };

export function actionStatus(action) {
  const [text, tone] = ACTION_STATUS[action.status] ?? [action.status, ""];
  return action.overdue ? pill("Overdue", "danger") : pill(text, tone);
}

export function dueCell(item) {
  return h("span", { class: item.overdue ? "overdue" : "" }, date(item.due_on),
    item.extensions?.length ? h("div", { class: "cell-sub" }, `Was ${date(item.original_due_on)}`) : null);
}

/** What a person may do with an action: start it, finish it, move its date, or reopen it. */
export function actionButtons(action, reload) {
  if (!action.can.act) return null;
  const set = (status) => async () => {
    await patch(`/api/v1/actions/${action.ref}`, { status });
    reload();
  };
  if (action.status === "done" || action.status === "cancelled") return button("Reopen", { kind: "btn-ghost btn-sm", onclick: set("open") });
  return h("div", { class: "row-sm" },
    action.status === "open" ? button("Start", { kind: "btn-ghost btn-sm", onclick: set("in_progress") }) : null,
    button("Done", { kind: "btn-sm", onclick: () => finishAction({ action, onDone: reload }) }),
    button("Move", { kind: "btn-ghost btn-sm", onclick: () => moveAction({ action, onDone: reload }) }));
}

function planCard(plan, ctx) {
  const state = plan.overdue ? pill("Overdue", "danger") : pill({ active: "On time", complete: "Complete", cancelled: "Cancelled" }[plan.status], plan.status === "active" ? "info" : plan.status === "complete" ? "ok" : "");
  const cancel = () => openOverlay({ title: "Cancel this plan?", subtitle: plan.ref, kind: "dialog", render: (body, footer, close) => {
    const problem = banner();
    const reason = field("Why", { type: "textarea", required: true });
    const go = button("Cancel the plan", { kind: "btn-primary" });
    go.addEventListener("click", async () => {
      const done = await submit({ button: go, banner: problem, fields: { reason }, run: () => post(`/api/v1/plans/${plan.ref}/cancellation`, { reason: reason.input.value }) });
      if (done) {
        close();
        toast("The plan was cancelled. Its open actions were cancelled with it.");
        ctx.reload();
      }
    });
    body.append(h("div", { class: "stack" }, problem, reason.node));
    footerOf(footer, go, close);
  } });
  const manage = plan.can.manage && plan.status === "active";
  return card({ title: `${plan.ref} · ${plan.objective}`, flush: plan.actions.length > 0,
    actions: h("div", { class: "row-sm" }, state, manage ? button("Add an action", { kind: "btn-sm", iconName: "plus", onclick: () => addAction({ plan, onDone: ctx.reload }) }) : null,
      manage ? button("Cancel", { kind: "btn-ghost btn-sm", onclick: cancel }) : null),
    footer: h("div", { class: "row wrap subtle" }, `Owned by ${plan.owner.name}`, h("span", {}, `Due ${date(plan.due_on)}`),
      plan.target_rating ? h("span", { class: "row-sm" }, "Target", rating(ctx.program, plan.target_rating)) : null,
      h("span", {}, `${plan.progress.done} of ${plan.progress.total} done`), plan.closed_note ? h("span", {}, plan.closed_note) : null) },
  plan.actions.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("tbody", {}, plan.actions.map((action) => h("tr", {},
      h("td", {}, h("div", { class: "cell-main" }, action.title), h("div", { class: "cell-sub" }, [action.ref, action.owner.name, action.completion_note].filter(Boolean).join(" · "))),
      h("td", { class: "nowrap" }, dueCell(action)),
      h("td", {}, actionStatus(action)),
      h("td", { class: "actions" }, actionButtons(action, ctx.reload)))))))
    : h("p", { class: "muted" }, "No actions yet. A plan is the sum of its actions: add what will be done, by whom, and by when."));
}

function acceptRisk({ risk, care, program, onDone }) {
  openOverlay({
    title: "Accept this risk",
    subtitle: `${risk.ref} · ${risk.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const rationale = field("Why it is being lived with", { type: "textarea", required: true });
      const conditions = field("Conditions", { type: "textarea", hint: "Optional. What must stay true while the acceptance stands." });
      const until = field("Until", { type: "date", required: true, value: care.authority.latest, max: care.authority.latest,
        hint: `At this rating, for at most ${plural(care.authority.max_months, "month")}: no later than ${date(care.authority.latest)}.` });
      const save = button("Accept", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { rationale, conditions, expires_on: until },
          run: () => post(`/api/v1/risks/${risk.ref}/acceptances`, { rationale: rationale.input.value, conditions: conditions.input.value || null, expires_on: until.input.value || "0001-01-01" }) });
        if (done) {
          close();
          toast("The acceptance was recorded in your name.");
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        alert("info", icon("info"), h("div", {}, "You are accepting, in your own name, a residual risk rated ", rating(program, risk.ratings.residual.rating),
          " in a category whose appetite is ", rating(program, care.authority.appetite), ". This is a statement and is never edited; it can be withdrawn.")),
        rationale.node, conditions.node, until.node));
      footerOf(footer, save, close);
    },
  });
}

const ACCEPTANCE_STATE = { in_force: ["In force", "ok"], expired: ["Expired", "danger"], withdrawn: ["Withdrawn", ""] };

export function acceptanceState(acceptance) {
  const [text, tone] = ACCEPTANCE_STATE[acceptance.state];
  return pill(acceptance.state === "in_force" && acceptance.expires_in_days <= 60 ? `Expires in ${plural(acceptance.expires_in_days, "day")}` : text,
    acceptance.state === "in_force" && acceptance.expires_in_days <= 60 ? "warn" : tone);
}

export function withdrawAcceptance({ acceptance, onDone }) {
  openOverlay({ title: "Withdraw this acceptance?", kind: "dialog", render: (body, footer, close) => {
    const problem = banner();
    const reason = field("Why", { type: "textarea", required: true });
    const go = button("Withdraw", { kind: "btn-primary" });
    go.addEventListener("click", async () => {
      const done = await submit({ button: go, banner: problem, fields: { reason }, run: () => post(`/api/v1/acceptances/${acceptance.id}/withdrawal`, { reason: reason.input.value }) });
      if (done) {
        close();
        toast("The acceptance was withdrawn. The risk needs a decision again.");
        onDone?.();
      }
    });
    body.append(h("div", { class: "stack" }, problem, reason.node));
    footerOf(footer, go, close);
  } });
}

function acceptanceCard(acceptance, ctx) {
  return card({ title: `Accepted by ${acceptance.accepted_by}`,
    actions: h("div", { class: "row-sm" }, acceptanceState(acceptance),
      acceptance.state === "in_force" && acceptance.can_withdraw ? button("Withdraw", { kind: "btn-ghost btn-sm", onclick: () => withdrawAcceptance({ acceptance, onDone: ctx.reload }) }) : null) },
  h("dl", { class: "dl" },
    h("dt", {}, "What was accepted"), h("dd", {}, rating(ctx.program, acceptance.rating_accepted), h("div", { class: "cell-sub" }, `Likelihood ${acceptance.likelihood} · Impact ${acceptance.impact}`)),
    h("dt", {}, "Why"), h("dd", { class: "prose" }, acceptance.rationale),
    acceptance.conditions ? [h("dt", {}, "Conditions"), h("dd", { class: "prose" }, acceptance.conditions)] : null,
    h("dt", {}, "From"), h("dd", {}, `${date(acceptance.accepted_at)} until ${date(acceptance.expires_on)}`),
    acceptance.withdrawn_at ? [h("dt", {}, "Withdrawn"), h("dd", {}, `${date(acceptance.withdrawn_at)} by ${acceptance.withdrawn_by}: ${acceptance.withdrawn_reason}`)] : null));
}

/** The Treatment tab of a risk: the response, the plans and their actions, and any acceptance. */
export function treatmentTab(risk, care, ctx) {
  const canEdit = risk.can.edit && risk.status !== "closed";
  const above = ["needs_decision", "treated", "accepted"].includes(risk.standing);
  const chosen = RESPONSES.find(([key]) => key === care.response);
  const context = { ...ctx, canManage: risk.can.edit };
  return h("div", { class: "stack-lg" },
    risk.standing === "needs_decision" ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, "This risk is above appetite and needs a decision. "),
      "Open a plan that will bring it down, or have someone with the authority accept what remains.")) : null,
    card({ title: "Response", actions: canEdit ? button(chosen ? "Change" : "Record a response", { kind: "btn-sm", onclick: () => setResponse({ risk, care, onDone: ctx.reload }) }) : null },
      chosen ? h("div", {}, h("div", { class: "cell-main" }, `${chosen[1]}: ${chosen[2].toLowerCase()}`), h("p", { class: "prose muted" }, care.response_rationale))
        : h("p", { class: "muted" }, "No response has been recorded. Reduce it, accept it, transfer it, or avoid it, and say why.")),
    h("div", { class: "row" }, h("h2", { class: "grow section-title" }, "Treatment plans"),
      canEdit ? button("Open a plan", { kind: "btn-sm", iconName: "plus", onclick: () => openPlan({ risk, program: ctx.program, onDone: ctx.reload }) }) : null),
    care.plans.length ? care.plans.map((plan) => planCard(plan, context))
      : card({}, h("p", { class: "muted" }, "No plan yet. A plan has an objective, an owner, a date, and the actions that will get there.")),
    h("div", { class: "row" }, h("h2", { class: "grow section-title" }, "Acceptance"),
      care.authority.allowed ? button("Accept this risk", { kind: "btn-sm btn-primary", onclick: () => acceptRisk({ risk, care, program: ctx.program, onDone: ctx.reload }) }) : null),
    above && !care.authority.allowed && care.authority.reason ? h("p", { class: "subtle" }, care.authority.reason) : null,
    care.acceptances.length ? care.acceptances.map((acceptance) => acceptanceCard(acceptance, context))
      : card({}, h("p", { class: "muted" }, above
        ? "Nobody has accepted this risk. Acceptance is a named decision by a leader with the authority for its rating, for a limited time, and never by its own owner."
        : "This risk is not above appetite, so there is nothing to accept.")));
}
