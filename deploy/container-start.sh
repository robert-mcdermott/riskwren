#!/bin/sh
# Set the installation up on its first start, then run what was asked (the server, by default).
set -eu
if [ ! -f "$RISKWREN_CONFIG" ]; then
  if [ -n "${RISKWREN_ADMIN_EMAIL:-}" ] && [ -n "${RISKWREN_ADMIN_PASSWORD:-}" ]; then
    printf '%s' "$RISKWREN_ADMIN_PASSWORD" | riskwren init --admin-email "$RISKWREN_ADMIN_EMAIL" \
      --admin-name "${RISKWREN_ADMIN_NAME:-Administrator}" --password-stdin \
      ${RISKWREN_PROGRAM:+--program "$RISKWREN_PROGRAM"}
  else
    riskwren init ${RISKWREN_PROGRAM:+--program "$RISKWREN_PROGRAM"} < /dev/null
  fi
else
  riskwren db upgrade
fi
unset RISKWREN_ADMIN_PASSWORD
exec "$@"
