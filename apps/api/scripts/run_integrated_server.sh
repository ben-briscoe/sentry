#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/../.." && pwd)"
HOST="${SENTRY_BRIDGE_HOST:-127.0.0.1}"
PORT="${SENTRY_BRIDGE_PORT:-8000}"
SPA_DIR="${SENTRY_BRIDGE_SPA_DIR:-${REPO_ROOT}/release/web}"

if [[ -n "${SENTRY_BRIDGE_ENV_BIN:-}" && -x "${SENTRY_BRIDGE_ENV_BIN}/python" ]]; then
  PYTHON_BIN="${SENTRY_BRIDGE_ENV_BIN}/python"
else
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "Python 3 was not found. Put it on PATH or set SENTRY_BRIDGE_ENV_BIN." >&2
  exit 1
fi

echo "Starting integrated SENTRY server..."
echo "API + SPA URL: http://${HOST}:${PORT}"
echo "API docs: http://${HOST}:${PORT}/api/docs"
echo "SPA directory: ${SPA_DIR}"

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" -m app.main --host "${HOST}" --port "${PORT}" --spa-dir "${SPA_DIR}"
