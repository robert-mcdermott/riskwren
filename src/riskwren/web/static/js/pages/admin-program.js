// Admin → Program: how risks are rated here, edited where it is used. Anything that can
// move a risk (the matrix, appetite, the cadences) is previewed before it is published.

import { get, patch, post, put } from "../core/api.js";
import { button, h, iconButton } from "../core/dom.js";
import { date, plural, titleCase } from "../core/format.js";
import { program as loadProgram, units } from "../core/lookups.js";
import { query } from "../core/router.js";
import { can } from "../core/session.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { matrixGrid } from "../components/matrix.js";
import { closeOverlay, openOverlay } from "../components/overlay.js";
import { peoplePicker } from "../components/people-picker.js";
import { rating, STANDING } from "../components/risk.js";
import { toast } from "../components/toast.js";
import { alert, card, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { tabBar } from "./record.js";

const TABS = [["categories", "Categories and appetite"], ["method", "Scales and matrix"], ["cadences", "Cadences"],
  ["vocabularies", "Vocabularies"], ["fields", "Fields"], ["visibility", "Who sees what"]];
const said = (error) => Object.values(error.fields ?? {}).join(" ") || error.detail || "That could not be saved.";
const copy = (value) => JSON.parse(JSON.stringify(value));
const same = (one, other) => JSON.stringify(one) === JSON.stringify(other);

/** The method as it is published: without what the app adds to show it. */
function bare(method) {
  const { version, published_at: at, ...rest } = copy(method);
  rest.ratings = rest.ratings.map(({ ramp_level: level, ...item }) => item);
  return rest;
}

// --- The preview every change that can move a risk goes through -------------------------------

function shown(program, change, value) {
  if (value == null) return "none";
  if (change.field.endsWith("_rating")) return program.method.ratings.find((item) => item.key === value)?.label ?? value;
  if (change.field === "standing") return STANDING[value]?.[0] ?? value;
  return date(value);
}

/** Show which risks a change would move, and publish it only from there. */
async function review(program, changes, { unitIndex, onDone }) {
  let found;
  try {
    found = (await post("/api/v1/program/preview", changes)).data;
  } catch (error) {
    toast(said(error));
    return;
  }
  // A changed method renames ratings from the moment it is published.
  const after = changes.method ? { method: { ratings: changes.method.ratings } } : program;
  openOverlay({
    title: "Before you publish",
    subtitle: found.changed.length ? `This changes the ${found.changed.join(", the ")}.` : "Nothing here differs from what is in force.",
    render: (body, footer, close) => {
      const count = found.risks.length;
      const { rating: rated, standing, review: reviewed } = found.counts;
      const publish = button(count ? `Publish, and change ${plural(count, "risk")}` : "Publish", { kind: "btn-primary" });
      publish.addEventListener("click", async () => {
        publish.disabled = true;
        try {
          const done = (await post("/api/v1/program/publish", changes)).data;
          close();
          toast(done.risks.length ? `Published. ${plural(done.risks.length, "risk")} changed.` : "Published. No risk changed.");
          onDone();
        } catch (error) {
          toast(said(error));
          publish.disabled = false;
        }
      });
      body.append(h("div", { class: "stack" },
        count
          ? alert("warn", h("div", {}, h("strong", {}, `${plural(count, "open risk")} would change. `),
            [rated ? `${rated} in rating` : null, standing ? `${standing} in standing` : null, reviewed ? `${reviewed} in when it is next reviewed` : null].filter(Boolean).join(", "),
            ". Judgments already made keep the rating they were given; what each risk shows is read again from what is in force."))
          : alert("info", "No open risk would change its rating, its standing, or when it is next reviewed."),
        found.counts.documents ? alert("info", `${plural(found.counts.documents, "document")} that follow the program's review cadence would have their next review moved.`) : null,
        count ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Risk"), h("th", { scope: "col" }, "What would change"))),
          h("tbody", {}, found.risks.map((risk) => h("tr", {},
            h("td", {}, h("a", { class: "cell-main", href: `/risks/${risk.ref}`, target: "_blank", rel: "noopener" }, risk.name),
              h("div", { class: "cell-sub" }, [risk.ref, unitIndex.byId.get(risk.org_unit_id)?.name].filter(Boolean).join(" · "))),
            h("td", {}, h("ul", { class: "plain-list" }, risk.changes.map((change) => h("li", {},
              `${change.label}: `, h("del", {}, shown(program, change, change.before)), h("span", { "aria-hidden": "true" }, " → "),
              h("span", { class: "sr-only" }, " becomes "), h("ins", {}, shown(after, change, change.after))))))))))) : null));
      footer.replaceChildren(h("div", { class: "row" }, found.changed.length ? publish : null, button(found.changed.length ? "Cancel" : "Close", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** The bar that says something is not yet published. */
function pending(count, what, { onReview, onDiscard }) {
  if (!count) return null;
  return h("div", { class: "draft-bar", role: "status" },
    h("span", { class: "grow" }, h("strong", {}, `${plural(count, what)} not published. `), "Nothing changes until you publish."),
    button("Discard", { kind: "btn-ghost", onclick: onDiscard }),
    button("Preview and publish", { kind: "btn-primary", onclick: onReview }));
}

// --- Categories and appetite ----------------------------------------------------------------------

function editCategory(program, category, top, reload) {
  openOverlay({
    title: category ? category.name : "Add a risk category",
    subtitle: category ? "Its risks keep it whatever it is called. A retired category is not offered to new risks." : "A kind of risk, with how much of it the organization is content to live with.",
    render: (body, footer, close) => {
      const name = field("Name", { value: category?.name ?? "", required: true, maxlength: 120 });
      const description = field("What it covers", { type: "textarea", value: category?.description ?? "" });
      const parent = category ? null : select("Under", [["", "The top of the tree"], ...program.categories.map((item) => [item.key, item.name])]);
      const appetite = category ? null : select("Appetite", [["", "The same as above"], ...program.method.ratings.map((item) => [item.key, item.label])],
        { hint: "The highest residual rating that needs no decision. A category at the top needs its own." });
      const retired = category ? checkbox("Retired", { checked: category.status === "retired", hint: "Risks already in it keep it." }) : null;
      const problem = banner();
      const save = button(category ? "Save" : "Add", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, fields: { name, description, ...(parent ? { parent, appetite } : {}) }, banner: problem,
          run: () => (category
            ? patch(`/api/v1/risk-categories/${category.key}`, { name: name.input.value, description: description.input.value, status: retired.input.checked ? "retired" : "active" })
            : post("/api/v1/risk-categories", { name: name.input.value, description: description.input.value, parent: parent.input.value || null, appetite: appetite.input.value || null })) });
        if (!done) return;
        close();
        toast(category ? "Saved." : "Added.");
        reload();
      });
      body.append(h("div", { class: "stack-lg" }, problem, name.node, description.node, parent?.node ?? null, appetite?.node ?? null, retired?.node ?? null));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function categoriesTab(program, ctx) {
  const draft = new Map();
  const holder = h("div", { class: "stack-lg" });
  const inForce = (category, above) => (draft.has(category.key) ? draft.get(category.key) : category.appetite) ?? above;
  const move = async (category, direction) => {
    try {
      await patch(`/api/v1/risk-categories/${category.key}`, { move: direction });
      ctx.reload();
    } catch (error) {
      toast(said(error));
    }
  };
  const draw = () => {
    const row = (category, top, above, at, count) => {
      const chosen = draft.has(category.key) ? draft.get(category.key) : category.appetite;
      const pick = h("select", { class: "select", "aria-label": `Appetite for ${category.name}` },
        [...(top ? [] : [["", "The same as above"]]), ...program.method.ratings.map((item) => [item.key, item.label])]
          .map(([key, text]) => h("option", { value: key, selected: key === (chosen ?? "") }, text)));
      pick.addEventListener("change", () => {
        const value = pick.value || null;
        if (value === (category.appetite ?? null)) draft.delete(category.key);
        else draft.set(category.key, value);
        draw();
      });
      return h("tr", {},
        h("td", {}, h("div", { class: top ? "cell-main" : "indent" }, category.name,
          category.status === "retired" ? [" ", pill("Retired")] : null, draft.has(category.key) ? [" ", pill("Changed", "warn")] : null),
        category.description ? h("div", { class: top ? "cell-sub" : "cell-sub indent" }, category.description) : null),
        h("td", {}, pick),
        h("td", {}, rating(program, inForce(category, above))),
        h("td", { class: "nowrap" },
          iconButton("chevron-up", `Move ${category.name} up`, { disabled: at === 0, onclick: () => move(category, "up") }),
          iconButton("chevron-down", `Move ${category.name} down`, { disabled: at === count - 1, onclick: () => move(category, "down") }),
          button("Edit", { kind: "btn-sm btn-ghost", "aria-label": `Edit ${category.name}`, onclick: () => editCategory(program, category, top, ctx.reload) })));
    };
    holder.replaceChildren(
      pending(draft.size, "appetite change", {
        onDiscard: () => {
          draft.clear();
          draw();
        },
        onReview: () => review(program, { appetites: Object.fromEntries(draft) }, ctx),
      }),
      card({ title: "Risk categories and appetite", flush: true,
        actions: button("Add a category", { iconName: "plus", onclick: () => editCategory(program, null, true, ctx.reload) }) },
      h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Category"), h("th", { scope: "col" }, "Appetite"), h("th", { scope: "col" }, "In force"),
          h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Order and edit")))),
        h("tbody", {}, program.categories.flatMap((top, at) => [row(top, true, null, at, program.categories.length),
          ...top.children.map((child, index) => row(child, false, inForce(top, null), index, top.children.length))])))),
      h("p", { class: "card-note muted" }, "Appetite is the highest residual rating that needs no decision. A risk above it must be treated or formally accepted. Changing it can change the standing of risks, so it is previewed first.")));
  };
  draw();
  return holder;
}

// --- Scales and matrix -----------------------------------------------------------------------------

function textCell(value, labelText, onChange, { area = false } = {}) {
  const node = area ? h("textarea", { class: "textarea", rows: 2, "aria-label": labelText }, value ?? "")
    : h("input", { class: "input", type: "text", value: value ?? "", "aria-label": labelText });
  node.addEventListener("input", () => onChange(node.value));
  return node;
}

function methodTab(program, ctx) {
  const original = bare(program.method);
  let draft = copy(original);
  const holder = h("div", { class: "stack-lg" });
  const bar = h("div", {});
  const refreshBar = () => bar.replaceChildren(...[pending(same(draft, original) ? 0 : 1, "change to the scoring method", {
    onDiscard: () => {
      draft = copy(original);
      draw();
    },
    onReview: () => review(program, { method: draft }, ctx),
  })].filter(Boolean));
  const set = (change) => {
    change();
    refreshBar();
  };
  const draw = () => {
    const ramp = Object.fromEntries(program.method.ratings.map((item) => [item.key, item.ramp_level]));
    const drafted = { method: { ...draft, ratings: draft.ratings.map((item) => ({ ...item, ramp_level: ramp[item.key] })) } };
    const grid = matrixGrid(drafted, { caption: "The rating for each likelihood and impact. Each cell can be changed.",
      cell: (likelihood, impact, rated) => {
        const pick = h("select", { class: "select matrix-pick", "aria-label": `Rating for likelihood ${likelihood}, impact ${impact}` },
          draft.ratings.map((item) => h("option", { value: item.key, selected: item.key === rated.key }, item.label)));
        pick.addEventListener("change", () => {
          draft.matrix[impact - 1][likelihood - 1] = pick.value;
          draw();
        });
        return pick;
      } });
    const levels = (title, rows, withDefinition) => card({ title, flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Level"), h("th", { scope: "col" }, "Name"), withDefinition ? h("th", { scope: "col" }, "What it means") : null)),
      h("tbody", {}, rows.map((level) => h("tr", {}, h("th", { scope: "row", class: "numeric" }, String(level.level ?? "")),
        h("td", {}, textCell(level.label, `Name of ${title.toLowerCase()} level ${level.level}`, (value) => set(() => { level.label = value; }))),
        withDefinition ? h("td", {}, textCell(level.definition, `Meaning of ${title.toLowerCase()} level ${level.level}`, (value) => set(() => { level.definition = value; }))) : null))))));
    const ratings = card({ title: "Ratings", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Rating"), h("th", { scope: "col" }, "Name"), h("th", { scope: "col" }, "What it means"))),
      h("tbody", {}, draft.ratings.map((item) => h("tr", {}, h("th", { scope: "row" }, rating(program, item.key)),
        h("td", {}, textCell(item.label, `Name of the ${item.key} rating`, (value) => set(() => { item.label = value; }))),
        h("td", {}, textCell(item.description, `Meaning of the ${item.key} rating`, (value) => set(() => { item.description = value; }))))))),
    h("p", { class: "card-note muted" }, "A rating can be renamed. Ratings are added or removed with a program pack, because appetite, acceptances, and people's limits all name them.")));
    const dimensions = card({ title: "Impact, by dimension" }, h("div", { class: "stack" },
      h("p", { class: "muted" }, "The overall impact of a risk is the highest level rated on any dimension."),
      draft.dimensions.map((dimension) => h("details", { class: "fold" },
        h("summary", {}, dimension.label),
        h("div", { class: "stack" },
          h("div", { class: "grid-2" },
            h("div", { class: "field" }, h("div", { class: "label" }, "Name"), textCell(dimension.label, `Name of the ${dimension.key} dimension`, (value) => set(() => { dimension.label = value; }))),
            h("div", { class: "field" }, h("div", { class: "label" }, "The question it asks"), textCell(dimension.question, `Question of the ${dimension.key} dimension`, (value) => set(() => { dimension.question = value; })))),
          draft.impact_levels.map((level) => h("div", { class: "field" }, h("div", { class: "label" }, `${level.level} ${level.label}`),
            textCell(dimension.levels[String(level.level)], `${dimension.label} at level ${level.level}`, (value) => set(() => { dimension.levels[String(level.level)] = value; }), { area: true }))))))));
    holder.replaceChildren(bar,
      card({ title: `The matrix (scoring method version ${program.method.version})` }, grid,
        h("p", { class: "subtle" }, "Impact up the side, likelihood along the bottom. A rating may not fall as likelihood or impact rises. Publishing a change makes a new version: every open risk is read again from it, and each judgment keeps the rating it was given.")),
      ratings, levels("Likelihood", draft.likelihood, true), levels("Impact", draft.impact_levels, false), dimensions);
    refreshBar();
  };
  draw();
  return holder;
}

// --- Cadences ------------------------------------------------------------------------------------------

function cadencesTab(program, ctx, vocab) {
  const original = program.cadences;
  const draft = copy(original);
  const bar = h("div", {});
  const refreshBar = () => bar.replaceChildren(...[pending(same(draft, original) ? 0 : 1, "change to the cadences", {
    onDiscard: ctx.reload,
    onReview: () => review(program, { cadences: draft }, ctx),
  })].filter(Boolean));
  const number = (labelText, read, write, unit, hint = null) => {
    const item = field(labelText, { type: "number", min: 0, max: 1825, value: read(), hint, inputmode: "numeric" });
    item.input.classList.add("short");
    item.input.addEventListener("input", () => {
      write(item.input.value === "" ? null : Number(item.input.value));
      refreshBar();
    });
    item.node.append(h("span", { class: "unit" }, unit));
    return item.node;
  };
  const severities = vocab.issue_severities;
  return h("div", { class: "stack-lg" }, bar,
    card({ title: "How often a risk is reviewed" }, h("div", { class: "stack" },
      h("p", { class: "muted" }, "From the day it was last assessed, by its residual rating. A higher rating is never reviewed less often. Changing these moves review dates, so it is previewed first."),
      h("div", { class: "grid-3" }, [...program.method.ratings].reverse().map((item) =>
        number(item.label, () => draft.risk_review_months[item.key], (value) => { draft.risk_review_months[item.key] = value; }, "months")),
      number("Not yet rated", () => draft.unrated_risk_review_months, (value) => { draft.unrated_risk_review_months = value; }, "months", "From the day it was raised.")))),
    card({ title: "Controls, tests, and exceptions" }, h("div", { class: "grid-3" },
      number("A control's rating stands for", () => draft.control_rating_months, (value) => { draft.control_rating_months = value; }, "months", "After that it is stale, and counts for nothing."),
      number("A key control is tested every", () => draft.key_control_test_months, (value) => { draft.key_control_test_months = value; }, "months"),
      number("An exception may run for", () => draft.exception_max_months, (value) => { draft.exception_max_months = value; }, "months"),
      number("A document is reviewed every", () => draft.document_review_months, (value) => { draft.document_review_months = value; }, "months",
        "A document may set its own. Changing this moves the next review of those that do not."),
      number("A continuity plan is exercised every", () => draft.plan_exercise_months, (value) => { draft.plan_exercise_months = value; }, "months"))),
    card({ title: "How long an issue is given" }, h("div", { class: "stack" },
      h("p", { class: "muted" }, "From the day it is raised, by its severity. A more severe issue is never given longer. Issues already raised keep the date they were given."),
      h("div", { class: "grid-3" }, severities.map((item) =>
        number(item.label, () => draft.issue_due_days[item.key], (value) => { draft.issue_due_days[item.key] = value; }, "days"))))),
    card({ title: "Reminders" }, h("div", { class: "grid-3" },
      number("Remind this long before", () => draft.reminders.soon_days, (value) => { draft.reminders.soon_days = value; }, "days"),
      number("Tell the steward when late by", () => draft.reminders.steward_after_days, (value) => { draft.reminders.steward_after_days = value; }, "days"),
      number("Tell the leader when late by", () => draft.reminders.leader_after_days, (value) => { draft.reminders.leader_after_days = value; }, "days"))));
}

// --- Fields of the organization's own ------------------------------------------------------------------

const FIELD_TYPES = [["system", "Systems"], ["process", "Processes"], ["third_party", "Third parties"], ["service", "Services"],
  ["information", "Information assets"], ["site", "Sites"], ["risk", "Risks"], ["control", "Controls"]];

function fieldsTab(data, reload) {
  const holder = h("div", { class: "stack-lg" });
  let kind = FIELD_TYPES.some(([key]) => key === query().get("kind")) ? query().get("kind") : "system";
  const draw = () => {
    let items = copy(data.fields[kind] ?? []);
    const pick = h("select", { class: "select", id: "field-kind" }, FIELD_TYPES.map(([key, label]) => h("option", { value: key, selected: key === kind }, label)));
    pick.addEventListener("change", () => {
      kind = pick.value;
      draw();
    });
    const body = h("tbody", {});
    const problem = banner();
    const rows = () => body.replaceChildren(...(items.length ? items.map((item, at) => h("tr", {},
      h("td", {}, textCell(item.label, `Label of ${item.key}`, (value) => { item.label = value; })),
      h("td", { class: "ref" }, item.key),
      h("td", {}, item.kind === "choice"
        ? textCell((item.choices ?? []).join(", "), `Choices for ${item.label}, separated by commas`, (value) => {
          item.choices = value.split(",").map((each) => each.trim()).filter(Boolean);
        })
        : h("span", { class: "subtle" }, data.kinds.find((each) => each.key === item.kind)?.label ?? item.kind)),
      h("td", {}, textCell(item.help ?? "", `Help for ${item.label}`, (value) => { item.help = value; })),
      h("td", {}, h("label", { class: "check" }, h("input", { type: "checkbox", checked: Boolean(item.required), disabled: !data.can_change,
        onchange: (event) => { item.required = event.target.checked; } }), h("span", {}, "Needed"))),
      h("td", { class: "nowrap" },
        iconButton("chevron-up", `Move ${item.label} up`, { disabled: at === 0 || !data.can_change, onclick: () => {
          [items[at - 1], items[at]] = [items[at], items[at - 1]];
          rows();
        } }),
        iconButton("chevron-down", `Move ${item.label} down`, { disabled: at === items.length - 1 || !data.can_change, onclick: () => {
          [items[at + 1], items[at]] = [items[at], items[at + 1]];
          rows();
        } }),
        iconButton("trash", `Take away ${item.label}`, { disabled: !data.can_change, onclick: () => {
          items = items.filter((_, index) => index !== at);
          rows();
        } }))))
      : [h("tr", {}, h("td", { colspan: 6, class: "subtle" }, "None yet."))]));
    rows();
    const label = field("A new field", { hint: "Its key is made from its label and never changes after.", maxlength: 60 });
    const newKind = select("Kind", data.kinds.map((each) => [each.key, each.label]), { value: "text" });
    const add = button("Add", { onclick: () => {
      const named = label.input.value.trim();
      const key = named.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);
      if (!key || !/^[a-z]/.test(key)) return label.setError("Give it a label that starts with a letter.");
      if (items.some((item) => item.key === key)) return label.setError("There is already a field with that key.");
      label.setError(null);
      items.push({ key, label: named, kind: newKind.input.value, ...(newKind.input.value === "choice" ? { choices: ["Yes", "No"] } : {}) });
      label.input.value = "";
      return rows();
    } });
    const save = button("Save these fields", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/program/fields/${kind}`, { fields: items }) });
      if (!done) return;
      toast("Saved.");
      reload();
    });
    holder.replaceChildren(
      h("p", { class: "muted" }, "What your organization also records about a kind of record, such as a cost center on a system or a contract owner on a third party. Each field is a line of text, a number, a date, or one of a list, and is shown and asked for with the record. A field taken away keeps its values, unshown, until it is brought back."),
      h("div", { class: "field" }, h("label", { class: "label", for: "field-kind" }, "Kind of record"), pick),
      card({ title: FIELD_TYPES.find(([key]) => key === kind)[1], flush: true },
        h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Label"), h("th", { scope: "col" }, "Key"), h("th", { scope: "col" }, "Kind or choices"),
            h("th", { scope: "col" }, "Help"), h("th", { scope: "col" }, "Needed"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Order")))),
          body)),
        data.can_change ? h("div", { class: "card-pad stack" }, problem, h("div", { class: "row wrap" }, label.node, newKind.node, add), h("div", { class: "form-actions" }, save)) : null));
  };
  draw();
  return holder;
}

// --- Vocabularies ----------------------------------------------------------------------------------------

function vocabulariesTab(lists, reload) {
  const holder = h("div", { class: "stack-lg" });
  let name = query().get("list") && lists.some((each) => each.name === query().get("list")) ? query().get("list") : lists[0].name;
  const draw = () => {
    const list = lists.find((each) => each.name === name);
    let items = copy(list.items);
    const described = items.some((item) => "description" in item);
    const pick = h("select", { class: "select", id: "vocabulary" }, lists.map((each) => h("option", { value: each.name, selected: each.name === name }, titleCase(each.name))));
    pick.addEventListener("change", () => {
      name = pick.value;
      draw();
    });
    const body = h("tbody", {});
    const problem = banner();
    const rows = () => body.replaceChildren(...items.map((item, at) => h("tr", {},
      h("td", {}, textCell(item.label, `Name of ${item.key}`, (value) => { item.label = value; })),
      described ? h("td", {}, textCell(item.description, `Meaning of ${item.label}`, (value) => { item.description = value; })) : null,
      h("td", { class: "ref" }, item.key),
      h("td", {}, list.labels_only || list.kept.includes(item.key) ? h("span", { class: "subtle" }, list.labels_only ? "" : "Always offered")
        : h("label", { class: "check" }, h("input", { type: "checkbox", checked: Boolean(item.retired), onchange: (event) => { item.retired = event.target.checked; } }), h("span", {}, "Retired"))),
      h("td", { class: "nowrap" },
        iconButton("chevron-up", `Move ${item.label} up`, { disabled: at === 0, onclick: () => {
          [items[at - 1], items[at]] = [items[at], items[at - 1]];
          rows();
        } }),
        iconButton("chevron-down", `Move ${item.label} down`, { disabled: at === items.length - 1, onclick: () => {
          [items[at + 1], items[at]] = [items[at], items[at + 1]];
          rows();
        } })))));
    rows();
    const added = field("A new value", { hint: "Its key is made from its name and never changes after.", maxlength: 60 });
    const add = button("Add", { onclick: () => {
      const label = added.input.value.trim();
      const key = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);
      if (!key || !/^[a-z]/.test(key)) return added.setError("Give it a name that starts with a letter.");
      if (items.some((item) => item.key === key)) return added.setError("There is already a value with that key.");
      added.setError(null);
      items.push({ key, label, ...(described ? { description: "" } : {}) });
      added.input.value = "";
      return rows();
    } });
    const save = button("Save this list", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, run: () => put(`/api/v1/vocabularies/${name}`, { items }) });
      if (!done) return;
      toast("Saved.");
      reload();
    });
    holder.replaceChildren(
      h("div", { class: "field" }, h("label", { class: "label", for: "vocabulary" }, "List"), pick),
      card({ title: titleCase(name), flush: true },
        h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Name"), described ? h("th", { scope: "col" }, "What it means") : null, h("th", { scope: "col" }, "Key"),
            h("th", { scope: "col" }, "In use"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Order")))),
          body)),
        h("div", { class: "card-pad stack" }, problem,
          list.labels_only ? h("p", { class: "muted" }, "The software gives each of these a meaning of its own, so their names and order can be changed here and nothing more. Values are added or taken away with a program pack.")
            : h("div", { class: "row add-row" }, added.node, add),
          h("p", { class: "subtle" }, "Records store a value's key, never its name, so renaming a value rewrites nothing. A value in use is retired, not removed: records keep it, and new ones cannot choose it."),
          h("div", {}, save))));
  };
  draw();
  return holder;
}

// --- Who sees what ----------------------------------------------------------------------------------------

function visibilityTab(seen) {
  const node = h("select", { class: "select", id: "register-visibility" },
    Object.entries(seen.choices).map(([key, text]) => h("option", { value: key, selected: key === seen.visibility }, text)));
  let current = seen.visibility;
  node.addEventListener("change", async () => {
    try {
      await put("/api/v1/admin/visibility", { visibility: node.value });
      current = node.value;
      toast("Saved.");
    } catch (error) {
      toast(said(error));
      node.value = current;
    }
  });
  return card({ title: "Who sees the register" },
    h("div", { class: "stack-sm" },
      h("label", { class: "label", for: "register-visibility" }, "What a person with no role sees"),
      node,
      h("p", { class: "subtle" }, "Leaders and stewards always see their unit and everything beneath it; managers, auditors, and assessors see what their role covers. A record marked restricted is seen only by whoever made it, its owners, its unit's steward and leaders, managers, auditors, and administrators. The inventory (processes, systems, third parties, services, information, and sites) is open to everyone signed in.")));
}

function readersTab(seen) {
  let reach = seen.reach;
  let people = seen.people.map((person) => ({ ...person }));
  const node = h("select", { class: "select", id: "leadership-reach" },
    Object.entries(seen.choices).map(([key, text]) => h("option", { value: key, selected: key === reach }, text)));
  const list = h("ul", { class: "plain-list stack-sm", "aria-label": "People named as readers" });
  const save = async (next) => {
    try {
      const saved = (await put("/api/v1/admin/leadership-readers", { reach: next.reach, people: next.people.map((person) => person.account_id) })).data;
      reach = saved.reach;
      people = saved.people;
      toast("Saved. It applies from each person's next page.");
    } catch (error) {
      toast(said(error));
    }
    node.value = reach;
    draw();
  };
  const draw = () => list.replaceChildren(...(people.length ? people.map((person) => h("li", { class: "row" },
    h("span", { class: "grow" }, h("span", { class: "cell-main" }, person.name), h("span", { class: "cell-sub" }, ` ${person.email}`)),
    button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Stop ${person.name} reading the reports`,
      onclick: () => save({ reach, people: people.filter((other) => other.account_id !== person.account_id) }) })))
    : [h("li", { class: "subtle" }, "Nobody is named.")]));
  node.addEventListener("change", () => save({ reach: node.value, people }));
  const picker = peoplePicker({ label: "Name someone who reads them", exclude: (account) => people.some((person) => person.account_id === account.id),
    onPick: (account) => save({ reach, people: [...people, { account_id: account.id, name: account.display_name, email: account.email }] }) });
  draw();
  return card({ title: "Who reads the leadership reports" },
    h("div", { class: "stack-sm" },
      h("p", { class: "subtle" }, "Managers for the whole organization, administrators, auditors, and those who lead the whole organization always read them. Choose how much further they reach: in a smaller organization the security leader, or those who run the program, may be the most senior people who use it."),
      h("label", { class: "label", for: "leadership-reach" }, "Who else reads them"),
      node,
      h("h3", {}, "Named readers"),
      h("p", { class: "subtle" }, "Anyone named here reads them whatever the choice above."),
      list, picker,
      h("p", { class: "subtle" }, "A reader who may not see a record a report names sees where it stands, but not what it is.")));
}

