from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.schemas import (
    Coordinate,
    MissionBridgeAckRequest,
    MissionBridgeAckResponse,
    MissionBridgeState,
    MissionCommandRequest,
    MissionCommandResponse,
    MissionPerturbationRequest,
    MissionPerturbationResponse,
    MissionServiceCreateRequest,
    MissionServiceSnapshot,
    MissionServiceSessionSummary,
    MissionServiceSessionView,
    MissionSyncRequest,
    MissionSyncResponse,
    ModeledMissionSnapshot,
    RenderScene,
    RoutePlanRequest,
    RoutePlanResponse,
)

from .mission_projection import LiveMissionProjection, ReferenceMetrics
from .mission_mode import canonical_mission_mode, mode_contains
from .playback_logging import log_live_playback, playback_log_path
from .rendering import build_render_state
from .mission_routes import deviate_route, plan_route_request
from .reference_scene import build_reference_scene


def _build_scene( request: MissionServiceCreateRequest ) -> RenderScene:
    scene = build_reference_scene()
    if request.base is not None:
        scene.base = request.base
    if request.patrol_area:
        scene.patrol_area = request.patrol_area
    if request.patrol_route:
        scene.patrol_route = request.patrol_route
    if request.incursion_route:
        scene.incursion_route = request.incursion_route
    return scene


