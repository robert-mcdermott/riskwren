# UX and design system

RiskWren should feel like a well-made professional tool: calm, quick, and exact. Most of the people who use it do so a few times a year and did not ask to, so the design has two jobs. For the owner of a risk or a control it must make their part short and obvious. For the risk and compliance team it must make a large amount of connected information readable at a glance, and every figure traceable to what produced it.

## Design principles

1. **Answer first.** Every page leads with the answer to the question that brought the person there: *what do I owe?*, *how bad is this?*, *is it in order?*, *where do we stand?*
2. **Short by default, deep on demand.** Lists are dense and scannable. Detail opens beside them, not instead of them.
3. **Show the reasoning.** A rating, a suggested residual, or a readiness figure is never a bare label. One click shows what produced it.
4. **Rating and standing are different things.** How much is at stake and whether it is in order are always two signals, never one color.
5. **The URL is the state.** Filters, sort, tabs, and the open record all live in the URL. Back works, and every view can be shared.
6. **One record, one click from its neighbors.** A risk shows its controls, a control its risks and requirements, a system everything that rests on it.
7. **Keyboard first, mouse friendly.** Everything is reachable by keyboard. Queues are fastest with keys.
8. **Honest states.** Untested is shown as untested, stale as stale, overdue as overdue, and nothing is green by default.
9. **Accessible.** WCAG 2.2 AA in every palette and mode.

## Identity

### The mark

The logo is a **stylized wren on a perch**: a compact, rounded body with the short, sharply cocked tail that makes a wren recognizable in silhouette, standing on a single short line. It is drawn from a few geometric strokes in a single color so that it holds at 16 pixels as a favicon and scales to a hero. The line beneath the bird is the perch, and it is also the **threshold**: the level an organization has decided it will live with, and the bird that watches from it.

- Supplied as SVG in three forms: the mark alone, the mark with the wordmark beside it, and a single-color version for print and dark backgrounds.
- The wordmark sets *Risk* in regular weight and *Wren* in semibold, in the interface font.
- Clear space equal to the height of the tail on every side.

An adopting organization replaces the mark and wordmark with its own. "RiskWren" then appears only as a small "Powered by RiskWren" link in the footer, which can be turned off.

### Voice

Plain words, short sentences, no jargon the reader did not bring with them. The interface says "What could go wrong?" and "How well is this working?", and never "Populate inherent risk attributes". Buttons name their outcome ("Accept until 30 June"), errors say what to do next, and empty states teach.

## Visual language

### Tokens

All visual values are CSS custom properties defined once in `tokens.css`. Colors are `light-dark()` pairs in `oklch()`, so each has a day and a night value side by side and the two stay balanced.

- **Surfaces:** `--bg`, `--surface-1..3`, `--border`, `--border-strong`, and `--control-border` for the edge of form fields, which must reach 3:1 against the page
- **Text:** `--text`, `--text-muted`, `--text-subtle`, `--text-inverse`
- **Accent:** `--accent`, `--accent-hover`, `--accent-strong`, `--accent-soft`, `--on-accent`
- **Standing:** `--ok`, `--warn`, `--danger`, `--info`, `--neutral`, each with a `-soft` tint
- **Rating:** `--rating-1..5`, an ordinal ramp (see below), each with a readable text color on top
- **Record types:** `--rec-risk`, `--rec-control`, `--rec-process`, `--rec-system`, `--rec-party`, each with a `-soft` tint
- **Series:** `--series-0..5`, categorical colors for charts
- **Spacing:** 4 px base scale (`--space-1` = 4 px … `--space-10` = 64 px)
- **Radius:** `--radius-s` 6 px, `--radius-m` 10 px, `--radius-l` 16 px
- **Elevation:** three shadow levels, deeper in dark mode
- **Motion:** 120, 200, and 320 ms durations, all disabled under `prefers-reduced-motion`

### Rating and standing

A critical risk that is well controlled and formally accepted is not a problem; it is the program working. A low risk whose review is a year overdue is a problem. So rating and standing never share colors.

- **Rating** uses its own ordinal ramp in a single hue (plum), pale to deep, always with a glyph of one to five bars and the rating's name. It reads as *how much is at stake*.
- **Standing** uses the conventional green, amber, and red, always with an icon and a word. It reads as *is this in order*.

Color is never the only signal for either.

| Standing | Color | Mark |
|---|---|---|
| Within appetite | Green | ● |
| Accepted | Green | ◐ |
| Being treated | Blue | ◔ |
| Needs a decision | Red | ! |
| Not assessed | Grey | ○ |
| Closed | Grey, quiet | ✕ |

