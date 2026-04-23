from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.schemas import Coordinate, RenderScene

from .geometry import path_distance_m
from .mission_mode import canonical_mission_mode, mode_contains
from .mission_projection_routes import (
    PATROL_SPEED_MPS,
    RETURN_SPEED_MPS,
    TRACK_SPEED_MPS,
    TRANSIT_SPEED_MPS,
    _dedupe_waypoints,
    engagement_waypoints,
    lift_coordinate,
    outbound_waypoints,
    patrol_rejoin_waypoints,
    patrol_waypoints,
    return_waypoints,
    track_waypoints,
)
from .playback_logging import log_live_playback
from .trajectory_motion import TimedCoordinateSample, build_multirotor_route_samples, sample_timed_coordinates

INCURSION_TRIGGER_DISTANCE_M = 6.0
INCURSION_RENDER_DURATION_SCALE = 0.5
RESET_EPSILON_S = 0.001


class _ProgressState( Protocol ):
    mission_time_s: float | None
    mission_mode: str | None
    current_speed_mps: float | None
    distance_to_base_m: float | None
    distance_to_perimeter_m: float | None
    patrol_distance_remaining_m: float | None
    track_time_remaining_s: float | None
    tier1_engagement_time_remaining_s: float | None
    low_battery_triggered: bool | None
    returned_early: bool | None
    mission_complete: bool | None


@dataclass
class ReferenceMetrics:
    distance_to_base_start_m: float | None = None
    distance_to_perimeter_start_m: float | None = None
    patrol_distance_start_m: float | None = None
    track_time_start_s: float | None = None
    tier1_engagement_start_s: float | None = None

    def observe( self, state: _ProgressState ) -> None:
        if self.distance_to_base_start_m is None and _positive( state.distance_to_base_m ):
            self.distance_to_base_start_m = state.distance_to_base_m
        if self.distance_to_perimeter_start_m is None and _positive( state.distance_to_perimeter_m ):
            self.distance_to_perimeter_start_m = state.distance_to_perimeter_m
        if self.patrol_distance_start_m is None and _positive( state.patrol_distance_remaining_m ):
            self.patrol_distance_start_m = state.patrol_distance_remaining_m
        if self.track_time_start_s is None and _positive( state.track_time_remaining_s ):
            self.track_time_start_s = state.track_time_remaining_s
        if self.tier1_engagement_start_s is None and _positive( state.tier1_engagement_time_remaining_s ):
            self.tier1_engagement_start_s = state.tier1_engagement_time_remaining_s


@dataclass( frozen=True )
class ProjectionResult:
    vehicle_position: Coordinate
    incursion_position: Coordinate | None
    phase: str


@dataclass( frozen=True )
class TimedPlan:
    samples: list[ TimedCoordinateSample ] = field( default_factory=list )
    loop: bool = False
    duration_s: float = 0.0