@dataclass
class MissionServiceSession:
    session_id: str
    scene: RenderScene
    sentry_position: Coordinate
    sentry_speed_mps: float
    incursion_route: list[ Coordinate ]
    incursion_speed_mps: float
    active_route_kind: str | None = None
    active_route: list[ Coordinate ] = field( default_factory=list )
    patrol_assigned: bool = False
    recall_active: bool = False
    escalation_authorized: bool = False
    incursion_active: bool = False
    incursion_position: Coordinate | None = None
    last_event: str | None = None
    notes: list[ str ] = field( default_factory=list )
    reference: ReferenceMetrics = field( default_factory=ReferenceMetrics )
    live_projection: LiveMissionProjection = field( default_factory=LiveMissionProjection )
    latest_modeled_state: ModeledMissionSnapshot | None = None
    pending_command_kind: str | None = None
    pending_command_note: str | None = None
    pending_real_time: bool | None = None
    pending_playback_speed: float | None = None
    command_revision: int = 0
    command_revision_applied: int = 0
    route_revision: int = 0
    route_revision_applied: int = 0

    def snapshot( self ) -> MissionServiceSnapshot:
        return MissionServiceSnapshot(
            session_id=self.session_id,
            scene=self.scene,
            sentry_position=self.sentry_position,
            sentry_speed_mps=self.sentry_speed_mps,
            active_route_kind=self.active_route_kind,
            active_route=list( self.active_route ),
            patrol_assigned=self.patrol_assigned,
            recall_active=self.recall_active,
            escalation_authorized=self.escalation_authorized,
            incursion_active=self.incursion_active,
            incursion_position=self.incursion_position,
            incursion_route=list( self.incursion_route ),
            incursion_speed_mps=self.incursion_speed_mps,
            last_event=self.last_event,
            notes=list( self.notes ),
        )

    def summary( self ) -> MissionServiceSessionSummary:
        return MissionServiceSessionSummary(
            session_id=self.session_id,
            mission_mode=self.latest_modeled_state.mission_mode if self.latest_modeled_state else None,
            mission_complete=self.latest_modeled_state.mission_complete if self.latest_modeled_state else None,
            last_event=self.last_event,
        )

    def view( self ) -> MissionServiceSessionView:
        render_state = self._render_state()
        return MissionServiceSessionView(
            snapshot=self.snapshot(),
            modeled_state=self.latest_modeled_state,
            render_state=render_state,
            bridge_state=self.bridge_state(),
        )

    def _remember( self, note: str ) -> None:
        self.last_event = note
        self.notes = [ *self.notes[ -4: ], note ]

    def _apply_route_plan( self, route_plan: RoutePlanResponse ) -> None:
        self.active_route_kind = route_plan.kind
        self.active_route = route_plan.waypoints
        self.route_revision += 1

    def _mark_pending_command(
        self,
        kind: str,
        note: str,
        *,
        real_time: bool | None = None,
        playback_speed: float | None = None,
    ) -> None:
        self.pending_command_kind = kind
        self.pending_command_note = note
        self.pending_real_time = real_time
        self.pending_playback_speed = playback_speed
        self.command_revision += 1

    def bridge_state( self ) -> MissionBridgeState:
        return MissionBridgeState(
            pending_command_kind=self.pending_command_kind,
            pending_command_note=self.pending_command_note,
            pending_real_time=self.pending_real_time,
            pending_playback_speed=self.pending_playback_speed,
            command_revision=self.command_revision,
            command_revision_applied=self.command_revision_applied,
            route_revision=self.route_revision,
            route_revision_applied=self.route_revision_applied,
        )

    def _current_position( self, request_position: Coordinate | None ) -> Coordinate:
        return request_position or self.sentry_position

    def _ensure_patrol_route( self ) -> RoutePlanResponse | None:
        if self.scene.patrol_route:
            return None
        route_plan = plan_route_request(
            RoutePlanRequest(
                kind="patrol_loop",
                start=self.sentry_position,
                patrol_area=self.scene.patrol_area,
                ownship_speed_mps=self.sentry_speed_mps,
            )
        )
        self.scene.patrol_route = route_plan.waypoints
        self.active_route_kind = "patrol_loop"
        self.active_route = list( route_plan.waypoints )
        self.patrol_assigned = True
        return route_plan

    def _render_state( self ):
        if self.latest_modeled_state is not None:
            return build_render_state(
                self.scene,
                self.latest_modeled_state.mission_mode,
                self.latest_modeled_state.mission_time_s,
                self.latest_modeled_state.current_speed_mps,
                self.latest_modeled_state.track_time_remaining_s,
                self.latest_modeled_state.tier1_engagement_time_remaining_s,
                self.reference,
                vehicle_position=self.sentry_position,
                incursion_position=self.incursion_position,
                attributes=self.latest_modeled_state.attributes,
                incursion_active=self.incursion_position is not None,
                fallback_speed_mps=self.sentry_speed_mps,
            )
        return build_render_state(
            self.scene,
            None,
            None,
            self.sentry_speed_mps,
            None,
            None,
            self.reference,
            vehicle_position=self.sentry_position,
            attributes={ "source": "mission_service_idle" },
            incursion_active=self.incursion_active,
            fallback_speed_mps=self.sentry_speed_mps,
        )

    def acknowledge_bridge_updates( self, request: MissionBridgeAckRequest ) -> MissionBridgeAckResponse:
        if request.command_revision_applied is not None:
            self.command_revision_applied = max( self.command_revision_applied, request.command_revision_applied )
            if self.command_revision_applied >= self.command_revision:
                self.pending_command_kind = None
                self.pending_command_note = None
                self.pending_real_time = None
                self.pending_playback_speed = None
        if request.route_revision_applied is not None:
            self.route_revision_applied = max( self.route_revision_applied, request.route_revision_applied )

        note = request.note or "Bridge revisions acknowledged."
        self._remember( note )
        return MissionBridgeAckResponse(
            session_id=self.session_id,
            bridge_state=self.bridge_state(),
            note=note,
        )

    def sync_modeled_state( self, request: MissionSyncRequest ) -> MissionSyncResponse:
        modeled_state = request.modeled_state
        self.latest_modeled_state = modeled_state
        self.reference.observe( modeled_state )

        recommended_route: RoutePlanResponse | None = self._ensure_patrol_route()
        suggested_command: str | None = None

        mission_mode = modeled_state.mission_mode or ""
        canonical_mode = canonical_mission_mode( mission_mode )
        if modeled_state.current_speed_mps is not None:
            self.sentry_speed_mps = modeled_state.current_speed_mps

        if mode_contains( canonical_mode, "TRACK", "ENGAGE", "TIER1" ):
            if self.incursion_route:
                self.incursion_active = True
                recommended_route = plan_route_request(
                    RoutePlanRequest(
                        kind="track",
                        start=self.sentry_position,
                        target_route=self.incursion_route,
                        ownship_speed_mps=self.sentry_speed_mps,
                        target_speed_mps=self.incursion_speed_mps,
                    )
                )
                self._apply_route_plan( recommended_route )
                suggested_command = "intercept_incursion"

        elif (
            mode_contains( canonical_mode, "RETURN" )
            or modeled_state.low_battery_triggered
            or modeled_state.returned_early
        ):
            recommended_route = plan_route_request(
                RoutePlanRequest(
                    kind="recall",
                    start=self.sentry_position,
                    end=self.scene.base,
                    ownship_speed_mps=self.sentry_speed_mps,
                )
            )
            self._apply_route_plan( recommended_route )
            self.recall_active = True
            suggested_command = "recall"

        elif mode_contains( canonical_mode, "PATROL" ) and self.scene.patrol_route:
            self.active_route_kind = "patrol_loop"
            self.active_route = list( self.scene.patrol_route )
            if not mode_contains( canonical_mode, "ENGAGE", "TIER1" ):
                self.incursion_active = False

        if mode_contains( canonical_mode, "MISSION_SUCCESS", "MISSION_FAIL" ) or modeled_state.mission_complete:
            self.active_route_kind = None
            self.active_route = []
            self.recall_active = False
            self.incursion_active = False

        projection = self.live_projection.advance(
            self.scene,
            modeled_state,
            self.reference,
            session_id=self.session_id,
            fallback_speed_mps=self.sentry_speed_mps,
            incursion_speed_mps=self.incursion_speed_mps,
        )
        self.sentry_position = projection.vehicle_position
        self.incursion_position = projection.incursion_position
        log_live_playback(
            "mission_sync",
            session_id=self.session_id,
            mission_mode=canonical_mode or mission_mode,
            mission_time_s=modeled_state.mission_time_s,
            time_ms=modeled_state.time_ms,
            current_speed_mps=modeled_state.current_speed_mps,
            distance_to_base_m=modeled_state.distance_to_base_m,
            distance_to_perimeter_m=modeled_state.distance_to_perimeter_m,
            patrol_distance_remaining_m=modeled_state.patrol_distance_remaining_m,
            track_time_remaining_s=modeled_state.track_time_remaining_s,
            tier1_engagement_time_remaining_s=modeled_state.tier1_engagement_time_remaining_s,
            low_battery_triggered=modeled_state.low_battery_triggered,
            returned_early=modeled_state.returned_early,
            mission_complete=modeled_state.mission_complete,
            projected_phase=projection.phase,
            projected_vehicle_position=self.sentry_position,
            projected_incursion_position=self.incursion_position,
            log_path=str( playback_log_path() ),
        )
        self._remember(
            "Modeled mission state synchronized"
            + ( f" for mode {canonical_mode or mission_mode}." if mission_mode else "." )
        )
        return MissionSyncResponse(
            session_id=self.session_id,
            modeled_state=modeled_state,
            snapshot=self.snapshot(),
            recommended_route=recommended_route,
            suggested_command=suggested_command,
            note=self.last_event or "Modeled mission state synchronized.",
        )

    def apply_command( self, request: MissionCommandRequest ) -> MissionCommandResponse:
        route_plan: RoutePlanResponse | None = None
        note = ""

        if request.sentry_speed_mps is not None:
            self.sentry_speed_mps = request.sentry_speed_mps

        current_position = self._current_position( request.current_position )
        self.sentry_position = current_position

        if request.kind == "assign_patrol":
            patrol_area = request.patrol_area or self.scene.patrol_area
            route_plan = plan_route_request(
                RoutePlanRequest(
                    kind="patrol_loop",
                    start=current_position,
                    patrol_area=patrol_area,
                    ownship_speed_mps=self.sentry_speed_mps,
                )
            )
            self.scene.patrol_area = patrol_area
            self.scene.patrol_route = route_plan.waypoints
            self._apply_route_plan( route_plan )
            self.patrol_assigned = True
            self.recall_active = False
            note = "Patrol area assigned and patrol loop generated."
            self._mark_pending_command( request.kind, note )

        elif request.kind == "recall":
            route_plan = plan_route_request(
                RoutePlanRequest(
                    kind="recall",
                    start=current_position,
                    end=self.scene.base,
                    ownship_speed_mps=self.sentry_speed_mps,
                )
            )
            self._apply_route_plan( route_plan )
            self.recall_active = True
            note = "Recall route generated back to base."
            self._mark_pending_command( request.kind, note )

        elif request.kind == "authorize_tier1":
            self.escalation_authorized = True
            note = "Tier 1 escalation authorized."
            self._mark_pending_command( request.kind, note )

        elif request.kind == "intercept_incursion":
            target_route = request.target_route or self.incursion_route
            route_plan = plan_route_request(
                RoutePlanRequest(
                    kind="track",
                    start=current_position,
                    target_route=target_route,
                    ownship_speed_mps=self.sentry_speed_mps,
                    target_speed_mps=self.incursion_speed_mps,
                )
            )
            self._apply_route_plan( route_plan )
            self.recall_active = False
            note = "Intercept/track route generated against the current incursion."
            self._mark_pending_command( request.kind, note )

        elif request.kind in { "clear_recall", "resume_patrol" }:
            self.recall_active = False
            if self.scene.patrol_route:
                self.active_route_kind = "patrol_loop"
                self.active_route = list( self.scene.patrol_route )
                self.route_revision += 1
            note = "Recall cleared; mission service resumed the current patrol route."
            self._mark_pending_command( request.kind, note )

        elif request.kind == "set_playback_speed":
            if request.playback_speed is None:
                raise HTTPException( status_code=400, detail="set_playback_speed requires playback_speed" )
            requested_real_time = True if request.real_time is None else request.real_time
            note = f"Requested live playback speed {request.playback_speed:.1f}x."
            self._mark_pending_command(
                request.kind,
                note,
                real_time=requested_real_time,
                playback_speed=request.playback_speed,
            )

        else:
            raise HTTPException( status_code=400, detail=f"Unsupported command: {request.kind}" )

        self._remember( note )
        return MissionCommandResponse(
            session_id=self.session_id,
            applied=True,
            command=request.kind,
            snapshot=self.snapshot(),
            route_plan=route_plan,
            note=note,
        )

    def apply_perturbation( self, request: MissionPerturbationRequest ) -> MissionPerturbationResponse:
        route_plan: RoutePlanResponse | None = None
        note = ""

        if request.kind == "incursion_spawn":
            if request.route:
                self.incursion_route = request.route
            self.incursion_position = self.incursion_route[ 0 ] if self.incursion_route else None
            self.incursion_active = bool( self.incursion_route )
            note = "Incursion spawned or refreshed on the active route."
            self._mark_pending_command( request.kind, note )

        elif request.kind == "route_deviation":
            if request.route:
                self.incursion_route = request.route
            else:
                self.incursion_route = deviate_route(
                    self.incursion_route,
                    offset_m=request.offset_m,
                    direction=request.direction,
            )
            self.incursion_position = self.incursion_route[ 0 ] if self.incursion_route else None
            note = "Incursion route laterally deviated from the nominal path."
            self._mark_pending_command( request.kind, note )

        elif request.kind == "incursion_speed_change":
            if request.speed_mps is None:
                raise HTTPException( status_code=400, detail="incursion_speed_change requires speed_mps" )
            self.incursion_speed_mps = request.speed_mps
            note = f"Incursion speed updated to {request.speed_mps:.2f} m/s."
            self._mark_pending_command( request.kind, note )

        elif request.kind == "all_clear":
            self.incursion_active = False
            self.incursion_position = None
            if self.active_route_kind in { "intercept", "track" }:
                self.active_route_kind = "patrol_loop" if self.scene.patrol_route else None
                self.active_route = list( self.scene.patrol_route ) if self.scene.patrol_route else []
                self.route_revision += 1
            note = "All-clear received; active incursion cleared."
            self._mark_pending_command( request.kind, note )

        else:
            raise HTTPException( status_code=400, detail=f"Unsupported perturbation: {request.kind}" )

        if self.incursion_active and self.active_route_kind in { "intercept", "track" } and self.incursion_route:
            route_plan = plan_route_request(
                RoutePlanRequest(
                    kind="track",
                    start=self.sentry_position,
                    target_route=self.incursion_route,
                    ownship_speed_mps=self.sentry_speed_mps,
                    target_speed_mps=self.incursion_speed_mps,
                )
            )
            self._apply_route_plan( route_plan )
            note = f"{note} Track route refreshed for the updated incursion geometry."

        self._remember( note )
        return MissionPerturbationResponse(
            session_id=self.session_id,
            applied=True,
            perturbation=request.kind,
            snapshot=self.snapshot(),
            route_plan=route_plan,
            note=note,
        )