function anonymousTab(setting, reload) {
  const open = setting.open;
  const flip = can("admin") ? button(open ? "Close it" : "Open it", { kind: open ? "" : "btn-primary", onclick: async () => {
    try {
      await put("/api/v1/admin/anonymous-reporting", { open: !open });
      toast(open ? "Reporting without a name is closed." : "Reporting without a name is open.");
      reload();
    } catch (error) {
      toast(said(error));
    }
  } }) : null;
  return card({ title: "Reporting without a name", actions: pill(open ? "Open" : "Closed", open ? "ok" : "") },
    h("div", { class: "stack-sm" },
      h("p", {}, open ? h("span", {}, "Anyone may report a concern at ", h("a", { href: "/report" }, "/report"), " without signing in. The sign-in page offers it.")
        : "Closed: everyone reports signed in. An administrator opens it."),
      h("p", { class: "subtle" }, `When it is open, nothing about who sends a report is kept: no account, no name, and no address. The reporter is shown a code once, and follows the report up with it. Failed codes are not counted against the address they came from, and at most ${setting.most_an_hour} reports are taken in an hour, from everyone together. Whether the web server's own log keeps addresses is set where it runs.`),
      flip ? h("div", {}, flip) : null));
}

function rules(program) {
  const months = (count) => (count == null ? "" : plural(count, "month"));
  return card({ title: "What follows from a rating", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Residual rating"), h("th", { scope: "col" }, "What it means"),
      h("th", { scope: "col" }, "Reviewed every"), h("th", { scope: "col" }, "If above appetite, may be accepted"))),
    h("tbody", {}, program.method.ratings.map((item) => {
      const rule = program.authority.acceptance[item.key];
      return h("tr", {}, h("td", {}, rating(program, item.key)), h("td", {}, item.description),
        h("td", {}, months(program.cadences.risk_review_months[item.key])),
        h("td", {}, rule ? `For up to ${months(rule.max_months)}, by a leader${rule.needs_limit ? ` whose limit reaches ${item.label}` : " of the unit or above"}` : "No acceptance is needed"));
    })))));
}

