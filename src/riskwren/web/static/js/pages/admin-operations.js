// Admin → Scheduled work: what RiskWren does by itself, when each job last ran, what it did,
// when reminders go, and whether email is set up. Email is optional.

import { get, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { dateTime, plural, relative } from "../core/format.js";
import { toast } from "../components/toast.js";
import { alert, card, pageHeader, pill, stat } from "../components/ui.js";
import { show } from "./page.js";

const SECURITY = { starttls: "Encrypted, with STARTTLS", tls: "Encrypted, with TLS", none: "Not encrypted" };

function every(seconds) {
  if (seconds < 3600) return `Every ${seconds / 60 === 1 ? "minute" : `${seconds / 60} minutes`}`;
  if (seconds < 86400) return `Every ${seconds / 3600 === 1 ? "hour" : `${seconds / 3600} hours`}`;
  return `Every ${seconds / 86400 === 1 ? "day" : `${seconds / 86400} days`}`;
}

function state(job) {
  if (!job.enabled) return pill("Paused", "warn");
  if (job.running) return pill("Running", "accent");
  if (job.last_status === "failed") return pill("Failed", "danger");
  return job.last_status ? pill("Working", "ok") : pill("Not run yet");
}

const facts = (rows) => h("dl", { class: "dl" }, rows.map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]));

function jobCard(job, reload) {
  const run = button("Run now", { kind: "btn-sm", "aria-label": `Run ${job.label} now`, onclick: async () => {
    run.disabled = true;
    try {
      const done = (await post(`/api/v1/jobs/${job.key}/run`, {})).data;
      toast(`${job.label}: ${done.summary}`);
    } catch (error) {
      toast(error.detail ?? "It could not be run.");
    }
    reload();
  } });
  const pause = button(job.enabled ? "Pause" : "Resume", { kind: "btn-sm btn-ghost", "aria-label": `${job.enabled ? "Pause" : "Resume"} ${job.label}`, onclick: async () => {
    await put(`/api/v1/jobs/${job.key}`, { enabled: !job.enabled });
    toast(job.enabled ? `${job.label} is paused.` : `${job.label} will run again.`);
    reload();
  } });
  return card({ title: h("span", { class: "row-sm wrap" }, job.label, state(job)), actions: h("div", { class: "row-sm" }, pause, run) },
    h("div", { class: "stack" },
      h("p", { class: "muted" }, `${job.describes}.`),
      facts([["How often", every(job.every_seconds)],
        ["Last ran", job.last_finished_at ? `${relative(job.last_finished_at)}: ${job.last_summary ?? ""}` : "Not yet"],
        ["Next due", job.enabled && job.next_run_at ? dateTime(job.next_run_at) : "Paused"]]),
      job.runs.length ? h("details", {}, h("summary", {}, `Recent runs that did something (${job.runs.length})`),
        h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "When"), h("th", { scope: "col" }, "Result"), h("th", { scope: "col" }, "What it did"))),
          h("tbody", {}, job.runs.map((item) => h("tr", {},
            h("td", {}, dateTime(item.started_at)),
            h("td", {}, item.status === "ok" ? pill("Done", "ok") : pill("Failed", "danger")),
            h("td", {}, item.summary))))))) : null));
}

function reminders(when) {
  const days = (count) => plural(count, "day");
  return card({ title: "When reminders go" }, h("div", { class: "stack" },
    h("p", { class: "muted" }, "Actions, risk reviews, issues, evidence, acceptances, exceptions, and control tests each have a date. A reminder is a notice: read under the bell, and sent by email where that is set up."),
    facts([["Before the date", `${when.soon_days} ${days(when.soon_days)} ahead, to whoever it is waiting on`],
      ["The day after", "To the same people, as overdue. A test that is overdue also goes to the assessors"],
      ["Still late", `After ${when.steward_after_days} ${days(when.steward_after_days)}, to the steward of the unit`],
      ["Later still", `After ${when.leader_after_days} ${days(when.leader_after_days)}, to the unit's leader`]]),
    h("p", { class: "subtle" }, "Each is said once for a given date. Moving the date starts again. Actions and issues go up to the steward and the leader; the others are for their owners.")));
}

