// How evidence stands, and where a person may add it: small enough for pages that only show
// evidence, without the editor.

import { ownUnits, session } from "../core/session.js";
import { pill } from "./ui.js";

export const STATES = { current: ["Current", "ok"], expiring: ["Expires soon", "warn"], stale: ["No longer counts", "danger"] };

export const freshness = (state) => pill(STATES[state]?.[0] ?? state, STATES[state]?.[1] ?? "");

/** The units a person may add evidence for: where they work, and where they have a role. */
export function evidenceUnits() {
  const me = session();
  const kept = ownUnits();
  if (kept === null) return null;
  const scoped = Object.values(me.units ?? {});
  if (scoped.some((units) => units === null)) return null;
  return new Set([...kept, ...(me.member_units ?? []), ...scoped.flat()]);
}
