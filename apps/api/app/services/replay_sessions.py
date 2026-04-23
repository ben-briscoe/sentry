from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.schemas import (
    MissionState,
    RenderScene,
    ReplayTraceDescriptor,
    SessionCreated,
)
from app.services.mission_projection import ReferenceMetrics
from app.services.rendering import build_render_state_for_modeled
from app.services.reference_scene import build_reference_scene


TRACE_FIELD_MAP = {
    "time(ms)": "time_ms",
    "currentMissionMode": "mission_mode",
    "missionTime": "mission_time_s",
    "currentSpeed": "current_speed_mps",
    "currentPropulsionPower": "current_propulsion_power_w",
    "currentTotalPower": "current_total_power_w",
    "currentLoad": "current_load_w",
    "sentry.payload.currentLoad": "current_load_w",
    "remainingScenarioEnergy": "remaining_energy_j",
    "distanceToBaseRemaining": "distance_to_base_m",
    "distanceToPerimeterRemaining": "distance_to_perimeter_m",
    "patrolDistanceRemaining": "patrol_distance_remaining_m",
    "trackTimeRemaining": "track_time_remaining_s",
    "tier1EngagementTimeRemaining": "tier1_engagement_time_remaining_s",
}

REPO_ROOT = Path( __file__ ).resolve().parents[ 4 ]

DEFAULT_TRACE_DIRS = [
    REPO_ROOT,
    REPO_ROOT / "trace_splits",
    REPO_ROOT / "release" / "trace_splits",
]

def _coerce_value( value: str ) -> Any:
    text = value.strip()
    if text == "":
        return None
    lower = text.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return float( text )
    except ValueError:
        return text


def _read_trace_rows( trace_csv: str ) -> list[ dict[ str, Any ] ]:
    path = Path( trace_csv ).expanduser().resolve()
    if not path.exists():
        raise HTTPException( status_code=404, detail=f"Trace CSV not found: {path}" )
    with path.open( newline="", encoding="utf-8-sig" ) as handle:
        reader = csv.DictReader( handle )
        rows = [ { key: _coerce_value( value or "" ) for key, value in row.items() } for row in reader ]
    if not rows:
        raise HTTPException( status_code=400, detail=f"Trace CSV has no data rows: {path}" )
    return rows


def list_trace_candidates( root: str | None = None ) -> list[ ReplayTraceDescriptor ]:
    roots = [ Path( root ).expanduser().resolve() ] if root else DEFAULT_TRACE_DIRS
    descriptors: list[ ReplayTraceDescriptor ] = []
    seen: set[ str ] = set()
    for base in roots:
        if not base.exists():
            continue
        candidates = sorted( base.glob( "*.csv" ) )
        for candidate in candidates:
            if candidate.name.endswith( "_split_metadata.csv" ):
                continue
            if "trace" not in candidate.name.lower():
                continue
            resolved = str( candidate.resolve() )
            if resolved in seen:
                continue
            seen.add( resolved )
            rows_hint, terminal_mode, duration_ms = _probe_trace_candidate( candidate )
            descriptors.append(
                ReplayTraceDescriptor(
                    name=candidate.name,
                    path=resolved,
                    rows_hint=rows_hint,
                    terminal_mode=terminal_mode,
                    duration_ms=duration_ms,
                )
            )
    descriptors.sort( key=_trace_priority )
    if descriptors:
        descriptors[ 0 ].recommended = True
    return descriptors


def _probe_trace_candidate( candidate: Path ) -> tuple[ int | None, str | None, float | None ]:
    rows_hint: int | None = None
    terminal_mode: str | None = None
    duration_ms: float | None = None
    try:
        with candidate.open( newline="", encoding="utf-8-sig" ) as handle:
            reader = csv.DictReader( handle )
            rows_hint = 0
            last_row: dict[ str, Any ] | None = None
            for row in reader:
                rows_hint += 1
                last_row = row
            if last_row is not None:
                terminal_mode = last_row.get( "currentMissionMode" ) or None
                duration_raw = _coerce_value( last_row.get( "time(ms)", "" ) )
                if isinstance( duration_raw, float ):
                    duration_ms = duration_raw
    except OSError:
        return None, None, None
    return rows_hint, terminal_mode, duration_ms


