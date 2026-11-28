// A small driver for headless Chrome over its debugging protocol. Node 22, no packages.
// Used by the accessibility audit and by the documentation's screenshot capture.

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CANDIDATES = [
  process.env.CHROME,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
].filter(Boolean);

function launch(binary, profile) {
  return new Promise((resolve, reject) => {
    const child = spawn(binary, [
      "--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
      "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--disable-gpu",
      "--force-device-scale-factor=2", "about:blank",
    ], { stdio: ["ignore", "ignore", "pipe"] });
    let seen = "";
    const timer = setTimeout(() => reject(new Error("Chrome did not start in time")), 20000);
    child.once("error", (error) => { clearTimeout(timer); reject(error); });
    child.stderr.on("data", (chunk) => {
      seen += chunk;
      const found = seen.match(/DevTools listening on (ws:\/\/\S+)/);
      if (found) { clearTimeout(timer); resolve({ child, endpoint: found[1] }); }
    });
  });
}

/** Start Chrome and return a page to drive. Call close() when finished. */
export async function openBrowser() {
  const profile = mkdtempSync(join(tmpdir(), "riskwren-chrome-"));
  let started = null;
  let lastError = null;
  for (const binary of CANDIDATES) {
    try { started = await launch(binary, profile); break; } catch (error) { lastError = error; }
  }
  if (!started) throw new Error(`Chrome was not found (set CHROME to its path): ${lastError?.message}`);
  const socket = new WebSocket(started.endpoint);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let next = 0;
  const waiting = new Map();
  const listeners = new Set();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && waiting.has(message.id)) {
      const { resolve, reject } = waiting.get(message.id);
      waiting.delete(message.id);
      if (message.error) reject(new Error(message.error.message)); else resolve(message.result);
    } else for (const listener of listeners) listener(message);
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++next;
    waiting.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params, sessionId }));
  });
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  const page = (method, params) => send(method, params, sessionId);
  await page("Page.enable");
  await page("Runtime.enable");

  const evaluate = async (expression) => {
    const result = await page("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
    }
    return result.result.value;
  };
  const waitFor = async (expression, what = expression, timeout = 15000) => {
    const until = Date.now() + timeout;
    for (;;) {
      if (await evaluate(`Boolean(${expression})`)) return;
      if (Date.now() > until) throw new Error(`Timed out waiting for ${what}`);
      await new Promise((resolve) => setTimeout(resolve, 60));
    }
  };
  return {
    evaluate,
    waitFor,
    /** The window's size, drawn at twice its pixels unless ``scale`` says otherwise. */
    async size(width, height, scale = 2) {
      await page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile: width < 600 });
    },
    async scheme(value) {
      await page("Emulation.setEmulatedMedia", { features: [
        { name: "prefers-color-scheme", value }, { name: "prefers-reduced-motion", value: "reduce" }] });
    },
    async goto(url) {
      const loaded = new Promise((resolve) => {
        const listener = (message) => {
          if (message.method === "Page.loadEventFired" && message.sessionId === sessionId) {
            listeners.delete(listener);
            resolve();
          }
        };
        listeners.add(listener);
      });
      await page("Page.navigate", { url });
      await loaded;
    },
    /** Wait until the app has drawn a page: a heading in main, nothing still loading. */
    async settled() {
      await waitFor(`document.querySelector("h1") && !document.querySelector("[aria-busy='true']")`, "the page to draw");
      await new Promise((resolve) => setTimeout(resolve, 250));
    },
    /** A picture of the page. The file's ending chooses the format: .webp (smaller) or .png. */
    async screenshot(file, { fullPage = false, quality = 82, scale = 1 } = {}) {
      let clip;
      if (fullPage) {
        // A picture can be 16,383 pixels tall at most, and the screen is drawn at twice its size.
        const { cssContentSize } = await page("Page.getLayoutMetrics");
        clip = { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, Math.floor(8000 / scale)), scale };
      }
      const format = file.endsWith(".webp") ? "webp" : "png";
      const { data } = await page("Page.captureScreenshot", {
        format, quality: format === "webp" ? quality : undefined, clip, captureBeyondViewport: fullPage });
      writeFileSync(file, Buffer.from(data, "base64"));
    },
    async close() {
      try { await send("Browser.close"); } catch { /* already gone */ }
      socket.close();
      const gone = new Promise((resolve) => started.child.once("exit", resolve));
      started.child.kill();
      await Promise.race([gone, new Promise((resolve) => setTimeout(resolve, 3000))]);
      try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* the system clears its temporary files */ }
    },
  };
}
