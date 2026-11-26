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

export function date(value) {
  return value ? DATE.format(new Date(value)) : "";
}

export function greeting(now = new Date()) {
  const hour = now.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}
