#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAGICDRAW_HOME="${MAGICDRAW_HOME:-}"
CONDA="${CONDA_BIN:-$(command -v conda || true)}"
ENV_NAME="${SENTRY_BRIDGE_ENV:-sentry-bridge}"

if [[ -z "${MAGICDRAW_HOME}" ]]; then
  for candidate in \
    "/mnt/c/Program Files/Magic Systems of Systems Architect" \
    "/mnt/c/Program Files/No Magic/Cameo Systems Modeler" \
    "/mnt/c/Program Files/Cameo Systems Modeler"
  do
    if [[ -d "${candidate}" ]]; then
      MAGICDRAW_HOME="${candidate}"
      break
    fi
  done
fi

if [[ -z "${MAGICDRAW_HOME}" || ! -d "${MAGICDRAW_HOME}" ]]; then
  echo "Set MAGICDRAW_HOME to your MSOSA/Cameo install root before building the plugin." >&2
  exit 1
fi

if [[ -z "${CONDA}" ]]; then
  echo "conda was not found. Put it on PATH or set CONDA_BIN." >&2
  exit 1
fi

cd "${ROOT_DIR}"
"${CONDA}" run -n "${ENV_NAME}" mvn -Dmagicdraw.home="${MAGICDRAW_HOME}" package
