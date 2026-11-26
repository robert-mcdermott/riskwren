import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { check, inline, markdown, MENU, prose, slug } from "../../scripts/site/build.mjs";

test("a heading's anchor is the one the repository's own reader gives it", () => {
  assert.equal(slug("Independence, and a second pair of eyes"), "independence-and-a-second-pair-of-eyes");
  assert.equal(slug("`riskwren users`"), "riskwren-users");
  assert.equal(slug("The demo and the network"), "the-demo-and-the-network");
  assert.equal(slug("0.2.0 - 2026-11-25"), "020---2026-11-25");
});

test("inline text: code is left alone, and everything else is escaped", () => {
  assert.equal(inline("Use `a < b` and **bold** <script>"), "Use <code>a &lt; b</code> and <strong>bold</strong> &lt;script&gt;");
  assert.equal(inline("`**not bold**`"), "<code>**not bold**</code>");
  assert.equal(inline("an *aside* here"), "an <em>aside</em> here");
  assert.equal(inline("5 * 4 * 3"), "5 * 4 * 3");
});

test("links are rewritten, and only links elsewhere are marked", () => {
  const link = (href) => href.replace(".md", ".html");
  assert.equal(inline("[Readiness](compliance.md#readiness)", link), '<a href="compliance.html#readiness">Readiness</a>');
  assert.equal(inline("[uv](https://docs.astral.sh/uv/)", link), '<a href="https://docs.astral.sh/uv/" rel="noopener">uv</a>');
  assert.equal(inline("[`riskwren users`](cli.md#riskwren-users)", link), '<a href="cli.html#riskwren-users"><code>riskwren users</code></a>');
  assert.equal(inline("see <https://example.org/a>"), 'see <a href="https://example.org/a" rel="noopener">https://example.org/a</a>');
});

test("headings get anchors, and a repeated heading gets its own", () => {
  const { html, headings } = markdown("# Title\n\n## Added\n\ntext\n\n## Added\n");
  assert.deepEqual(headings.map((h) => [h.level, h.id]), [[1, "title"], [2, "added"], [2, "added-1"]]);
  assert.match(html, /<h1 id="title">Title<\/h1>/);
  assert.match(html, /<h2 id="added-1">Added<a class="anchor" href="#added-1"/);
});

test("a table keeps a bar that is inside code, and can be scrolled with the keyboard", () => {
  const { html } = markdown("| Key | Meaning |\n|---|---|\n| `a | b` | Either |\n");
  assert.match(html, /<div class="table-wrap" tabindex="0" role="region" aria-label="Table">/);
  assert.match(html, /<th scope="col">Key<\/th>/);
  assert.match(html, /<td><code>a \| b<\/code><\/td><td>Either<\/td>/);
});

test("lists: numbered ones keep their start, and a wrapped item stays one item", () => {
  const { html } = markdown("3. Third\n   carried on\n4. Fourth\n\n- one\n- two\n");
  assert.match(html, /<ol start="3"><li>Third carried on<\/li><li>Fourth<\/li><\/ol>/);
  assert.match(html, /<ul><li>one<\/li><li>two<\/li><\/ul>/);
});

test("code blocks are escaped and say their language", () => {
  const { html } = markdown("```bash\nuv run riskwren serve  # <port>\n```\n");
  assert.match(html, /<pre><code class="language-bash">uv run riskwren serve {2}# &lt;port&gt;<\/code><\/pre>/);
});

test("a paragraph that is only a picture is handed to the figure maker", () => {
  const seen = [];
  const figure = (alt, src, caption) => { seen.push([alt, src, caption]); return "<figure></figure>"; };
  const { html } = markdown('Before.\n\n![What it shows](img/home-light.webp "A caption")\n\nAfter ![inline](img/x.webp) text.\n', { figure });
  assert.deepEqual(seen, [["What it shows", "img/home-light.webp", "A caption"]]);
  assert.match(html, /<p>Before\.<\/p>\n<figure><\/figure>\n<p>After <img src="img\/x\.webp" alt="inline" loading="lazy"> text\.<\/p>/);
});

test("words from the code's documentation show their names as code", () => {
  assert.equal(prose("With ``dry_run`` (the default)\nnothing <is> changed, like `this`."),
    "With <code>dry_run</code> (the default) nothing &lt;is&gt; changed, like <code>this</code>.");
});

test("a quotation holds its own blocks", () => {
  const { html } = markdown("> **Note.** One.\n>\n> Two.\n");
  assert.equal(html, "<blockquote><p><strong>Note.</strong> One.</p>\n<p>Two.</p></blockquote>");
});

test("the check finds a missing page, a missing anchor, and a missing picture", () => {
  const out = mkdtempSync(join(tmpdir(), "site-check-"));
  try {
    mkdirSync(join(out, "img"));
    writeFileSync(join(out, "img", "here.webp"), "");
    writeFileSync(join(out, "a.html"), '<h2 id="one">One</h2> <a href="b.html#two">ok</a> <a href="b.html#three">no anchor</a>'
      + ' <a href="c.html">no page</a> <a href="#one">ok</a> <a href="#none">no anchor here</a>'
      + ' <img src="img/here.webp" alt=""> <img src="img/gone.webp" alt=""> <a href="https://example.org/x">elsewhere</a>');
    writeFileSync(join(out, "b.html"), '<h2 id="two">Two</h2>');
    assert.deepEqual(check(out), [
      "a.html: no #three in b.html", "a.html: href c.html is missing", "a.html: no #none in a.html", "a.html: src img/gone.webp is missing",
    ]);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test("every page in the menu is named once", () => {
  const pages = MENU.flatMap(([, items]) => items.map(([page]) => page));
  assert.equal(new Set(pages).size, pages.length);
  assert.equal(pages[0], "index");
});
