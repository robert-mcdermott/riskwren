// Reporting without a name: a page that needs no sign-in, open only where an administrator
// has opened it. Nothing about who sends a report is kept. The reporter is shown a code once,
// which is never put in the address, and with it they follow the report up.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime } from "../core/format.js";
import { KIND, reportFields } from "../components/incident-report.js";
import { banner, field, submit } from "../components/form.js";
import { brand } from "../components/shell.js";
import { alert, card, pill } from "../components/ui.js";
import { setTitle } from "./page.js";

const STATUS = { reported: ["Received, waiting to be looked at", "warn"], handling: ["Being handled", "info"], closed: ["Closed", ""] };

function frame(meta, ...children) {
  return h("div", { class: "respond" },
    h("header", { class: "respond-top" }, h("div", { class: "sign-in-brand" }, brand(meta))),
    h("main", { class: "respond-main", id: "main" }, children));
}

function tabs(current, go) {
  return h("div", { class: "tabs", role: "tablist" }, [["report", "Report something"], ["follow", "Follow up a report"]].map(([key, text]) =>
    h("button", { type: "button", class: "tab", role: "tab", "aria-selected": String(current === key), onclick: () => go(key) }, text)));
}

function reportView(draw) {
  const form = reportFields();
  form.fields.kind.input.value = "concern";
  const problem = banner();
  const send = button("Send the report", { kind: "btn-primary" });
  send.addEventListener("click", async () => {
    const done = await submit({ button: send, banner: problem, fields: form.fields, run: () => post("/api/v1/anonymous-reports", form.values()) });
    if (done) draw("sent", { code: done.data.code });
  });
  return [
    h("h1", { tabindex: "-1" }, "Report something without your name"),
    alert("info", h("strong", {}, "Nothing about who you are is kept: "), "no account, no name, and no address. Leave out of the report anything that would name you, unless you want to be known."),
    card({}, h("div", { class: "stack" }, problem, ...form.nodes, h("div", { class: "respond-actions" }, send))),
  ];
}

function sentView(code, draw) {
  return [
    h("h1", { tabindex: "-1" }, "Your report is in"),
    h("p", {}, "Those who triage reports have been told. To see where it stands, read what they say to you, or add to it, come back with this code:"),
    h("div", { class: "follow-code", "aria-label": "Your follow-up code" }, code),
    alert("warn", h("strong", {}, "Write it down or keep it somewhere safe now. "), "It is the only way back to your report, and it is not shown again. Nobody here can look it up for you."),
    h("div", { class: "respond-actions" }, button("Follow it up now", { kind: "btn-primary", onclick: () => draw("report-status", { code }) })),
  ];
}

function followView(draw) {
  const code = field("Your follow-up code", { autocomplete: "off", spellcheck: "false", hint: "Four groups of five letters and numbers. Capitals and dashes do not matter." });
  const problem = banner();
  const go = button("Open my report", { kind: "btn-primary" });
  go.addEventListener("click", async () => {
    const done = await submit({ button: go, banner: problem, fields: { code }, run: () => post("/api/v1/anonymous-reports/follow-up", { code: code.input.value }) });
    if (done) draw("report-status", { code: code.input.value, data: done.data });
  });
  return [h("h1", { tabindex: "-1" }, "Follow up a report"), card({}, h("div", { class: "stack" }, problem, code.node, h("div", {}, go)))];
}

function statusView(code, data, draw) {
  const [text, tone] = STATUS[data.status] ?? [data.status, ""];
  const said = data.messages.length ? h("ol", { class: "plain-list stack messages" }, data.messages.map((message) => h("li", {},
    h("div", { class: "row wrap" }, h("span", { class: "cell-main" }, message.by), h("span", { class: "subtle" }, dateTime(message.at))),
    h("p", { class: "prose" }, message.body))))
    : h("p", { class: "muted" }, "Nothing has been said to you yet.");
  let more = null;
  if (data.can_write) {
    const text_ = field("Add something", { type: "textarea", rows: 3, maxlength: 10000, hint: "It goes to those handling your report." });
    const problem = banner();
    const send = button("Send", { kind: "btn-primary" });
    send.addEventListener("click", async () => {
      const done = await submit({ button: send, banner: problem, fields: { body: text_ }, run: () => post("/api/v1/anonymous-reports/messages", { code, body: text_.input.value }) });
      if (done) draw("report-status", { code, data: done.data });
    });
    more = h("div", { class: "stack" }, problem, text_.node, h("div", {}, send));
  }
  return [
    h("h1", { tabindex: "-1" }, data.name),
    h("div", { class: "row wrap" }, pill(KIND[data.kind]?.[0] ?? data.kind), pill(text, tone)),
    card({ title: "What you reported" }, h("div", { class: "stack" }, h("p", { class: "prose" }, data.summary),
      h("p", { class: "subtle" }, [`Reported ${date(data.reported_at)}`, data.occurred_on ? `happened ${date(data.occurred_on)}` : null, data.location].filter(Boolean).join(" · ")))),
    card({ title: "What has been said" }, h("div", { class: "stack" }, said, more,
      data.status === "closed" ? h("p", { class: "muted" }, "It is closed, so nothing more can be added.") : null)),
  ];
}

export function reportPage(root, meta) {
  setTitle("Report without your name");
  if (!meta.report_without_name) {
    root.replaceChildren(frame(meta, h("h1", {}, "Reporting without a name is not open here"),
      h("p", {}, "Sign in to report something, or speak to someone you trust."), h("p", {}, h("a", { href: "/sign-in" }, "Sign in"))));
    return;
  }
  const draw = async (view, state = {}) => {
    let body;
    if (view === "sent") body = sentView(state.code, draw);
    else if (view === "report-status") {
      let data = state.data;
      if (!data) {
        try {
          data = (await post("/api/v1/anonymous-reports/follow-up", { code: state.code })).data;
        } catch {
          draw("follow");
          return;
        }
      }
      body = [tabs("follow", draw), ...statusView(state.code, data, draw)];
    } else body = [tabs(view, draw), ...(view === "follow" ? followView(draw) : reportView(draw))];
    root.replaceChildren(frame(meta, ...body));
    root.querySelector("h1")?.focus();
  };
  draw("report");
}
