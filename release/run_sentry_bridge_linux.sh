#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="${ROOT_DIR}/apps/api"
SPA_DIR="${ROOT_DIR}/release/web"

if [[ -n "${SENTRY_BRIDGE_ENV_BIN:-}" && -x "${SENTRY_BRIDGE_ENV_BIN}/python" ]]; then
  PYTHON_BIN="${SENTRY_BRIDGE_ENV_BIN}/python"
else
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "Python 3 was not found. Put it on PATH or set SENTRY_BRIDGE_ENV_BIN." >&2
  exit 1
fi

cd "${API_DIR}"
exec "${PYTHON_BIN}" -m app.main --host 127.0.0.1 --port 8000 --spa-dir "${SPA_DIR}" "$@"
