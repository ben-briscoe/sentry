# Surveilance & ENforcemenT Response sYstem (SENTRY)

INSY 6130 Team 15 project. SENTRY is a digital-engineering demonstration of a UAS that patrols a crowd-control perimeter, detects a boundary crossing, tracks the incursion, and escalates to visible/audible deterrence during the modeled mission timeline.

This repository is submission-oriented. It contains the SysML model, the bridge/server/browser stack, the Cameo plugin source, the parametric-sweep outputs, and the prebuilt runtime assets needed to run the browser-backed demo from Windows.

## Contents

- `SENTRY_INSY_6130_Team15.mdzip`
  Authoritative mission model used for the final demo.
- `launch_msosa_from_project_dir.cmd`
  Windows launcher for MSOSA with the project-specific logging configuration.
- `simulation-log4j2-fixed.xml`
  Logging override used by the launcher above.
- `apps/api`
  FastAPI bridge and mission-service source.
- `apps/web`
  React/Cesium browser source.
- `apps/cameo-plugin`
  Cameo/MSOSA plugin source.
- `release/web`
  Prebuilt browser bundle served by the Python API for the integrated demo.
- `release/plugins/sentry-cameo-bridge`
  Prebuilt plugin payload ready to copy into the MSOSA plugins directory.
- `sentry_parametric_sweep.csv`
  Parametric sweep summary output.
- `parametric_sweep_trace_metrics.csv`
  Parametric sweep trace output.
- `images/conops`
  Project imagery used in documentation/presentation material.

## Required Software

Minimum external dependencies:

- Windows:
  - MSOSA / Magic Systems of Systems Architect 2022x Refresh 2
  - Python 3.10+ for the bridge server
- Optional for rebuilding assets:
  - Node.js 20+
  - Java 11+
  - Maven 3.9+

Dependency manifests:

- Python runtime: `apps/api/requirements.txt`
- Python dev/test: `apps/api/requirements-dev.txt`
- Python project metadata: `apps/api/pyproject.toml`
- Web dependencies: `apps/web/package.json`
- Web lockfile: `apps/web/package-lock.json`
- Plugin build metadata: `apps/cameo-plugin/pom.xml`

## Run on Windows

1. Start the integrated Python server:

   ```bat
   run_sentry_bridge_windows.cmd
   ```

   That script creates `.venv-windows` on first run, installs `apps/api/requirements.txt`, and serves the prebuilt browser bundle from `release/web`.

2. Open the browser console at:

   ```text
   http://127.0.0.1:8000/
   ```

3. Deploy the prebuilt Cameo plugin if needed by copying:

   ```text
   release\plugins\sentry-cameo-bridge
   ```

   into:

   ```text
   %LOCALAPPDATA%\.magic.systems.of.systems.architect\2022x\plugins
   ```

4. Launch MSOSA with:

   ```text
   launch_msosa_from_project_dir.cmd
   ```

5. Open `SENTRY_INSY_6130_Team15.mdzip`, create a mission session from the SENTRY plugin menu, start live DRMAnalysis sync, and run the single open-loop DRMAnalysis mission.

## Rebuild Assets on Linux/WSL

Linux/WSL was the development environment. To rebuild the prebuilt browser bundle and Linux launcher:

```bash
cd /path/to/sentry
./buildit
```

That refreshes:

- `release/web`
- `release/run_sentry_bridge_linux.sh`
- `release/plugins/sentry-cameo-bridge` if a plugin build already exists under `apps/cameo-plugin/target/plugin-dist`

For Linux development servers:

- API dev server: `apps/api/scripts/run_dev_server.sh`
- Web dev server: `apps/web/scripts/run_dev_server.sh`
- Integrated server: `apps/api/scripts/run_integrated_server.sh`

## Notes

- This project contains AI-generated imagery in `images/conops`.
- The browser/server demo is intended to be self-contained inside this repository, with MSOSA as the only required external project-specific software.
- For Linux rebuilds, put `python3`, `npm`, and optionally `conda` on `PATH`, or set `SENTRY_BRIDGE_ENV_BIN` / `CONDA_BIN` / `MAGICDRAW_HOME` explicitly.
