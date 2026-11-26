# ADR-0011: The arithmetic suggests; a named person judges

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

A register can obtain a residual rating in two ways. It can compute one from the inherent rating and the controls linked to the risk. Or it can ask a person. A computed rating is consistent and updates itself, but it invites people to add controls until the number is comfortable, and it claims a precision that the inputs do not have. A purely judged rating is honest about being a judgment, but it floats free of what is known about the controls, and it does not change when a control fails.

Separately, a register has to decide what a single color means. If red means both "a lot is at stake" and "something is wrong", a well-run program looks permanently alarming and a neglected low risk looks fine.

## Decision

- **Every rating is a judgment by a named person on a date, with a rationale.** Assessments are never edited, only superseded.
- **For a residual assessment the system offers a suggestion** worked out from the inherent rating and the known effectiveness of the linked controls, and shows its working. The assessor confirms it or departs from it with a reason. Both are kept.
- **Unknown counts for nothing.** A control that has not been assessed, or whose rating is older than its cadence, contributes no reduction, and the working says so.
- **There is a limit** on how far controls can lower either axis, so that a list of controls cannot argue a risk down to nothing.
- **The suggestion keeps being compared with the record.** When today's suggestion is worse than the residual rating on record, the risk is flagged and its owner asked to re-assess. The rating itself is not changed by the system.
- **Rating and standing are separate signals** with separate colors, marks, and words. Rating says how much is at stake; standing says whether the risk is within appetite, being treated, accepted, or in need of a decision.
- **Acceptance is a statement by a named person with the authority for that rating**, limited in time, and never by the risk's own owner.

## Consequences

- A register that an auditor can read as a series of attributable judgments, each with its reasons.
- A failed control reaches every risk that leaned on it without silently rewriting anyone's assessment.
- People must act on flags for ratings to stay current; campaigns and reminders (wave 3) exist for that.
- The arithmetic is simple enough to do by hand, which is the point: it has to be explainable on the screen.

## Alternatives

- **Residual computed and stored by the system:** consistent, but nobody owns the number.
- **Residual judged with no suggestion:** common in spreadsheets, and the reason control testing so rarely changes a risk rating.
- **Financial quantification as the default method:** valuable for a few risks and available later as an optional estimate; as the only method it excludes the consequences that matter most to mission-driven organizations.