function email(data) {
  if (!data.enabled) {
    return card({ title: "Email", actions: pill("Not set up") }, h("div", { class: "stack" },
      h("p", {}, "RiskWren sends no email, and needs none. What needs each person is on their Home page and under the bell."),
      h("p", { class: "muted" }, "To send notices by email as well:"),
      h("ol", { class: "steps-list" },
        h("li", {}, "In ", h("code", {}, "riskwren.toml"), ", give the ", h("code", {}, "[mail]"), " section your mail server's host and the address email should come from."),
        h("li", {}, "If the server needs a password, put it in the environment variable that section names."),
        h("li", {}, "Set ", h("code", {}, "base_url"), " under ", h("code", {}, "[server]"), " so that messages can link back here, then restart RiskWren."))));
  }
  const result = h("div", { "aria-live": "polite" });
  const test = button("Send me a test message", { onclick: async () => {
    test.disabled = true;
    result.replaceChildren();
    try {
      const done = (await post("/api/v1/mail/test", {})).data;
      result.replaceChildren(alert("ok", icon("check"), h("div", {}, `The mail server accepted a message for ${done.sent_to}. Check that it arrives.`)));
    } catch (error) {
      result.replaceChildren(alert("danger", icon("alert"), h("div", {}, h("strong", {}, "It could not be sent. "), error.detail ?? error.message ?? "")));
    } finally {
      test.disabled = false;
    }
  } });
  return card({ title: "Email", actions: pill("Set up", "ok"),
    footer: h("div", { class: "row" }, test, h("span", { class: "subtle" }, "These are set in riskwren.toml on the server, not here.")) },
  h("div", { class: "stack" },
    data.links ? null : alert("warn", icon("alert"), h("div", {}, h("strong", {}, "Messages cannot link back to RiskWren. "),
      "Set base_url under [server] in riskwren.toml to the address people use.")),
    h("div", { class: "grid-3" }, stat(String(data.waiting), "Waiting to be sent"), stat(String(data.sent), "Sent"), stat(String(data.failed), "Given up on")),
    data.last_error ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, "The most recent problem: "), data.last_error)) : null,
    facts([["Mail server", `${data.host}, port ${data.port}`], ["Connection", SECURITY[data.security] ?? data.security],
      ["From", data.from_name ? `${data.from_name} <${data.from_address}>` : data.from_address],
      ["Daily summaries", `Put together after ${String(data.digest_hour).padStart(2, "0")}:00 UTC`],
      ["Each person chooses", "Every notice as it happens, one summary a day, or none, under Your account"]]),
    result));
}

export function adminOperations(main) {
  return show(main, {
    title: "Scheduled work",
    load: async () => {
      const [work, mail] = await Promise.all([get("/api/v1/jobs", null, { fresh: true }), get("/api/v1/mail", null, { fresh: true })]);
      return { ...work.data, mail: mail.data };
    },
    view: (data, reload) => {
      const failed = data.jobs.filter((job) => job.enabled && job.last_status === "failed");
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "Scheduled work", lede: "What RiskWren does by itself, so that nobody has to remember to." }),
        data.scheduler ? null : alert("info", icon("info"), h("div", {}, h("strong", {}, "This server's scheduler is turned off. "),
          "Jobs run when ", h("code", {}, "riskwren jobs run"), " is run, from a scheduled task or by hand, or from here.")),
        failed.length ? alert("danger", icon("alert"), h("div", {}, h("strong", {}, `${failed.map((job) => job.label).join(", ")} failed last time. `),
          "It will be tried again when it is next due. The reason is below, and in the server's log.")) : null,
        data.jobs.map((job) => jobCard(job, reload)),
        reminders(data.reminders),
        email(data.mail));
    },
  });
}
