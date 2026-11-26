// Words, dates, and names.

export function initials(name) {
  const parts = String(name ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function plural(count, one, many = `${one}s`) {
  return `${count} ${count === 1 ? one : many}`;
}

export function titleCase(text) {
  return String(text ?? "").replace(/[_-]/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

const DATE = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

const DAY_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * A date as people write it. A day with no time (a due date, a review date) is that day
 * wherever the reader is: it is never shifted by their time zone. A moment is shown in it.
 */
export function date(value) {
  if (!value) return "";
  const day = DAY_ONLY.exec(String(value));
  return DATE.format(day ? new Date(Number(day[1]), Number(day[2]) - 1, Number(day[3])) : new Date(value));
}

export function greeting(now = new Date()) {
  const hour = now.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const STEPS = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];

/** "3 days ago", "in 2 weeks", "just now". */
export function relative(value, now = Date.now()) {
  if (!value) return "";
  const seconds = (new Date(value).getTime() - now) / 1000;
  for (const [unit, size] of STEPS) {
    if (Math.abs(seconds) >= size) return RELATIVE.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

const DATE_TIME = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function dateTime(value) {
  return value ? DATE_TIME.format(new Date(value)) : "";
}
