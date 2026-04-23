from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles


router = APIRouter()


def _spa_dir(request: Request) -> Path:
    spa_dir = getattr(request.app.state, "spa_dist_dir", None)
    if spa_dir is None:
        raise HTTPException(status_code=404, detail="SPA not configured.")
    return Path(spa_dir)


def _file_response(path: Path, *, cache_control: str | None = None) -> Response:
    media_type, _ = mimetypes.guess_type(str(path))
    response = Response(content=path.read_bytes(), media_type=media_type or "application/octet-stream")
    if cache_control is not None:
        response.headers["Cache-Control"] = cache_control
    return response


def _index_response(spa_dir: Path) -> HTMLResponse:
    response = HTMLResponse(content=(spa_dir / "index.html").read_text(encoding="utf-8"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _resolve_spa_file(spa_dir: Path, resource_path: str) -> Path | None:
    if resource_path == "":
        return None

    candidate = (spa_dir / resource_path).resolve()
    try:
        candidate.relative_to(spa_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Invalid SPA resource path.") from exc

    if candidate.exists() and candidate.is_file():
        return candidate

    return None


@router.get("/")
async def index(request: Request) -> HTMLResponse:
    return _index_response(_spa_dir(request))


@router.get("/{resource_path:path}")
async def spa_entry(request: Request, resource_path: str) -> Response:
    if resource_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not Found")

    spa_dir = _spa_dir(request)
    resolved_file = _resolve_spa_file(spa_dir, resource_path)

    if resolved_file is not None:
        return _file_response(resolved_file, cache_control="public, max-age=3600")

    return _index_response(spa_dir)


def register_spa(app: FastAPI, spa_dir: Path) -> None:
    spa_dir = Path(spa_dir).resolve()
    index_path = spa_dir / "index.html"

    if not index_path.exists():
        raise RuntimeError(f"SPA index file not found: {index_path}")

    app.state.spa_dist_dir = spa_dir

    assets_dir = spa_dir / "assets"
    cesium_dir = spa_dir / "cesium"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

    if cesium_dir.exists():
        app.mount("/cesium", StaticFiles(directory=cesium_dir), name="spa-cesium")

    app.include_router(router)
