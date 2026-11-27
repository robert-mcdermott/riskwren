// The one condition language, in the browser. This is the twin of riskwren/core/conditions.py:
// both must pass the cases in tests/fixtures/conditions-cases.json. The server's answer is the one
// that counts; this one lets a form show and hide questions, and react as it is filled in.

const MAX_DEPTH = 12;

export function lookup(context, path) {
  let current = context;
  for (const part of path.split(".")) {
    if (current === null || typeof current !== "object" || Array.isArray(current) || !Object.hasOwn(current, part)) {
      return null;
    }
    current = current[part];
  }
  return current ?? null;
}

function isEmpty(value) {
  if (value == null || value === "") return true;
  if (Array.isArray(value)) return value.length === 0;
  return typeof value === "object" && Object.keys(value).length === 0;
}

function asNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asList(value) {
  if (Array.isArray(value)) return value;
  return isEmpty(value) ? [] : [value];
}

function same(a, b) {
  if (a === b) return true;
  // Lists and objects are equal when they hold the same things, as they are in Python.
  if (a !== null && b !== null && typeof a === "object" && typeof b === "object") {
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);
    return keysA.length === keysB.length && keysA.every((key) => Object.hasOwn(b, key) && same(a[key], b[key]));
  }
  // Python treats true as 1 and false as 0; conditions are written with one or the other.
  if (typeof a === "boolean" && typeof b === "number") return Number(a) === b;
  if (typeof a === "number" && typeof b === "boolean") return a === Number(b);
  return false;
}

function has(list, item) {
  return list.some((entry) => same(entry, item));
}

function compare(op, actual, expected) {
  if (op === "empty") return isEmpty(actual);
  if (op === "answered") return !isEmpty(actual);
  if (op === "ne") return !same(actual, expected ?? null);
  if (op === "not_in") return !has(asList(expected), actual);
  if (isEmpty(actual)) return false;
  if (op === "eq") return same(actual, expected ?? null);
  if (op === "in") return has(asList(expected), actual);
  if (op === "contains") return has(asList(actual), expected);
  if (op === "contains_any") return asList(expected).some((item) => has(asList(actual), item));
  if (op === "contains_all") {
    const wanted = asList(expected);
    return wanted.length > 0 && wanted.every((item) => has(asList(actual), item));
  }
  const left = asNumber(actual);
  const right = asNumber(expected);
  if (left === null || right === null) return false;
  return { gt: left > right, gte: left >= right, lt: left < right, lte: left <= right }[op] ?? false;
}

/** Is the condition true of the context? No condition at all is true. */
export function evaluate(condition, context, depth = 0) {
  if (condition == null || Object.keys(condition).length === 0) return true;
  if (depth > MAX_DEPTH) return false;
  if ("all" in condition) return condition.all.every((part) => evaluate(part, context, depth + 1));
  if ("any" in condition) return condition.any.some((part) => evaluate(part, context, depth + 1));
  if ("not" in condition) return !evaluate(condition.not, context, depth + 1);
  return compare(condition.op, lookup(context, condition.field), condition.value);
}