Flags sit beside the standing, in amber with their own icon and words: *review overdue*, *residual may be out of date*.

Many boards expect a heat map in green, amber, and red. An organization can choose the **signal ramp** for ratings in Admin → Appearance, which replaces the plum ramp with those colors everywhere a rating is shown. The bars, the names, and the separate standing mark remain, so nothing depends on telling red from green.

### Record types

Each record type has one hue and one icon, used consistently in chips, list rows, graph nodes, and page headers. A test keeps record hues well away from the standing colors and the rating ramp in every palette.

| Record | Hue | Icon idea |
|---|---|---|
| Risk | Indigo | Triangle with a point |
| Control | Teal | Shield outline |
| Process | Ochre | Linked steps |
| System | Blue | Window |
| Third party | Slate | Storefront |

Later record types (requirement, scope, evidence, issue, policy) take their hues when their wave arrives, under the same test.

### Typography

- **Font:** the platform's system UI stack. Nothing to download. Tabular numerals in tables and figures.
- **Scale:** 12 / 13 / 14 (body) / 16 / 18 / 20 / 24 / 30 / 36 px.
- **Weights:** 400, 500, 600.

### Themes: mode and palette

Appearance has two independent choices, under **Appearance** in the top bar and in the command palette.

- **Mode:** light, dark, or follow the system.
- **Palette:** a named set of colors with a day and a night version. The organization sets the default; each person may choose another, remembered in their browser.

| Palette | By day | After dark |
|---|---|---|
| **Wren** (default) | Warm paper neutrals, ink text, a deep harbor-blue accent, a thin russet rule | Warm charcoal, soft harbor-blue accent |
| **Slate** | Cool white and grey, cobalt accent; the conventional enterprise look | Blue-black surfaces, bright cobalt accent |
| **Garnet** | Neutral greys with a deep red accent, for the many institutions whose colors are red | Near-black with a softened garnet accent |

Every palette and mode is checked for AA contrast, first on the token pairs and then by sampling the rendered text of the main pages against its real background.

### Branding

An organization makes RiskWren its own in **Admin → Appearance**, with a live preview and no file editing:

- product name and organization name,
- logo for light and dark backgrounds, and a favicon,
- default palette, and optionally its own accent color,
- the rating ramp: ordinal or signal,
- from wave 9, a full custom palette, a message and image on the sign-in page, footer links, an email header, and its own words for key terms ("unit" may be "department"; "third party" may be "vendor").

The server generates `theme.css` from these settings. A chosen accent is checked for contrast against its backgrounds before it can be saved, lightened automatically for dark mode, and given readable text on top. Uploaded images are size-limited, type-checked, and, for SVG, sanitized.

## Information architecture

```text
Top bar:  [mark / product name]  [ ⌘K Search… ]  [+ New]  [🔔] [appearance] [me]

Sidebar:  Home
          Risks         Register · Heat map · Treatment plans · Acceptances
          Controls      Library · Tests (2)
          Inventory     Processes · Systems · Third parties · Information (2)
          Compliance    Frameworks · Scopes · Assessments · Evidence        (2)
          Issues        Issues (2) · Exceptions (2) · Actions
          Policies      Library · Acknowledgments                           (4)
          Audit         Plan · Engagements                                  (7)
          Incidents     Reports · Cases                                     (8)
          Reports       Dashboard · Portfolio (6) · Reports (6)
          ───────────
          Admin         Program · People and units · Appearance · System
```

Numbers in brackets are the wave in which a section arrives; the sidebar never shows an empty section.

- Each person sees only the sections their roles use. A member sees Home, their own records, and, from wave 4, the policy library.
- **Command palette (⌘K or Ctrl-K):** find any record by reference or name, jump to a page, or run an action ("New risk", "Switch to dark").
- The sidebar collapses to icons on narrow screens and becomes a drawer on a phone. Attesting, completing an action, reading a policy, and reporting all work on a phone; assessment and administration assume a larger screen.

## Key screens

