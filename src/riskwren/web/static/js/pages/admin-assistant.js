// Admin → Assistant: how the optional assistant is set up, a check that its provider answers,
// and the log of every exchange. Present only while the assistant is turned on.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { dateTime } from "../core/format.js";
import { card, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const TASKS = { summarize: "Summary", draft_risk: "Drafted a risk", check: "Connection check" };
const STATES = { answered: ["Answered", "ok"], failed: ["Failed", "danger"], refused: ["Over the day's limit", "warn"], asking: ["Asking", "info"] };

function setup(data) {
  const rows = [["Provider", `${data.provider} (the protocol it speaks)`], ["Model", data.model], ["Address", data.url],
    ["Key", data.key_env ? `From the ${data.key_env} environment variable` : "None: a provider on this computer, or one that needs none"],
    ["Sent", data.send.length ? `Records of the data classes ${data.send.join(", ")}, and records with none; never restricted ones` : "Only records with no data class; never restricted ones"],
    ["Each person", `${data.daily_limit} exchanges a day, each within ${data.time_limit_seconds} seconds`]];
  const result = h("div", { "aria-live": "polite" });
  const check = button("Check the connection");
  check.addEventListener("click", async () => {
    check.disabled = true;
    result.replaceChildren(h("p", { class: "muted" }, "Asking the provider…"));
    try {
      const done = await post("/api/v1/admin/assistant/check", {});
      result.replaceChildren(h("p", {}, pill("It answered", "ok"), ` in ${(done.data.took_ms / 1000).toFixed(1)} seconds: “${done.data.answer}”`));
    } catch (failed) {
      result.replaceChildren(h("div", { class: "alert alert-danger", role: "alert" }, failed?.detail ?? "The provider did not answer."));
    } finally {
      check.disabled = false;
    }
  });
  return card({ title: "Set up in riskwren.toml", actions: pill("On", "ok") },
    h("div", { class: "stack" },
      h("dl", { class: "dl" }, rows.flatMap(([term, said]) => [h("dt", {}, term), h("dd", {}, said)])),
      h("p", { class: "muted" }, "To change any of it, edit the [assistant] section and restart RiskWren. To turn it off, set enabled = false: its routes, its pages, and this one go away."),
      h("div", { class: "row" }, check), result));
}

function logCard(entries) {
  if (!entries.length) return card({ title: "Log" }, h("p", { class: "subtle" }, "Nobody has asked the assistant anything yet."));
  return card({ title: "Log", flush: true },
    h("div", { class: "card-pad" }, h("p", { class: "muted" }, "Every exchange, newest first: who asked, what for, which tools it used, and what it answered. Each is also in the history, where it cannot be changed unnoticed.")),
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("caption", { class: "sr-only" }, "The assistant's exchanges"),
      h("thead", {}, h("tr", {}, ["When", "Who", "What", "Tools", "Tokens", "Result"].map((text) => h("th", { scope: "col" }, text)))),
      h("tbody", {}, entries.map((entry) => h("tr", {},
        h("td", {}, dateTime(entry.asked_at)),
        h("td", {}, entry.asked_by),
        h("td", {}, h("div", { class: "cell-main" }, `${TASKS[entry.task] ?? entry.task}${entry.ref ? ` of ${entry.ref}` : ""}`),
          entry.asked ? h("div", { class: "cell-sub" }, `Asked: ${entry.asked}`) : null,
          entry.answer ? h("div", { class: "cell-sub" }, `Answered: ${entry.answer}`) : null),
        h("td", {}, entry.tools_used.length ? entry.tools_used.map((used) => used.name).join(", ") : "—"),
        h("td", {}, `${entry.input_tokens} in, ${entry.output_tokens} out`),
        h("td", {}, pill(...(STATES[entry.status] ?? [entry.status, ""])), entry.error ? h("div", { class: "cell-sub" }, entry.error) : null,
          entry.took_ms != null ? h("div", { class: "cell-sub" }, `${(entry.took_ms / 1000).toFixed(1)} s`) : null)))))));
}

export function adminAssistant(main) {
  return show(main, {
    title: "Assistant",
    load: async () => (await get("/api/v1/admin/assistant", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Admin", title: "Assistant",
        lede: "An assistant that summarizes records and drafts risks, with the provider your organization chose. It reads only what the person asking may see, is sent no restricted record, and makes nothing: a person saves every draft." }),
      setup(data), logCard(data.log)),
  });
}
