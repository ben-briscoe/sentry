from __future__ import annotations

from typing import Any

from app.schemas import Coordinate, RenderIncursionState, RenderState, RenderEntityState, RenderScene

from .geometry import path_distance_m, sample_path
from .mission_mode import canonical_mission_mode, mode_contains
from .mission_projection import ReferenceMetrics, derive_vehicle_position


CRUISE_ALTITUDE_M = 42.0
TRACK_ALTITUDE_M = 36.0
TIER1_ALTITUDE_M = 30.0


def _attribute_bool( attributes: dict[ str, Any ] | None, *keys: str ) -> bool | None:
    if not attributes:
        return None
    for key in keys:
        value = attributes.get( key )
        if isinstance( value, bool ):
            return value
        if isinstance( value, str ):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
    return None


def derive_effect_flags(
    mission_mode: str | None,
    attributes: dict[ str, Any ] | None,
) -> tuple[ bool, bool ]:
    explicit_spotlight = _attribute_bool( attributes, "spotlight_on", "spotlightOn", "spotlightActive" )
    explicit_speaker = _attribute_bool( attributes, "speaker_on", "speakerOn", "speakerActive" )

    mode = canonical_mission_mode( mission_mode )
    spotlight_on = explicit_spotlight if explicit_spotlight is not None else (
        mode_contains( mode, "TRACK", "ENGAGE", "TIER1" )
    )
    speaker_on = explicit_speaker if explicit_speaker is not None else (
        mode_contains( mode, "TIER1", "ENGAGE" )
    )
    return spotlight_on, speaker_on


def derive_render_speed_mps(
    mission_mode: str | None,
    explicit_speed_mps: float | None,
    fallback_speed_mps: float | None = None,
) -> float | None:
    if explicit_speed_mps is not None:
        return explicit_speed_mps
    if fallback_speed_mps is not None:
        return fallback_speed_mps

    mode = canonical_mission_mode( mission_mode )
    if mode_contains( mode, "MISSION_SUCCESS", "MISSION_FAIL" ):
        return 0.0
    if mode_contains( mode, "RETURN" ):
        return 6.0
    if mode_contains( mode, "ENGAGE", "TIER1" ):
        return 5.5
    if mode_contains( mode, "TRACK" ):
        return 6.5
    if mode_contains( mode, "PATROL" ):
        return 5.0
    if mode:
        return 4.0
    return None


def lift_coordinate( point: Coordinate, altitude_m: float ) -> Coordinate:
    return Coordinate( lon=point.lon, lat=point.lat, alt_m=max( point.alt_m, altitude_m ) )


def derive_incursion_position(
    scene: RenderScene,
    mission_mode: str | None,
    mission_time_s: float | None,
    track_time_remaining_s: float | None,
    tier1_engagement_time_remaining_s: float | None,
    reference: ReferenceMetrics,
    *,
    active: bool,
) -> Coordinate | None:
    if not active or not scene.incursion_route:
        return None

    mode = canonical_mission_mode( mission_mode )
    if mode_contains( mode, "MISSION_SUCCESS", "MISSION_FAIL" ):
        return None

    if mode and not mode_contains( mode, "TRACK", "TIER1", "ENGAGE" ):
        return None
    if not mode and not (
        ( track_time_remaining_s is not None and track_time_remaining_s > 0.0 )
        or ( tier1_engagement_time_remaining_s is not None and tier1_engagement_time_remaining_s > 0.0 )
    ):
        return None

    if mode_contains( mode, "TRACK", "ENGAGE", "TIER1" ) or ( not mode and track_time_remaining_s is not None and track_time_remaining_s > 0.0 ):
        baseline = reference.tier1_engagement_start_s
        remaining = tier1_engagement_time_remaining_s
        if mode_contains( mode, "TRACK" ):
            baseline = reference.track_time_start_s
            remaining = track_time_remaining_s
        if baseline is not None and remaining is not None and baseline > 0.0:
            progress = 1.0 - min( max( remaining / baseline, 0.0 ), 1.0 )
            return sample_path( scene.incursion_route, progress * path_distance_m( scene.incursion_route ) )

    return scene.incursion_route[ 0 ]


def build_render_state(
    scene: RenderScene,
    mission_mode: str | None,
    mission_time_s: float | None,
    current_speed_mps: float | None,
    track_time_remaining_s: float | None,
    tier1_engagement_time_remaining_s: float | None,
    reference: ReferenceMetrics,
    *,
    vehicle_position: Coordinate,
    incursion_position: Coordinate | None = None,
    attributes: dict[ str, Any ] | None,
    incursion_active: bool,
    incursion_radius_m: float = 14.0,
    fallback_speed_mps: float | None = None,
) -> RenderState:
    spotlight_on, speaker_on = derive_effect_flags( mission_mode, attributes )
    resolved_incursion_position = incursion_position
    if resolved_incursion_position is None:
        resolved_incursion_position = derive_incursion_position(
            scene,
            mission_mode,
            mission_time_s,
            track_time_remaining_s,
            tier1_engagement_time_remaining_s,
            reference,
            active=incursion_active,
        )
    return RenderState(
        vehicle=RenderEntityState(
            label="SENTRY",
            position=vehicle_position,
            speed_mps=derive_render_speed_mps( mission_mode, current_speed_mps, fallback_speed_mps ),
            spotlight_on=spotlight_on,
            speaker_on=speaker_on,
        ),
        incursion=RenderIncursionState(
            position=resolved_incursion_position,
            active=resolved_incursion_position is not None,
            radius_m=incursion_radius_m,
        ),
    )


def build_render_state_for_modeled(
    scene: RenderScene,
    state: Any,
    reference: ReferenceMetrics,
    *,
    fallback_speed_mps: float | None = None,
    incursion_active: bool = True,
) -> RenderState:
    vehicle_position = derive_vehicle_position( scene, state, reference )
    return build_render_state(
        scene,
        getattr( state, "mission_mode", None ),
        getattr( state, "mission_time_s", None ),
        getattr( state, "current_speed_mps", None ),
        getattr( state, "track_time_remaining_s", None ),
        getattr( state, "tier1_engagement_time_remaining_s", None ),
        reference,
        vehicle_position=vehicle_position,
        attributes=getattr( state, "attributes", None ),
        incursion_active=incursion_active,
        fallback_speed_mps=fallback_speed_mps,
    )
