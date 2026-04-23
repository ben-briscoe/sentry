from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Coordinate( BaseModel ):
    lon: float
    lat: float
    alt_m: float = 0.0


class RenderBoxDimensions( BaseModel ):
    length_m: float
    width_m: float
    height_m: float


class RenderStructure( BaseModel ):
    id: str
    kind: Literal[ "building", "barrier", "tower" ] = "building"
    label: str
    center: Coordinate
    dimensions_m: RenderBoxDimensions
    heading_deg: float = 0.0
    color: str | None = None


class RenderScene( BaseModel ):
    id: str
    description: str
    base: Coordinate
    patrol_area: list[ Coordinate ]
    patrol_route: list[ Coordinate ]
    incursion_route: list[ Coordinate ]
    structures: list[ RenderStructure ] = Field( default_factory=list )


class RenderEntityState( BaseModel ):
    label: str
    position: Coordinate
    speed_mps: float | None = None
    spotlight_on: bool = False
    speaker_on: bool = False


class RenderIncursionState( BaseModel ):
    label: str = "Incursion"
    position: Coordinate | None = None
    active: bool = False
    radius_m: float = 14.0


class RenderState( BaseModel ):
    vehicle: RenderEntityState
    incursion: RenderIncursionState


class MissionState( BaseModel ):
    session_id: str
    step_index: int
    time_ms: float | None = None
    mission_mode: str | None = None
    mission_time_s: float | None = None
    real_time: bool | None = None
    playback_speed: float | None = None
    simulation_rate_hz: float | None = None
    current_speed_mps: float | None = None
    current_propulsion_power_w: float | None = None
    current_total_power_w: float | None = None
    current_load_w: float | None = None
    remaining_energy_j: float | None = None
    distance_to_base_m: float | None = None
    distance_to_perimeter_m: float | None = None
    patrol_distance_remaining_m: float | None = None
    track_time_remaining_s: float | None = None
    tier1_engagement_time_remaining_s: float | None = None
    attributes: dict[ str, Any ] = Field( default_factory=dict )


class ModeledMissionSnapshot( BaseModel ):
    time_ms: float | None = None
    mission_mode: str | None = None
    mission_time_s: float | None = None
    real_time: bool | None = None
    playback_speed: float | None = None
    simulation_rate_hz: float | None = None
    current_speed_mps: float | None = None
    current_propulsion_power_w: float | None = None
    current_total_power_w: float | None = None
    current_load_w: float | None = None
    remaining_energy_j: float | None = None
    distance_to_base_m: float | None = None
    distance_to_perimeter_m: float | None = None
    patrol_distance_remaining_m: float | None = None
    track_time_remaining_s: float | None = None
    tier1_engagement_time_remaining_s: float | None = None
    flight_feasible: bool | None = None
    endurance_feasible: bool | None = None
    configuration_suitable: bool | None = None
    low_battery_triggered: bool | None = None
    returned_early: bool | None = None
    mission_complete: bool | None = None
    attributes: dict[ str, Any ] = Field( default_factory=dict )


class CreateSessionRequest( BaseModel ):
    mode: Literal[ "replay", "live" ] = "replay"
    trace_csv: str = Field( description="Path to a single-run trace CSV for replay mode." )
    scene_profile: str = "reference_mission_v1"


class SessionCreated( BaseModel ):
    session_id: str
    mode: str
    trace_csv: str
    scene_profile: str


class ReplayTraceDescriptor( BaseModel ):
    name: str
    path: str
    rows_hint: int | None = None
    terminal_mode: str | None = None
    duration_ms: float | None = None
    recommended: bool = False


class InitializeResponse( BaseModel ):
    session_id: str
    mode: str
    trace_csv: str
    scene: RenderScene
    render_state: RenderState
    total_steps: int
    state: MissionState


class StepRequest( BaseModel ):
    step_count: int = Field( default=1, ge=1, le=100 )


class StepResponse( BaseModel ):
    session_id: str
    total_steps: int
    render_state: RenderState
    state: MissionState
    done: bool


class TerminateResponse( BaseModel ):
    session_id: str
    terminated: bool


class RoutePlanRequest( BaseModel ):
    kind: Literal[ "patrol_loop", "recall", "intercept", "track" ]
    start: Coordinate | None = None
    end: Coordinate | None = None
    patrol_area: list[ Coordinate ] = Field( default_factory=list )
    target_route: list[ Coordinate ] = Field( default_factory=list )
    ownship_speed_mps: float = Field( default=8.0, gt=0.0 )
    target_speed_mps: float = Field( default=4.0, gt=0.0 )
    patrol_inset_ratio: float = Field( default=0.15, ge=0.0, le=0.45 )
    route_offset_m: float = Field( default=35.0, ge=0.0 )


