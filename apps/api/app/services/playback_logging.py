from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path( __file__ ).resolve().parents[4]
LOG_DIR = REPO_ROOT / "runtime_logs"
LOG_PATH = LOG_DIR / "live_playback.jsonl"
LOGGER_NAME = "sentry.live_playback"


def playback_log_path() -> Path:
    return LOG_PATH


def log_live_playback( event: str, **payload: Any ) -> None:
    if not _logging_enabled():
        return
    logger = _logger()
    record = {
        "event": event,
        "timestamp_utc": datetime.now( timezone.utc ).isoformat(),
        **_normalize_value( payload ),
    }
    logger.info( json.dumps( record, separators=( ",", ":" ), sort_keys=True ) )


def _logger() -> logging.Logger:
    logger = logging.getLogger( LOGGER_NAME )
    if logger.handlers:
        return logger

    LOG_DIR.mkdir( parents=True, exist_ok=True )
    logger.setLevel( logging.INFO )
    handler = logging.FileHandler( LOG_PATH, encoding="utf-8", mode="w" )
    handler.setFormatter( logging.Formatter( "%(message)s" ) )
    logger.addHandler( handler )
    logger.propagate = False
    return logger


def _logging_enabled() -> bool:
    value = os.environ.get( "SENTRY_ENABLE_PLAYBACK_LOG", "" ).strip().lower()
    return value in { "1", "true", "yes", "on" }


def _normalize_value( value: Any ) -> Any:
    if isinstance( value, dict ):
        return { key: _normalize_value( nested ) for key, nested in value.items() }
    if isinstance( value, ( list, tuple ) ):
        return [ _normalize_value( item ) for item in value ]
    if hasattr( value, "model_dump" ):
        return _normalize_value( value.model_dump() )
    if hasattr( value, "__dict__" ) and value.__class__.__module__.startswith( "app." ):
        return _normalize_value( value.__dict__ )
    if isinstance( value, float ):
        return round( value, 6 )
    return value
