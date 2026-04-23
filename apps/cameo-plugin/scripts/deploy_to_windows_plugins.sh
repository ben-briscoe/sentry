#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${DIST_DIR:-${ROOT_DIR}/target/plugin-dist/sentry-cameo-bridge}"
WINDOWS_LOCALAPPDATA_DEFAULT="$(/mnt/c/Windows/System32/cmd.exe /c echo %LOCALAPPDATA% 2>/dev/null | tr -d '\r')"
if [[ -n "${WINDOWS_LOCALAPPDATA_DEFAULT}" ]] && command -v wslpath >/dev/null 2>&1; then
  WINDOWS_LOCALAPPDATA_DEFAULT="$(wslpath "${WINDOWS_LOCALAPPDATA_DEFAULT}")"
fi
PLUGINS_DIR="${WINDOWS_MSOSA_PLUGINS_DIR:-${WINDOWS_LOCALAPPDATA_DEFAULT}/.magic.systems.of.systems.architect/2022x/plugins}"
TARGET_DIR="${PLUGINS_DIR}/sentry-cameo-bridge"

if [[ ! -d "${DIST_DIR}" ]]; then
  echo "Plugin distribution not found at ${DIST_DIR}" >&2
  echo "Build it first with scripts/build_plugin_dist.sh" >&2
  exit 1
fi

mkdir -p "${PLUGINS_DIR}"
mkdir -p "${TARGET_DIR}"
cp -f "${DIST_DIR}/plugin.xml" "${TARGET_DIR}/plugin.xml"
cp -f "${DIST_DIR}/sentry-cameo-bridge.jar" "${TARGET_DIR}/sentry-cameo-bridge.jar"

echo "Deployed plugin to ${TARGET_DIR}"