@dataclass
class LiveMissionProjection:
    phase: str = "idle"
    vehicle_position: Coordinate | None = None
    incursion_position: Coordinate | None = None
    last_mission_time_s: float | None = None
    phase_started_at_s: float | None = None
    vehicle_plan: TimedPlan = field( default_factory=TimedPlan )
    incursion_started_at_s: float | None = None
    incursion_plan: TimedPlan = field( default_factory=TimedPlan )

    def reset( self, scene: RenderScene ) -> None:
        self.phase = "idle"
        self.vehicle_position = scene.base
        self.incursion_position = None
        self.last_mission_time_s = None
        self.phase_started_at_s = None
        self.vehicle_plan = TimedPlan()
        self.incursion_started_at_s = None
        self.incursion_plan = TimedPlan()

    def advance(
        self,
        scene: RenderScene,
        state: _ProgressState,
        reference: ReferenceMetrics,
        *,
        session_id: str,
        fallback_speed_mps: float | None,
        incursion_speed_mps: float,
    ) -> ProjectionResult:
        mission_mode = canonical_mission_mode( state.mission_mode )
        mission_time_s = _normalized_mission_time_s( state.mission_time_s )

        if self.vehicle_position is None:
            self.reset( scene )
            log_live_playback(
                "projection_reset",
                session_id=session_id,
                reason="uninitialized_projection",
                scene_id=scene.id,
            )

        if (
            mission_time_s is not None
            and self.last_mission_time_s is not None
            and mission_time_s + RESET_EPSILON_S < self.last_mission_time_s
        ):
            self.reset( scene )
            log_live_playback(
                "projection_reset",
                session_id=session_id,
                reason="mission_time_decreased",
                mission_time_s=mission_time_s,
                previous_mission_time_s=self.last_mission_time_s,
                scene_id=scene.id,
            )

        delta_s = 0.0
        if mission_time_s is not None and self.last_mission_time_s is not None:
            delta_s = max( 0.0, mission_time_s - self.last_mission_time_s )

        phase = resolve_live_phase( state, reference )
        if phase != self.phase or not self.vehicle_plan.samples:
            previous_phase = self.phase
            self._enter_phase(
                scene,
                state,
                reference,
                phase=phase,
                previous_phase=previous_phase,
                mission_mode=mission_mode,
                mission_time_s=mission_time_s,
                fallback_speed_mps=fallback_speed_mps,
                incursion_speed_mps=incursion_speed_mps,
            )
            log_live_playback(
                "projection_phase_enter",
                session_id=session_id,
                previous_phase=previous_phase,
                next_phase=phase,
                mission_mode=mission_mode,
                mission_time_s=mission_time_s,
                phase_started_at_s=self.phase_started_at_s,
                vehicle_plan_duration_s=self.vehicle_plan.duration_s,
                vehicle_plan_loop=self.vehicle_plan.loop,
                vehicle_sample_count=len( self.vehicle_plan.samples ),
                incursion_plan_duration_s=self.incursion_plan.duration_s,
                incursion_sample_count=len( self.incursion_plan.samples ),
            )

        phase_elapsed_s = _elapsed_since_start( mission_time_s, self.phase_started_at_s )
        incursion_elapsed_s = _elapsed_since_start( mission_time_s, self.incursion_started_at_s )
        sampled_vehicle = _sample_plan( self.vehicle_plan, phase_elapsed_s )
        if sampled_vehicle is not None:
            self.vehicle_position = sampled_vehicle
        sampled_incursion = _sample_plan( self.incursion_plan, incursion_elapsed_s )
        if sampled_incursion is not None:
            self.incursion_position = sampled_incursion

        visible_incursion_position = self.incursion_position if phase in { "track", "engage" } else None
        self.last_mission_time_s = mission_time_s if mission_time_s is not None else self.last_mission_time_s

        log_live_playback(
            "projection_step",
            session_id=session_id,
            phase=phase,
            mission_mode=mission_mode,
            mission_time_s=mission_time_s,
            delta_s=delta_s,
            phase_elapsed_s=phase_elapsed_s,
            vehicle_plan_duration_s=self.vehicle_plan.duration_s,
            vehicle_position=self.vehicle_position,
            incursion_elapsed_s=incursion_elapsed_s,
            incursion_plan_duration_s=self.incursion_plan.duration_s,
            incursion_position=visible_incursion_position,
        )
        return ProjectionResult(
            vehicle_position=self.vehicle_position or scene.base,
            incursion_position=visible_incursion_position,
            phase=phase,
        )

    def _enter_phase(
        self,
        scene: RenderScene,
        state: _ProgressState,
        reference: ReferenceMetrics,
        *,
        phase: str,
        previous_phase: str,
        mission_mode: str,
        mission_time_s: float | None,
        fallback_speed_mps: float | None,
        incursion_speed_mps: float,
    ) -> None:
        anchor = self.vehicle_position or scene.base
        phase_speed_mps = _phase_speed_mps( phase, state.current_speed_mps, fallback_speed_mps )
        estimated_elapsed_s = _estimate_phase_elapsed_s( phase, state, reference, phase_speed_mps )
        if phase == "patrol" and previous_phase in { "track", "engage" }:
            estimated_elapsed_s = 0.0
        if phase == "return" and previous_phase != "return":
            estimated_elapsed_s = 0.0
        normalized_mission_time_s = mission_time_s if mission_time_s is not None else 0.0
        self.phase = phase
        self.phase_started_at_s = max( normalized_mission_time_s - estimated_elapsed_s, 0.0 )

        if phase in { "track", "engage" } and not self.incursion_plan.samples:
            self._start_incursion_plan(
                scene,
                state,
                reference,
                mission_time_s=normalized_mission_time_s,
                incursion_speed_mps=incursion_speed_mps,
            )

        incursion_anchor = _sample_plan(
            self.incursion_plan,
            _elapsed_since_start( mission_time_s, self.incursion_started_at_s ),
        ) if self.incursion_plan.samples else None

        self.vehicle_plan = _build_vehicle_plan(
            scene,
            state,
            reference,
            phase=phase,
            previous_phase=previous_phase,
            anchor=anchor,
            phase_speed_mps=phase_speed_mps,
            incursion_anchor=incursion_anchor,
        )

    def _start_incursion_plan(
        self,
        scene: RenderScene,
        state: _ProgressState,
        reference: ReferenceMetrics,
        *,
        mission_time_s: float,
        incursion_speed_mps: float,
    ) -> None:
        base_duration_s = reference.track_time_start_s or state.track_time_remaining_s
        duration_s = base_duration_s * INCURSION_RENDER_DURATION_SCALE if base_duration_s is not None else None
        routed_incursion = [ lift_coordinate( point, 0.0 ) for point in scene.incursion_route ] or list( scene.incursion_route )
        self.incursion_plan = _plan_from_waypoints(
            routed_incursion,
            speed_mps=incursion_speed_mps,
            loop=False,
            duration_s=duration_s,
        )
        estimated_elapsed_s = _estimate_phase_elapsed_s( "track", state, reference, incursion_speed_mps )
        self.incursion_started_at_s = max( mission_time_s - estimated_elapsed_s, 0.0 )


