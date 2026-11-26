// Check that the picture of how a record is connected can be used from the keyboard, and
// that the list beside it is complete. Run with: node scripts/keyboard-check.mjs
import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";

const demo = await startDemo();
const page = await openBrowser();
const fail = (message) => {
  console.error(`✗ ${message}`);
  process.exitCode = 1;
};
try {
  await page.size(1360, 900);
  await signInAs(page, demo.base, "cro");
  await page.goto(`${demo.base}/scopes`);
  await page.settled();
  const ref = await page.evaluate(`fetch("/api/v1/scopes?q=clinical+systems").then((r) => r.json()).then((b) => b.data[0].ref)`);
  const graph = await page.evaluate(`fetch("/api/v1/graph/${ref}").then((r) => r.json()).then((b) => b.data)`);
  await page.goto(`${demo.base}/graph/${ref}`);
  await page.waitFor(`document.querySelector("svg.graph")`, "the picture");
  // The list says everything the answer holds, whatever the picture left out.
  const listed = await page.evaluate(`document.querySelectorAll(".glist > li").length`);
  if (listed !== graph.count) fail(`the list has ${listed} records and the answer ${graph.count}`);
  const reach = await page.evaluate(`(() => {
    const all = [...document.querySelectorAll('svg.graph [role="link"], svg.graph [role="button"]')];
    return { count: all.length, focusable: all.every((el) => el.tabIndex === 0 && el.getAttribute("aria-label")) };
  })()`);
  if (!reach.count || !reach.focusable) fail("not every record in the picture can be reached and named");
  // Enter on a record's button shows what lies beyond it, and the focus stays on it.
  const press = (selector, key) => `(() => { const el = document.querySelector(${JSON.stringify(selector)}); el.focus();
    el.dispatchEvent(new KeyboardEvent("keydown", { key: ${JSON.stringify(key)}, bubbles: true, cancelable: true })); return document.activeElement === el; })()`;
  if (!(await page.evaluate(press(".gexpand", "Enter")))) fail("the expand button does not take the focus");
  await page.waitFor(`document.querySelector('svg.graph [data-ring="2"]') || document.querySelector('.gexpand[aria-expanded="true"]')`, "the neighbor to open");
  const kept = await page.evaluate(`document.activeElement?.getAttribute("aria-expanded")`);
  if (kept !== "true") fail(`after opening, the focus is not on the button that opened it (${kept})`);
  if (!(await page.evaluate(`Boolean(document.querySelector(".glist-more"))`))) fail("the list did not open with the picture");
  // Space closes it again.
  await page.evaluate(press('.gexpand[aria-expanded="true"]', " "));
  await page.waitFor(`!document.querySelector('.gexpand[aria-expanded="true"]')`, "the neighbor to close");
  // Enter on a record puts it in the middle.
  const target = await page.evaluate(`document.querySelector('svg.graph [role="link"]').getAttribute("aria-label")`);
  await page.evaluate(press('svg.graph [role="link"]', "Enter"));
  await page.waitFor(`location.pathname.startsWith("/graph/") && location.pathname !== "/graph/${ref}"`, "the record to move to the middle");
  await page.waitFor(`document.querySelector("svg.graph")`, "the new picture");
  const middle = await page.evaluate(`document.querySelector('.gnode[data-ring="0"] title').textContent`);
  if (!target.startsWith(middle)) fail(`${target} was chosen and ${middle} is in the middle`);
  if (!process.exitCode) console.log(`✓ the picture of ${ref}: ${reach.count} things reachable by keyboard, ${listed} records listed`);
} finally {
  await page.close?.();
  await demo.stop?.();
}