class RoutePlanResponse( BaseModel ):
    kind: str
    waypoints: list[ Coordinate ]
    note: str
    estimated_distance_m: float | None = None
    estimated_duration_s: float | None = None
    intercept_point: Coordinate | None = None


class MissionServiceSnapshot( BaseModel ):
    session_id: str
    scene: RenderScene
    sentry_position: Coordinate
    sentry_speed_mps: float
    active_route_kind: str | None = None
    active_route: list[ Coordinate ] = Field( default_factory=list )
    patrol_assigned: bool = False
    recall_active: bool = False
    escalation_authorized: bool = False
    incursion_active: bool = True
    incursion_position: Coordinate | None = None
    incursion_route: list[ Coordinate ] = Field( default_factory=list )
    incursion_speed_mps: float = 4.0
    last_event: str | None = None
    notes: list[ str ] = Field( default_factory=list )


class MissionServiceSessionSummary( BaseModel ):
    session_id: str
    mission_mode: str | None = None
    mission_complete: bool | None = None
    last_event: str | None = None


class MissionBridgeState( BaseModel ):
    pending_command_kind: str | None = None
    pending_command_note: str | None = None
    pending_real_time: bool | None = None
    pending_playback_speed: float | None = None
    command_revision: int = 0
    command_revision_applied: int = 0
    route_revision: int = 0
    route_revision_applied: int = 0


class MissionServiceSessionView( BaseModel ):
    snapshot: MissionServiceSnapshot
    modeled_state: ModeledMissionSnapshot | None = None
    render_state: RenderState
    bridge_state: MissionBridgeState


class MissionBridgeAckRequest( BaseModel ):
    command_revision_applied: int | None = Field( default=None, ge=0 )
    route_revision_applied: int | None = Field( default=None, ge=0 )
    note: str | None = None


class MissionBridgeAckResponse( BaseModel ):
    session_id: str
    bridge_state: MissionBridgeState
    note: str


class MissionServiceCreateRequest( BaseModel ):
    scene_profile: str = "reference_mission_v1"
    base: Coordinate | None = None
    patrol_area: list[ Coordinate ] = Field( default_factory=list )
    patrol_route: list[ Coordinate ] = Field( default_factory=list )
    incursion_route: list[ Coordinate ] = Field( default_factory=list )
    sentry_position: Coordinate | None = None
    sentry_speed_mps: float = Field( default=8.0, gt=0.0 )
    incursion_speed_mps: float = Field( default=4.0, gt=0.0 )


class MissionCommandRequest( BaseModel ):
    kind: Literal[
        "assign_patrol",
        "recall",
        "authorize_tier1",
        "clear_recall",
        "resume_patrol",
        "intercept_incursion",
        "set_playback_speed",
    ]
    current_position: Coordinate | None = None
    patrol_area: list[ Coordinate ] = Field( default_factory=list )
    target_route: list[ Coordinate ] = Field( default_factory=list )
    sentry_speed_mps: float | None = Field( default=None, gt=0.0 )
    playback_speed: float | None = Field( default=None, gt=0.0 )
    real_time: bool | None = None


class MissionCommandResponse( BaseModel ):
    session_id: str
    applied: bool
    command: str
    snapshot: MissionServiceSnapshot
    route_plan: RoutePlanResponse | None = None
    note: str


class MissionPerturbationRequest( BaseModel ):
    kind: Literal[ "incursion_spawn", "route_deviation", "incursion_speed_change", "all_clear" ]
    route: list[ Coordinate ] = Field( default_factory=list )
    offset_m: float = Field( default=30.0, ge=0.0 )
    direction: Literal[ "left", "right" ] = "right"
    speed_mps: float | None = Field( default=None, gt=0.0 )


class MissionPerturbationResponse( BaseModel ):
    session_id: str
    applied: bool
    perturbation: str
    snapshot: MissionServiceSnapshot
    route_plan: RoutePlanResponse | None = None
    note: str


class MissionSyncRequest( BaseModel ):
    modeled_state: ModeledMissionSnapshot


class MissionSyncResponse( BaseModel ):
    session_id: str
    modeled_state: ModeledMissionSnapshot
    snapshot: MissionServiceSnapshot
    recommended_route: RoutePlanResponse | None = None
    suggested_command: str | None = None
    note: str