def _trace_priority( descriptor: ReplayTraceDescriptor ) -> tuple[ int, int, float, str ]:
    terminal_rank = 0
    if descriptor.terminal_mode == "MISSION_SUCCESS":
        terminal_rank = 2
    elif descriptor.terminal_mode == "MISSION_FAIL":
        terminal_rank = 1
    return (
        -terminal_rank,
        -( descriptor.rows_hint or 0 ),
        -( descriptor.duration_ms or 0.0 ),
        descriptor.name,
    )


def _build_state( session_id: str, step_index: int, row: dict[ str, Any ] ) -> MissionState:
    state_fields: dict[ str, Any ] = {
        "session_id": session_id,
        "step_index": step_index,
        "attributes": dict( row ),
    }
    for source_name, target_name in TRACE_FIELD_MAP.items():
        state_fields[ target_name ] = row.get( source_name )
    return MissionState( **state_fields )


def _first_numeric_value( rows: list[ dict[ str, Any ] ], key: str ) -> float | None:
    for row in rows:
        value = row.get( key )
        if isinstance( value, float ):
            return value
    return None


def _build_reference_metrics( rows: list[ dict[ str, Any ] ] ) -> ReferenceMetrics:
    return ReferenceMetrics(
        distance_to_base_start_m=_first_numeric_value( rows, "distanceToBaseRemaining" ),
        distance_to_perimeter_start_m=_first_numeric_value( rows, "distanceToPerimeterRemaining" ),
        patrol_distance_start_m=_first_numeric_value( rows, "patrolDistanceRemaining" ),
        track_time_start_s=_first_numeric_value( rows, "trackTimeRemaining" ),
        tier1_engagement_start_s=_first_numeric_value( rows, "tier1EngagementTimeRemaining" ),
    )


@dataclass
class ReplaySession:
    session_id: str
    mode: str
    trace_csv: str
    scene: RenderScene
    rows: list[ dict[ str, Any ] ]
    reference: ReferenceMetrics
    current_index: int = 0

    @property
    def total_steps( self ) -> int:
        return len( self.rows )

    def current_state( self ) -> MissionState:
        return _build_state( self.session_id, self.current_index, self.rows[ self.current_index ] )

    def current_render_state( self ) -> RenderState:
        state = self.current_state()
        return build_render_state_for_modeled(
            self.scene,
            state,
            self.reference,
            incursion_active=True,
        )

    def advance( self, step_count: int ) -> MissionState:
        self.current_index = min( self.current_index + step_count, self.total_steps - 1 )
        return self.current_state()


class ReplaySessionStore:
    def __init__( self ) -> None:
        self._sessions: dict[ str, ReplaySession ] = {}

    def create_session( self, trace_csv: str, mode: str = "replay" ) -> SessionCreated:
        session_id = str( uuid.uuid4() )
        rows = _read_trace_rows( trace_csv )
        session = ReplaySession(
            session_id=session_id,
            mode=mode,
            trace_csv=str( Path( trace_csv ).expanduser().resolve() ),
            scene=build_reference_scene(),
            rows=rows,
            reference=_build_reference_metrics( rows ),
        )
        self._sessions[ session_id ] = session
        return SessionCreated(
            session_id=session.session_id,
            mode=session.mode,
            trace_csv=session.trace_csv,
            scene_profile=session.scene.id,
        )

    def get( self, session_id: str ) -> ReplaySession:
        session = self._sessions.get( session_id )
        if session is None:
            raise HTTPException( status_code=404, detail=f"Unknown session: {session_id}" )
        return session

    def terminate( self, session_id: str ) -> bool:
        return self._sessions.pop( session_id, None ) is not None


store = ReplaySessionStore()