| Screen | Purpose | Highlights |
|---|---|---|
| **Home** | What I owe and what is waiting on others | One list, overdue first: reviews due, actions, acceptances expiring, drafts. For a leader, their unit's risks above appetite. For program staff, what is at risk of running late across the organization |
| **Risk register** | Find and compare risks | A dense table with rating, standing, category, unit, owner, and next review; filters for all of them; grouping by category or unit; the selected risk opens beside the list |
| **Heat map** | See the whole register at once | A five-by-five grid of counts for inherent, residual, or target; the appetite boundary drawn for a chosen category; a cell opens its risks beside the grid; a table view of the same figures |
| **Risk** | Everything about one risk | Header with reference, rating, standing, owner, and next review. The *journey* strip: inherent → residual → target, each opening its reasoning. Tabs: Overview, Assessments, Controls, Treatment, Links, History |
| **Assess** | Record a judgment | Likelihood and each impact dimension as a row of five choices with the definition of the level under the pointer; the rating appears as levels are chosen; for a residual assessment, the suggestion and its working sit beside the form |
| **Control** | One control in context | Statement, owner, kind, and frequency; effectiveness with who rated it, when, and on what basis; the risks it reduces; from wave 2 the requirements it satisfies, its tests, and its evidence |
| **Process, System, Third party** | One thing and what rests on it | The shared header and tabs; *relies on* and *supports* lists; its risks with ratings; from wave 2 the scopes it is in |
| **Treatment plan** | Follow a risk down | Objective, target rating, owner, due date, and the actions with their progress |
| **Accept a risk** | A named decision | What is being accepted, at what rating, why appetite is exceeded, the controls in place, the end date within the limit for that rating, and a rationale; refused with the reason if the person lacks the authority |
| **Actions** | One list of everything owed | By owner, due date, and source; an action completes with a note and optional evidence |
| **Dashboard** | Where the program stands | The heat map, the top risks, risks above appetite by standing, distribution by category and unit, reviews and actions overdue; every tile opens the records behind it |
| **Framework and scope** (wave 2) | Readiness | The five-state bar, the requirement tree with states, and the controls, tests, and evidence behind any requirement |
| **Test queue** (wave 2) | Work through tests | Split view: the queue on the left; on the right the control, its procedure, the previous result, and the result form |
| **Admin: Program** | Shape the program | The taxonomy with appetite; the scoring method with its matrix; cadences; vocabularies; from wave 3 editing with an impact preview |
| **Admin: Appearance** | Brand it | Names, logos, palette, accent, and rating ramp with a live preview and contrast results |

## Components

Each is a small ES module that returns DOM. There is no virtual DOM and no templating library.

- **Layout:** app shell, sidebar, top bar, page header, split view, drawer, modal, tabs
- **Records:** record chip (icon, reference, name), rating badge with a reasons popover, standing pill, owner list, journey strip
- **Data display:** data table (sortable, column chooser, dense mode), definition list, stat tile, timeline, empty state, skeleton
- **Forms:** fields with server errors on their fields, level picker (a row of defined levels), record picker, person picker, unit picker, date picker
- **Workflow:** action list, acceptance dialog, plan editor
- **Feedback:** toast with undo, inline alert, due-date badge, progress bar
- **Charts (SVG):** heat map, bar, stacked bar, line, donut, and from wave 2 the five-state readiness bar, each with a table behind it

## Interaction details

- **Rating badge:** clicking it opens the reasons: likelihood, each dimension's level with its definition, who judged it, and when. A residual rating also shows the suggestion and whether the assessor departed from it.
- **Level picker:** five choices in a row, each with its name; the definition of the focused level is shown beneath, so an assessor never has to remember what "Major" means on the safety scale.
- **Due dates:** shown as relative time with the date on hover; amber inside the warning window; red when past.
- **Undo:** reversible actions (adding a link, dismissing a notice) show a toast with Undo. Assessments, ratings, and acceptances are not undoable; they ask for confirmation and are superseded, never erased.
- **History:** every record's History tab shows changes as a readable timeline ("Residual rating changed from High to Moderate by … because …"), filterable by kind.
- **Empty states teach:** an empty register explains how to add the first risk, start from the library, or import a spreadsheet.
- **Printing:** a risk, the register, the heat map, and the dashboard have print styles and produce clean PDFs from the browser's print dialog.

## Accessibility checklist

- Landmarks, headings in order, and a skip link
- A visible focus ring (2 px, offset) in every palette and mode
- Every control reachable and operable by keyboard; no traps in drawers or modals
- `aria-live` announcements for saves, async results, and workflow actions
- Form errors tied to their fields and summarized at the top
- The heat map and every chart have tabular alternatives
- Targets at least 24 × 24 px
- Respects `prefers-reduced-motion` and `prefers-contrast`
- An automated audit runs over every documented screen, and a manual screen-reader script is run before each release

## Performance budgets

| Budget | Target |
|---|---|
| App shell JS and CSS (gzipped) | ≤ 100 KB |
| Each part loaded on first use (gzipped) | ≤ 40 KB |
| First meaningful render on a laptop | < 1 s |
| List API response (p95) at 10,000 records | < 200 ms |
| Record page API response (p95) | < 200 ms |
| Rating update after choosing a level | < 50 ms (computed in the browser) |
| Demo organization build | < 60 s |