export function adminProgram(main) {
  const tab = TABS.some(([key]) => key === query().get("tab")) ? query().get("tab") : "categories";
  return show(main, {
    title: "Program",
    load: async () => {
      const [program, unitIndex, extra] = await Promise.all([loadProgram({ fresh: true }), units(),
        tab === "vocabularies" ? get("/api/v1/admin/vocabularies", undefined, { fresh: true })
          : tab === "fields" ? get("/api/v1/program/fields", undefined, { fresh: true })
          : tab === "visibility" ? Promise.all(["visibility", "leadership-readers", "anonymous-reporting"].map((name) => get(`/api/v1/admin/${name}`, undefined, { fresh: true })))
            .then(([seen, readers, anonymous]) => ({ data: { seen: seen.data, readers: readers.data, anonymous: anonymous.data } }))
            : tab === "cadences" ? get("/api/v1/vocabularies", undefined, { fresh: true }) : null]);
      return { program, unitIndex, extra: extra?.data };
    },
    view: (data, reload) => {
      closeOverlay();
      const ctx = { unitIndex: data.unitIndex, reload, onDone: reload };
      const body = tab === "method" ? methodTab(data.program, ctx)
        : tab === "cadences" ? cadencesTab(data.program, ctx, data.extra)
          : tab === "vocabularies" ? vocabulariesTab(data.extra, reload)
            : tab === "fields" ? fieldsTab(data.extra, reload)
            : tab === "visibility" ? [visibilityTab(data.extra.seen), readersTab(data.extra.readers), anonymousTab(data.extra.anonymous, reload)]
              : [categoriesTab(data.program, ctx), rules(data.program)];
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "Program",
          lede: "How risks are rated here, and the lists records choose from. What can move a risk is previewed before it is published: you see every risk that would change, and nothing changes until you say so." }),
        tabBar(TABS, tab), body,
        tab === "categories" || tab === "method" || tab === "cadences"
          ? alert("info", h("div", {}, "Who may accept what, and the number of levels and ratings, are changed with a program pack: ",
            h("code", {}, "riskwren program export"), " writes the one in force, and ", h("code", {}, "riskwren program import"), " loads an edited one.")) : null);
    },
  });
}