class MissionServiceStore:
    def __init__( self ) -> None:
        self._sessions: dict[ str, MissionServiceSession ] = {}

    def create( self, request: MissionServiceCreateRequest ) -> MissionServiceSnapshot:
        session_id = str( uuid.uuid4() )
        scene = _build_scene( request )
        sentry_position = request.sentry_position or scene.base
        incursion_route = request.incursion_route or list( scene.incursion_route )
        session = MissionServiceSession(
            session_id=session_id,
            scene=scene,
            sentry_position=sentry_position,
            sentry_speed_mps=request.sentry_speed_mps,
            incursion_route=incursion_route,
            incursion_speed_mps=request.incursion_speed_mps,
            incursion_position=None,
        )
        session._remember( "Mission service session initialized." )
        log_live_playback(
            "mission_session_created",
            session_id=session_id,
            scene_id=scene.id,
            sentry_position=sentry_position,
            incursion_route=incursion_route,
            log_path=str( playback_log_path() ),
        )
        self._sessions[ session_id ] = session
        return session.snapshot()

    def get( self, session_id: str ) -> MissionServiceSession:
        session = self._sessions.get( session_id )
        if session is None:
            raise HTTPException( status_code=404, detail=f"Unknown mission service session: {session_id}" )
        return session

    def list( self ) -> list[ MissionServiceSessionSummary ]:
        return [ session.summary() for session in reversed( list( self._sessions.values() ) ) ]

    def terminate( self, session_id: str ) -> bool:
        return self._sessions.pop( session_id, None ) is not None


store = MissionServiceStore()