def _positive( value: float | None ) -> bool:
    return value is not None and value > 0.0


def _normalized_mission_time_s( mission_time_s: float | None ) -> float | None:
    if mission_time_s is None or mission_time_s < 0.0:
        return None
    return mission_time_s


def _ratio_from_remaining( remaining: float | None, baseline: float | None ) -> float | None:
    if remaining is None or baseline is None or baseline <= 0.0:
        return None
    return 1.0 - min( max( remaining / baseline, 0.0 ), 1.0 )


def _duration_s( distance_magnitude_m: float | None, speed_mps: float ) -> float | None:
    if distance_magnitude_m is None or distance_magnitude_m <= 0.0 or speed_mps <= 0.0:
        return None
    return distance_magnitude_m / speed_mps


def _elapsed_since_start( mission_time_s: float | None, started_at_s: float | None ) -> float:
    if mission_time_s is None or started_at_s is None:
        return 0.0
    return max( mission_time_s - started_at_s, 0.0 )

def _plan_from_waypoints(
    waypoints: list[ Coordinate ],
    *,
    speed_mps: float,
    loop: bool,
    duration_s: float | None = None,
) -> TimedPlan:
    normalized_waypoints = _dedupe_waypoints( waypoints )
    if not normalized_waypoints:
        return TimedPlan()
    samples = build_multirotor_route_samples(
        normalized_waypoints,
        speed_mps=max( speed_mps, 0.1 ),
        loop=loop,
        total_duration_s=duration_s,
        time_step_s=0.25,
    )
    if not samples:
        return TimedPlan()
    return TimedPlan(
        samples=samples,
        loop=loop,
        duration_s=samples[ -1 ].time_s,
    )


def _sample_plan( plan: TimedPlan, elapsed_s: float ) -> Coordinate | None:
    if not plan.samples:
        return None
    return sample_timed_coordinates( plan.samples, elapsed_s, loop=plan.loop )


def _phase_speed_mps(
    phase: str,
    explicit_speed_mps: float | None,
    fallback_speed_mps: float | None,
) -> float:
    if explicit_speed_mps is not None and explicit_speed_mps > 0.1:
        return explicit_speed_mps
    if fallback_speed_mps is not None and fallback_speed_mps > 0.1:
        return fallback_speed_mps
    if phase == "patrol":
        return PATROL_SPEED_MPS
    if phase in { "track", "engage" }:
        return TRACK_SPEED_MPS
    if phase == "return":
        return RETURN_SPEED_MPS
    return TRANSIT_SPEED_MPS


