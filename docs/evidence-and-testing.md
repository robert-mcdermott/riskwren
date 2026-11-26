# Evidence and testing

This guide is for the people who collect proof that a control is done, and for those who test whether it works: control owners, assessors, and whoever leads an assessment. It covers evidence, its dates, files, assessments, tests, independence, and what a result changes.

## Evidence

An evidence item is something that shows a control is done. It is collected once and attached to everything it supports.

| Kind | What it is |
|---|---|
| **A file** | A report, an export, a screenshot, a signed form |
| **A link** | Where the proof lives in another system |
| **A note of what was seen** | What somebody looked at, and what they saw |
| **An attestation** | A named person's statement that something is so |

**Compliance → Evidence → Add evidence**, or **Add evidence** on a control or a scope, which attaches it there as it is made. Anyone may add evidence for a unit they work in, because the people who do the work hold the proof.

Every item has an owner, the date it was collected, the period it covers, a data class, and the date it **holds until**.

### Evidence stops counting

Evidence is true of a moment. An item holds for twelve months from the day it was collected unless you give another date, and it is in one of three states:

| State | Meaning |
|---|---|
| **Current** | It counts |
| **Expires soon** | It counts, and its date is within 30 days. Its owner sees it on Home |
| **No longer counts** | Its date has passed. It stays on the record, and counts toward nothing |

Stale evidence is never deleted and never quietly renewed. Collect it again and add a new item; the old one remains as what was true then.

### Attach it

An item counts once it is attached to the control it shows. On the item, **Supports → Edit** lists the controls and scopes it is attached to. One item can support many: the same restore log may be evidence for a backup control and for the scope that relies on it.

Putting evidence on a control or a scope is for those who keep or assess that control or scope. Collecting is open; attaching is not.

### Files

A file is checked by what it contains, not by its name. PDF, common images, Word, Excel, and PowerPoint documents, and plain text (including CSV and JSON) are taken, up to 25 MB. Programs are refused.

- Files are stored under the SHA-256 of their content, in the data home, in a directory the server does not serve from. The same file sent twice is kept once.
- A file only ever leaves as a download. A page or a drawing kept as evidence of a configuration is stored and returned as the plain text it is, so it cannot run in the browser.
- Every download is recorded in the item's history.

### Who sees evidence

Evidence is more closely held than the register. An item is seen by whoever collected it, those named on it, and those with a role over its unit. Others see it only through something it is attached to that they may see, and not at all if it is restricted or of the most sensitive data class. A person who cannot see a control cannot download its evidence.

## Assessments

An assessment is a planned look at whether a scope's controls work. **Compliance → Assessments → Start an assessment** (an assessor or a manager), or **Start an assessment** on a scope.

Give it a name, the scope, a period, and a lead. It plans a test for each control the scope does itself:

- every one of them; or
- with **Against** set to a framework, only those that answer a requirement of it that applies in the scope.

A control the scope inherits is not tested here. It is tested where it is provided, once, and the result reaches every scope that relies on it.

### Plan the tests

Each test has a **method** (examine records and settings, interview the people who do it, or test it and see), a **procedure**, and a person it is **assigned to**. **Plan** on a test changes them. A test that is assigned appears on that person's Home, due on the last day of the assessment's period.

### Record a result

**Record result** on a test:

- **Design**: would it reduce the risk, if it operated as described?
- **Operation**: does it operate as described?
- **What was looked at**: the sample, the period, the people asked.
- **What was found.** This is required.
- **Evidence**: cite the items that show it.

Each of design and operation is effective, partly effective, or ineffective. The control is as strong as the weaker of the two.

### Independence, and a second pair of eyes

Two rules always hold, and the server enforces both.

1. **Nobody records or reviews a result for a control they own.** The test is shown to them as theirs, with someone else to do it.
2. **A result counts only when a second person has confirmed it.** Whoever recorded it cannot confirm it.

Recording a result changes nothing. It waits, and the assessment's lead sees it on Home. **Review** then either confirms it or returns it with a note saying what needs another look. A returned result is recorded again; the earlier one stays in the assessment's history.

### What a confirmed result changes

Confirming a result does three things at once.

1. **It becomes the control's rating**, on the basis of a test, in the tester's name.
2. **It moves every requirement the control answers, in every scope that relies on it.** Effective, with evidence that still counts, makes them verified. Partly effective or ineffective makes them failing, in the scope that does the control and in every scope that inherits it.
3. **It moves the residual rating that the controls suggest for every risk the control reduces.** If the suggestion is now worse than the rating on record, the risk is flagged as in doubt and its owner is asked to assess again.

A result of partly effective or ineffective also opens an issue for the control's owners, filled in from the result. See [Issues and exceptions](issues-and-exceptions.md#from-a-failed-test).

While a test result holds, the control cannot be re-rated by judgment. Otherwise the quickest way to clear a failing test would be to have an opinion. A later test replaces it, and so does the passing of time: a result holds for as long as any rating does, twelve months by default.

### Finish

**Complete** closes an assessment once every test in it has a result that counts. A test that will not be done is taken out first. **Cancel it** abandons an assessment; results already confirmed still count.

The assessment's **History** tab tells every test planned, every result recorded, and every confirmation and return, with who did each.

## Verified, in practice

A requirement is verified when each control that answers it in the scope is in place, has a confirmed test result of effective that still holds, and has current evidence, either attached to the control or cited by that result.

So the working rhythm for a control owner and an assessor is:

1. The owner keeps the control's evidence current, renewing it before its date.
2. The assessor tests the control once a year and cites that evidence.
3. A second assessor confirms the result.

Miss the first and the requirement drops to in place when the evidence goes stale. Miss the second and it drops when the test is a year old. Neither needs anyone to notice: the scope's Requirements tab and the compliance dashboard say so the same day.
