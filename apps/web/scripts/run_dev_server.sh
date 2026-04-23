#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SENTRY_BRIDGE_WEB_HOST:-127.0.0.1}"
PORT="${SENTRY_BRIDGE_WEB_PORT:-4173}"

if [[ -n "${SENTRY_BRIDGE_ENV_BIN:-}" && -x "${SENTRY_BRIDGE_ENV_BIN}/npm" ]]; then
  NPM_BIN="${SENTRY_BRIDGE_ENV_BIN}/npm"
else
  NPM_BIN="$(command -v npm || true)"
fi

if [[ -z "${NPM_BIN:-}" ]]; then
  echo "npm was not found. Put it on PATH or set SENTRY_BRIDGE_ENV_BIN." >&2
  exit 1
fi

cd "${ROOT_DIR}"
echo "Starting SENTRY Bridge Web dev server..."
echo "Expected local URL: http://${HOST}:${PORT}"
exec "${NPM_BIN}" run dev -- --host "${HOST}" --port "${PORT}"
