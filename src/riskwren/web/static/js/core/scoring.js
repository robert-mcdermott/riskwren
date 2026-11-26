// The arithmetic of a scoring method, for live previews. The server does the same sums and
// is the authority (riskwren/core/scoring.py); tests/fixtures/scoring-cases.json holds the
// cases both must pass. Data in, data out: nothing here touches the page.

export const AXES = ["likelihood", "impact"];

export function levels(method, axis) {
  return (axis === "likelihood" ? method.likelihood : method.impact_levels).map((level) => level.level);
}

export function ratingKeys(method) {
  return method.ratings.map((rating) => rating.key);
}

/** Where a rating sits among the method's ratings, from 1. Zero if it is not one of them. */
export function position(method, rating) {
  return ratingKeys(method).indexOf(rating) + 1;
}

/** Where the rating at `place` of `count` sits on the five-step color ramp. */
export function rampLevel(place, count) {
  if (!place) return 0;
  if (count <= 1) return 5;
  return Math.floor(1 + ((place - 1) * 4) / (count - 1) + 0.5);
}

/** The highest level rated on any dimension, or null when none is. */
export function overallImpact(impactLevels) {
  const rated = Object.values(impactLevels ?? {}).filter(Boolean);
  return rated.length ? Math.max(...rated) : null;
}

/** The rating for a likelihood and an overall impact, by looking up the matrix. */
export function rating(method, likelihood, impact) {
  if (!levels(method, "likelihood").includes(likelihood) || !levels(method, "impact").includes(impact)) {
    throw new RangeError("That is not a level of this scoring method.");
  }
  return method.matrix[impact - 1][likelihood - 1];
}

/** Whether a rating is above an appetite. With either unknown, nothing is exceeded. */
export function exceeds(method, ratingKey, appetite) {
  if (!ratingKey || !appetite) return false;
  return position(method, ratingKey) > position(method, appetite);
}

/** What is known about a control, as one word. Unknown counts for nothing. */
export function controlState(design, operation, { stale = false } = {}) {
  const unknown = (value) => value == null || value === "not_assessed";
  if (stale) return "stale";
  if (unknown(design) || unknown(operation)) return "not_assessed";
  if (design === "ineffective" || operation === "ineffective") return "ineffective";
  if (design === "partly" || operation === "partly") return "partly";
  return "effective";
}

export function strength(method, state) {
  return Number(method.control_effect.strength[state === "stale" ? "not_assessed" : state] ?? 0);
}

/** The residual rating the controls suggest, with its working. */
export function suggest(method, likelihood, impact, controls) {
  const effect = method.control_effect;
  const totals = { likelihood: 0, impact: 0 };
  const lines = controls.map((control) => {
    const state = controlState(control.design, control.operation, { stale: Boolean(control.stale) });
    const power = strength(method, state);
    const weight = Number(effect.reliance[control.reliance] ?? 0);
    for (const axis of AXES) {
      if (control.reduces === axis || control.reduces === "both") totals[axis] += power * weight;
    }
    const line = { reduces: control.reduces ?? null, reliance: control.reliance ?? null, state, strength: power, weight, counts: power * weight };
    for (const key of ["ref", "name"]) if (key in control) line[key] = control[key];
    return line;
  });
  const start = { likelihood, impact };
  const steps = {};
  const after = {};
  for (const axis of AXES) {
    const down = Math.min(effect.limit, Math.floor(totals[axis] + 1e-9));
    after[axis] = Math.max(1, start[axis] - down);
    steps[axis] = start[axis] - after[axis];
  }
  return {
    likelihood: after.likelihood,
    impact: after.impact,
    rating: rating(method, after.likelihood, after.impact),
    from: { ...start, rating: rating(method, likelihood, impact) },
    totals,
    steps,
    limit: effect.limit,
    controls: lines,
  };
}
