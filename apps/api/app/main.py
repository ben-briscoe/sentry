from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.health import router as health_router
from app.routes.mission import router as mission_router
from app.routes.replays import router as replay_router
from app.routes.route_plan import router as route_plan_router
from app.routes.simulation import router as simulation_router
from app.routes.spa import register_spa


def create_app(*, spa_dir: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="SENTRY Bridge API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router( health_router )
    app.include_router( mission_router )
    app.include_router( replay_router )
    app.include_router( simulation_router )
    app.include_router( route_plan_router )

    if spa_dir is not None:
        register_spa(app, spa_dir)
    else:
        @app.get("/")
        def root() -> dict[str, str]:
            return {
                "service": "SENTRY Bridge API",
                "status": "ok",
                "docs": "/api/docs",
                "note": "This port serves the bridge API. The browser UI runs on the Vite dev/build host, not on the API root unless a built SPA is staged and passed with --spa-dir.",
            }

    return app


app = create_app()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SENTRY bridge API and optionally serve the built SPA.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--spa-dir", type=Path, default=None)
    parser.add_argument("--reload", action="store_true")
    return parser.parse_args()


def main() -> None:
    import uvicorn

    args = parse_args()
    uvicorn.run(create_app(spa_dir=args.spa_dir), host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