def _phase_duration_s(
    phase: str,
    state: _ProgressState,
    reference: ReferenceMetrics,
    *,
    speed_mps: float,
) -> float | None:
    if phase == "outbound":
        return _duration_s( reference.distance_to_perimeter_start_m or state.distance_to_perimeter_m, speed_mps )
    if phase == "patrol":
        return _duration_s( reference.patrol_distance_start_m or state.patrol_distance_remaining_m, speed_mps )
    if phase == "track":
        return reference.track_time_start_s or state.track_time_remaining_s
    if phase == "engage":
        return reference.tier1_engagement_start_s or state.tier1_engagement_time_remaining_s
    if phase == "return":
        return _duration_s( state.distance_to_base_m or reference.distance_to_base_start_m, speed_mps )
    return None


def _return_duration_s(
    scene: RenderScene,
    state: _ProgressState,
    reference: ReferenceMetrics,
    *,
    anchor: Coordinate,
    speed_mps: float,
    previous_phase: str,
) -> float | None:
    if previous_phase != "return":
        path_length_m = path_distance_m( return_waypoints( scene, start=anchor ) )
        return _duration_s( path_length_m, speed_mps )
    return _phase_duration_s( "return", state, reference, speed_mps=speed_mps )


def _estimate_phase_elapsed_s(
    phase: str,
    state: _ProgressState,
    reference: ReferenceMetrics,
    speed_mps: float,
) -> float:
    if phase == "outbound":
        ratio = _ratio_from_remaining( state.distance_to_perimeter_m, reference.distance_to_perimeter_start_m )
        duration_s = _phase_duration_s( phase, state, reference, speed_mps=speed_mps )
        if ratio is not None and duration_s is not None:
            return ratio * duration_s
        return 0.0
    if phase == "patrol":
        ratio = _ratio_from_remaining( state.patrol_distance_remaining_m, reference.patrol_distance_start_m )
        duration_s = _duration_s( reference.patrol_distance_start_m, speed_mps )
        if ratio is not None and duration_s is not None:
            return ratio * duration_s
        return 0.0
    if phase == "track" and reference.track_time_start_s is not None and state.track_time_remaining_s is not None:
        return max( reference.track_time_start_s - state.track_time_remaining_s, 0.0 )
    if phase == "engage" and reference.tier1_engagement_start_s is not None and state.tier1_engagement_time_remaining_s is not None:
        return max( reference.tier1_engagement_start_s - state.tier1_engagement_time_remaining_s, 0.0 )
    if phase == "return":
        ratio = _ratio_from_remaining( state.distance_to_base_m, reference.distance_to_base_start_m )
        duration_s = _phase_duration_s( phase, state, reference, speed_mps=speed_mps )
        if ratio is not None and duration_s is not None:
            return ratio * duration_s
    return 0.0


