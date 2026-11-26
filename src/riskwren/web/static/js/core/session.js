// Who is signed in, and what they may do (from GET /api/v1/session).

let current = null;

export function setSession(value) {
  current = value;
}

export function session() {
  return current;
}

/** permission: "admin", "govern", "configure", "read_all", "edit_all", "review", "steward". */
export function can(permission) {
  return Boolean(current?.permissions?.[permission]);
}

export function csrfToken() {
  return current?.csrf_token ?? null;
}
