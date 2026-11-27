// The page someone without an account sees when they open a link they were sent: who is
// asking, by when, and the questions; saving to finish later, and sending. The link's token
// is after "#" in the address, which the browser never sends to a server, and goes back in
// a header of its own. Nothing else in the app is reachable from here.

import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { brand } from "../components/shell.js";
import { banner } from "../components/form.js";
import { questionnaireForm } from "../components/questionnaire.js";
import { alert } from "../components/ui.js";
import { setTitle } from "./page.js";

const HEADER = "X-RiskWren-Link";

async function call(method, token, body) {
  const response = await fetch(method === "POST" ? "/api/v1/respond/submit" : "/api/v1/respond", {
    method, credentials: "omit", cache: "no-store",
    headers: { Accept: "application/json", [HEADER]: token, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const error = new Error(payload?.detail || "That did not work.");
    error.status = response.status;
    error.fields = Object.fromEntries((payload?.errors ?? []).map((each) => [each.location?.[0], each.message]));
    throw error;
  }
  return payload.data;
}

function frame(meta, ...children) {
  return h("div", { class: "respond" },
    h("header", { class: "respond-top" }, h("div", { class: "sign-in-brand" }, brand(meta))),
    h("main", { class: "respond-main", id: "main" }, children));
}

function stopped(root, meta, text) {
  setTitle("This link");
  root.replaceChildren(frame(meta, h("h1", { tabindex: "-1" }, "This link cannot be used"), h("p", {}, text)));
  root.querySelector("h1").focus();
}

export async function respondPage(root, meta) {
  // The token is read once and taken out of the address bar, so it is not left on screen.
  const token = window.location.hash.slice(1);
  if (token) history.replaceState(null, "", "/respond");
  const kept = token || sessionStorage.getItem("riskwren.link") || "";
  if (token) sessionStorage.setItem("riskwren.link", token);
  if (!kept) {
    stopped(root, meta, "The address is missing the part that opens your questionnaire. Open the link from the message you were sent, or ask whoever sent it for a new one.");
    return;
  }
  let asked;
  try {
    asked = await call("GET", kept);
  } catch (error) {
    sessionStorage.removeItem("riskwren.link");
    stopped(root, meta, error.message);
    return;
  }
  setTitle(asked.title);
  const problem = banner();
  const saved = h("p", { class: "subtle", "aria-live": "polite" }, asked.saved_at ? "Your earlier answers are filled in." : "");
  const form = questionnaireForm(asked.document, asked.answers ?? {});
  const saveButton = button("Save to finish later");
  const sendButton = button("Send the answers", { kind: "btn-primary" });
  const busy = (on) => {
    saveButton.disabled = on;
    sendButton.disabled = on;
  };
  const fail = (error) => {
    if (error.status === 410 || error.status === 404) {
      sessionStorage.removeItem("riskwren.link");
      stopped(root, meta, error.message);
      return;
    }
    form.setErrors(error.fields ?? {});
    problem.textContent = error.message;
    problem.hidden = false;
  };
  saveButton.addEventListener("click", async () => {
    problem.hidden = true;
    busy(true);
    try {
      await call("PUT", kept, { answers: form.answers() });
      saved.textContent = "Saved. Open the same link again to finish.";
    } catch (error) {
      fail(error);
    } finally {
      busy(false);
    }
  });
  sendButton.addEventListener("click", async () => {
    problem.hidden = true;
    const missing = form.missing();
    form.setErrors(missing);
    if (Object.keys(missing).length) {
      problem.textContent = "Some questions still need an answer.";
      problem.hidden = false;
      return;
    }
    busy(true);
    try {
      await call("POST", kept, { answers: form.answers() });
      sessionStorage.removeItem("riskwren.link");
      setTitle("Thank you");
      root.replaceChildren(frame(meta, h("h1", { tabindex: "-1" }, "Thank you"),
        h("p", {}, `Your answers have been sent to ${asked.organization}. ${asked.asked_by ? `${asked.asked_by} will be in touch if anything needs more detail.` : ""}`),
        h("p", { class: "subtle" }, "This link no longer opens the questionnaire. You can close this page.")));
      root.querySelector("h1").focus();
    } catch (error) {
      fail(error);
    } finally {
      busy(false);
    }
  });
  const who = [asked.organization, asked.asked_by ? `${asked.asked_by} asks` : null].filter(Boolean).join(" · ");
  root.replaceChildren(frame(meta,
    h("p", { class: "eyebrow" }, who),
    h("h1", {}, asked.title),
    h("p", { class: "lede" }, `For ${asked.contact}, of ${asked.third_party}.`, asked.due_on ? ` Please answer by ${date(asked.due_on)}.` : ""),
    asked.summary ? h("p", { class: "muted" }, asked.summary) : null,
    alert("info", h("div", {}, `You can save your answers and come back to them with the same link until ${date(asked.expires_at)}. Once you send them, they cannot be changed.`)),
    problem, h("h2", { class: "sr-only" }, "The questions"), form.node, saved,
    h("div", { class: "row wrap respond-actions" }, sendButton, saveButton)));
}
