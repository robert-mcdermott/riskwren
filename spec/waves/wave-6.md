# Wave 6: Insight (v0.6.0)

**Goal:** answer leadership's questions from the record, with figures that explain themselves. Waves 1 to 5 made a record of what could go wrong, what must be complied with, what the organization has said and promised, and who it depends on. Wave 6 reads that record back: defined measures with a history, views across the portfolio, a report that can be reopened exactly as it was given, the register as it stood on any date, and packages an auditor or a sponsor can verify.

**Branch:** `wave-6` · **Target version:** `0.6.0` · **Status:** ☐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). For a security leader, insight means being able to say, with a date and a definition, how many critical findings are open and for how long, how much of each framework is verified rather than merely in place, which suppliers hold restricted information without a current review or a covering agreement, and whether those figures are getting better; and to hand an auditor a package that proves itself.

## Exit criteria

The wave is done when, on a fresh checkout:

1. Each measure says what it counts, over what period, and for which records; its figure opens the list behind it; a daily snapshot gives its trend (RPT-06).
2. Risk and compliance can be viewed by unit, category, framework, and third party over a chosen period, drilling down to records; issues by root cause, age, and source over time (RPT-07, RPT-11).
3. A periodic leadership report of top risks, movement, appetite, posture, and overdue items is frozen when issued, and reopens unchanged (RPT-08).
4. Any record, and the register, can be seen as it stood on a chosen date (RPT-09).
5. A scope, a risk, or a third party can be exported as a complete package with a manifest that verifies (RPT-10).
6. The role-by-route matrix covers every new route; the demo has something worth reading on every new screen; the accessibility audit passes over them.

## Slices

### Slice 1: Measures ☑

**Goal:** figures with definitions, and their history.

- [x] A catalog of defined measures of risk, treatment, compliance, third parties, and timeliness: each with what it counts, the records it counts among, and whether lower or higher is better
- [x] Each figure opens the list of records it counts, filtered the same way
- [x] Daily snapshots, taken by the scheduler, so each measure has a trend; taking one again on the same day replaces it
- [x] Reports → Measures: every measure with its current figure, its definition, and its trend over the last quarter
- [x] The demo's snapshots over its last half year, taken as its history happened

**Acceptance:** each measure's figure equals the length of the list it opens, for the person who sees it; a snapshot taken twice in a day keeps one.

**Done:** sixteen measures are defined in `riskwren.insight.measures`, in five groups, each with what it counts in words, the record type and filters of the list it opens (or, for the stops, the coverage page), and whether fewer is better. A figure is worked out by the list's own conditions for the person asking (`reporting.count`, the action search, or the stops they may see), so it equals the length of the list it opens. The scheduler's new job, Measures, takes a snapshot every six hours of each measure for the whole organization (`measure_snapshot`, one row per measure and day, unaudited, the day's earlier one replaced). **Reports → Measures** shows each with its figure, a line of the last quarter's snapshots with its first and last figures in words, and how far it moved, marked better or worse by its direction; it is for those who read everything, since the trends are the organization's. The demo takes a snapshot each week of its last half year as its history happens, and one on the day it is built. The acceptance tests are `tests/test_measures.py::test_each_figure_is_the_length_of_the_list_it_opens` and `::test_a_snapshot_taken_twice_in_a_day_keeps_one`.

### Slice 2: Portfolio ☑

**Goal:** the register and compliance, cut every way leadership asks.

- [x] Views by unit, category, framework, and third party, over a chosen period, each figure drilling down to records
- [x] Issues by root cause, age, and source over time

**Acceptance:** every figure in a view opens exactly the records it counts.

**Done:** `riskwren.insight.portfolio` builds five views over the last quarter, half year, or year: by unit (the units beneath the organization), by category (each family of risk), by framework (each framework a scope the person may see is held to, with how much of what applies is verified or in place), by third party (those in the two highest tiers, with their next review and the sharing no agreement covers), and issues by root cause, source, and age, with twelve months raised and closed. Each figure is `reporting.count` over the list's own conditions for the person, with the list's path and filters; rows with nothing in them are left out. New list filters make each figure openable: risks `added`, issues `raised` and `closed` (each `FROM..TO`, both days counted), issues `root_cause` and `framework`, and exceptions `framework`. **Reports → Portfolio** is open to everyone, counting only what each may see. The acceptance test is `tests/test_portfolio.py::test_every_figure_opens_exactly_the_records_it_counts`, which opens every figure of every view and period as three roles.

### Slice 3: Leadership report ☐

**Goal:** a report given once, and reopened exactly as it was.

- [ ] A periodic report of top risks, movement since the last, appetite, posture by framework, third parties, and overdue items
- [ ] Issued, it is frozen as a snapshot with a fingerprint, and reopens unchanged whatever has happened since

**Acceptance:** a report reopened after the register has changed shows what it showed when issued, and its fingerprint verifies.

### Slice 4: As of ☐

- [ ] Any record, and the register, as it stood on a chosen date, rebuilt from the history

### Slice 5: Dossier and open formats ☐

- [ ] A complete, verifiable package for a scope, a risk, or a third party; export in the open assessment language; the security plan document

### Slice 6: Scenarios and ranges ☐

- [ ] Scenarios; estimates in ranges with simulation; the bow-tie view

### Slice 7: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.5.0 on both databases, audits, release, and the site republished

## Notes

- A measure is defined once, in code, as the same condition a list uses, so a figure and the list behind it cannot disagree (RPT-04).
- A snapshot records the organization's figure for each measure on a day. It is bookkeeping, not history: it is not in the hash chain, and it can be taken again.
