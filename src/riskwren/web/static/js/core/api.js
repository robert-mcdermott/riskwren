// API client: envelopes, problem details, and a small time-limited GET cache. Changes carry
// the session's CSRF token; a 401 means the session ended, so the app returns to sign-in.

import { csrfToken } from "./session.js";

export class ApiError extends Error {
  constructor(status, title, detail, body) {
    super(detail || title || `HTTP ${status}`);
    this.status = status;
    this.title = title;
    this.detail = detail;
    this.body = body;
  }

  /** Field errors as { field: message }, from a 422 answer. */
  get fields() {
    const out = {};
    for (const error of this.body?.errors ?? []) {
      const where = error.location ?? [];
      const name = where[where.length - 1];
      if (name != null && !(name in out)) out[name] = error.message;
    }
    return out;
  }
}

const cache = new Map();
const TTL_MS = 20_000;

export function buildUrl(path, params = {}) {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value == null || value === "") continue;
    if (Array.isArray(value)) {
      for (const v of value) if (v != null && v !== "") url.searchParams.append(key, v);
    } else {
      url.searchParams.set(key, value);
    }
  }
  return url.pathname + url.search;
}

async function send(method, path, { params, body, raw, signal } = {}) {
  const headers = { Accept: "application/json" };
  if (raw) headers["Content-Type"] = raw.type || "application/octet-stream";
  else if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = method === "GET" ? null : csrfToken();
  if (token) headers["X-CSRF-Token"] = token;
  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      signal,
      credentials: "same-origin",
      headers,
      body: raw ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "Network error", "The server could not be reached.");
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/v1/session")) {
      window.dispatchEvent(new CustomEvent("riskwren:signed-out"));
    }
    throw new ApiError(response.status, payload?.title, payload?.detail, payload);
  }
  return payload;
}

/** GET with a short-lived cache. Concurrent requests for the same URL share one fetch. */
export function get(path, params, { fresh = false, signal } = {}) {
  const key = buildUrl(path, params);
  const hit = cache.get(key);
  if (!fresh && hit && Date.now() - hit.at < TTL_MS) return hit.promise;
  const promise = send("GET", path, { params, signal });
  cache.set(key, { at: Date.now(), promise });
  promise.catch(() => {
    if (cache.get(key)?.promise === promise) cache.delete(key);
  });
  return promise;
}

async function change(method, path, options) {
  const value = await send(method, path, options);
  cache.clear(); // a change can alter any list or count
  window.dispatchEvent(new CustomEvent("riskwren:changed", { detail: { path } }));
  return value;
}

export const post = (path, body = {}, options = {}) => change("POST", path, { body, ...options });
export const put = (path, body = {}) => change("PUT", path, { body });
export const patch = (path, body = {}) => change("PATCH", path, { body });
export const del = (path) => change("DELETE", path, {});

/** Send a file or text as the request's body. */
export const upload = (path, raw, params) => change("POST", path, { raw, params });

/** Quiet requests that should not send anyone to the sign-in page (the first look at who is signed in). */
export const peek = (path) => send("GET", path, {});
