// Build a fresh demo organization in a temporary directory and serve it, for the audit and
// the screenshot capture. Nothing here touches an installation you care about.

import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

/** A port nothing is listening on, asked of the operating system. */
function freePort() {
  return new Promise((done, failed) => {
    const probe = createServer();
    probe.once("error", failed);
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => done(port));
    });
  });
}

/** Build a demo and serve it. The port is one that is free: a fixed one may already belong to
 *  something else on this machine, which would then be audited or photographed in its place. */
export async function startDemo({ port = null, seed = 1 } = {}) {
  port ??= await freePort();
  const home = mkdtempSync(join(tmpdir(), "riskwren-demo-"));
  const built = spawnSync("uv", ["run", "riskwren", "demo", home, "--seed", String(seed), "--port", String(port)],
    { cwd: ROOT, encoding: "utf8" });
  if (built.status !== 0) throw new Error(`The demo did not build:\n${built.stdout}${built.stderr}`);
  const server = spawn("uv", ["run", "riskwren", "--config", join(home, "riskwren.toml"), "serve"],
    { cwd: ROOT, stdio: "ignore" });
  const base = `http://127.0.0.1:${port}`;
  const until = Date.now() + 30000;
  for (;;) {
    try {
      if ((await fetch(`${base}/api/v1/health/ready`)).ok) break;
    } catch { /* not up yet */ }
    if (server.exitCode !== null) throw new Error("The demo server stopped as it started");
    if (Date.now() > until) { server.kill(); throw new Error("The demo server did not start"); }
    await new Promise((r) => setTimeout(r, 200));
  }
  return { base, stop() { server.kill(); rmSync(home, { recursive: true, force: true }); } };
}

/** Sign the page in as one of the demo's sample people, by the key the demo gives them. */
export async function signInAs(page, base, key) {
  await page.goto(`${base}/api/v1/meta`); // any page of the demo: the request must come from it
  const ok = await page.evaluate(`(async () => {
    const meta = (await (await fetch("/api/v1/meta")).json()).data;
    const person = meta.demo.accounts.find((p) => p.key === ${JSON.stringify(key)});
    const done = await fetch("/api/v1/session/demo", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: person.email }) });
    return done.ok;
  })()`);
  if (!ok) throw new Error(`Could not sign in as ${key}`);
}