def _build_vehicle_plan(
    scene: RenderScene,
    state: _ProgressState,
    reference: ReferenceMetrics,
    *,
    phase: str,
    previous_phase: str,
    anchor: Coordinate,
    phase_speed_mps: float,
    incursion_anchor: Coordinate | None,
) -> TimedPlan:
    if phase == "terminal":
        return TimedPlan( samples=[ TimedCoordinateSample( time_s=0.0, position=scene.base ) ], loop=False, duration_s=0.0 )
    if phase == "idle":
        return TimedPlan( samples=[ TimedCoordinateSample( time_s=0.0, position=anchor ) ], loop=False, duration_s=0.0 )
    if phase == "outbound":
        return _plan_from_waypoints(
            outbound_waypoints( scene, start=anchor ),
            speed_mps=phase_speed_mps,
            loop=False,
            duration_s=_phase_duration_s( phase, state, reference, speed_mps=phase_speed_mps ),
        )
    if phase == "patrol":
        patrol_loop = patrol_waypoints( scene, anchor=anchor )
        patrol_route_waypoints = (
            patrol_rejoin_waypoints( scene, anchor=anchor )
            if previous_phase in { "track", "engage" }
            else patrol_waypoints( scene )
            if patrol_loop
            else [ anchor ]
        )
        patrol_duration_s = (
            _duration_s( state.patrol_distance_remaining_m or reference.patrol_distance_start_m, phase_speed_mps )
            if previous_phase in { "track", "engage" }
            else _duration_s( reference.patrol_distance_start_m or state.patrol_distance_remaining_m, phase_speed_mps )
        )
        return _plan_from_waypoints(
            patrol_route_waypoints,
            speed_mps=phase_speed_mps,
            loop=False,
            duration_s=patrol_duration_s,
        )
    if phase == "track":
        return _plan_from_waypoints(
            track_waypoints( scene, anchor=anchor, incursion_anchor=incursion_anchor ),
            speed_mps=phase_speed_mps,
            loop=False,
            duration_s=_phase_duration_s( phase, state, reference, speed_mps=phase_speed_mps ),
        )
    if phase == "engage":
        return _plan_from_waypoints(
            engagement_waypoints( scene, anchor=anchor, incursion_anchor=incursion_anchor ),
            speed_mps=phase_speed_mps,
            loop=False,
            duration_s=_phase_duration_s( phase, state, reference, speed_mps=phase_speed_mps ),
        )
    if phase == "return":
        return _plan_from_waypoints(
            return_waypoints( scene, start=anchor ),
            speed_mps=phase_speed_mps,
            loop=False,
            duration_s=_return_duration_s(
                scene,
                state,
                reference,
                anchor=anchor,
                speed_mps=phase_speed_mps,
                previous_phase=previous_phase,
            ),
        )
    return TimedPlan( samples=[ TimedCoordinateSample( time_s=0.0, position=anchor ) ], loop=False, duration_s=0.0 )


def resolve_live_phase( state: _ProgressState, reference: ReferenceMetrics ) -> str:
    del reference
    mission_mode = canonical_mission_mode( state.mission_mode )

    if state.mission_complete or mode_contains( mission_mode, "MISSION_SUCCESS", "MISSION_FAIL" ):
        return "terminal"
    if mode_contains( mission_mode, "RETURN", "RECALL", "BASE" ):
        return "return"
    if mode_contains( mission_mode, "ENGAGE", "TIER1" ):
        return "engage"
    if mode_contains( mission_mode, "TRACK" ):
        return "track"
    if mode_contains( mission_mode, "TRANSIT", "PERIMETER", "STARTMISSION" ):
        return "outbound"
    if state.distance_to_perimeter_m is not None and state.distance_to_perimeter_m > INCURSION_TRIGGER_DISTANCE_M:
        return "outbound"
    if mode_contains( mission_mode, "PATROL" ):
        return "patrol"
    return "idle"


def derive_vehicle_position(
    scene: RenderScene,
    state: _ProgressState,
    reference: ReferenceMetrics,
) -> Coordinate:
    mission_mode = canonical_mission_mode( state.mission_mode )
    mission_time_s = _normalized_mission_time_s( state.mission_time_s ) or 0.0
    phase = resolve_live_phase( state, reference )
    phase_speed_mps = _phase_speed_mps( phase, state.current_speed_mps, None )
    phase_elapsed_s = _estimate_phase_elapsed_s( phase, state, reference, phase_speed_mps )
    phase_started_at_s = max( mission_time_s - phase_elapsed_s, 0.0 )

    incursion_plan = TimedPlan()
    incursion_anchor: Coordinate | None = None
    if phase in { "track", "engage" }:
        incursion_plan = _plan_from_waypoints(
            scene.incursion_route,
            speed_mps=4.0,
            loop=False,
            duration_s=reference.track_time_start_s or state.track_time_remaining_s,
        )
        incursion_anchor = _sample_plan( incursion_plan, _elapsed_since_start( mission_time_s, phase_started_at_s ) )

    vehicle_plan = _build_vehicle_plan(
        scene,
        state,
        reference,
        phase=phase,
        previous_phase="idle",
        anchor=scene.base,
        phase_speed_mps=phase_speed_mps,
        incursion_anchor=incursion_anchor,
    )
    sampled = _sample_plan( vehicle_plan, _elapsed_since_start( mission_time_s, phase_started_at_s ) )
    return sampled or scene.base
