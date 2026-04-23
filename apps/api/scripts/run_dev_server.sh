#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SENTRY_BRIDGE_HOST:-0.0.0.0}"
PORT="${SENTRY_BRIDGE_PORT:-8000}"

if [[ -n "${SENTRY_BRIDGE_ENV_BIN:-}" && -x "${SENTRY_BRIDGE_ENV_BIN}/uvicorn" ]]; then
  UVICORN_BIN="${SENTRY_BRIDGE_ENV_BIN}/uvicorn"
else
  UVICORN_BIN="$(command -v uvicorn || true)"
fi

if [[ -z "${UVICORN_BIN:-}" ]]; then
  echo "uvicorn was not found. Put it on PATH or set SENTRY_BRIDGE_ENV_BIN." >&2
  exit 1
fi

cd "${ROOT_DIR}"
echo "Starting SENTRY Bridge API..."
echo "Expected local URL: http://${HOST}:${PORT}"
echo "API docs: http://${HOST}:${PORT}/api/docs"
exec "${UVICORN_BIN}" app.main:app --host "${HOST}" --port "${PORT}" --reload
