from __future__ import annotations

from dataclasses import dataclass

from app.services.geometry import distance_m, path_distance_m, sample_path_points
from app.services.mission_mode import canonical_mission_mode
from app.services.mission_projection import LiveMissionProjection, ReferenceMetrics, derive_vehicle_position, resolve_live_phase
from app.services.reference_scene import build_reference_scene


@dataclass
class _State:
    mission_time_s: float | None
    mission_mode: str | None
    current_speed_mps: float | None
    distance_to_base_m: float | None
    distance_to_perimeter_m: float | None
    patrol_distance_remaining_m: float | None
    track_time_remaining_s: float | None
    tier1_engagement_time_remaining_s: float | None
    low_battery_triggered: bool | None = None
    returned_early: bool | None = None
    mission_complete: bool | None = None


def test_canonical_mission_mode_normalizes_named_element_strings() -> None:
    raw_mode = "com.nomagic.uml2.ext.magicdraw.statemachines.mdbehaviorstatemachines.State@1234::TransitToPerimeter"
    assert canonical_mission_mode( raw_mode ) == "TRANSIT_TO_PERIMETER"


def test_vehicle_position_stays_near_base_at_early_mission_time() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
    )

    early_state = _State(
        mission_time_s=2.0,
        mission_mode="PATROL",
        current_speed_mps=5.0,
        distance_to_base_m=0.0,
        distance_to_perimeter_m=300.0,
        patrol_distance_remaining_m=600.0,
        track_time_remaining_s=300.0,
        tier1_engagement_time_remaining_s=180.0,
    )

    early_position = derive_vehicle_position( scene, early_state, reference )

    assert distance_m( scene.base, early_position ) < 60.0


def test_vehicle_position_advances_with_mission_time_during_outbound_phase() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
    )

    start_state = _State(
        mission_time_s=2.0,
        mission_mode="PATROL",
        current_speed_mps=5.0,
        distance_to_base_m=0.0,
        distance_to_perimeter_m=300.0,
        patrol_distance_remaining_m=600.0,
        track_time_remaining_s=300.0,
        tier1_engagement_time_remaining_s=180.0,
    )
    later_state = _State(
        mission_time_s=20.0,
        mission_mode="PATROL",
        current_speed_mps=5.0,
        distance_to_base_m=0.0,
        distance_to_perimeter_m=140.0,
        patrol_distance_remaining_m=600.0,
        track_time_remaining_s=300.0,
        tier1_engagement_time_remaining_s=180.0,
    )

    start_position = derive_vehicle_position( scene, start_state, reference )
    later_position = derive_vehicle_position( scene, later_state, reference )

    assert distance_m( scene.base, later_position ) > distance_m( scene.base, start_position ) + 20.0


def test_outbound_metric_takes_precedence_over_patrol_mode() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
    )

    state = _State(
        mission_time_s=18.0,
        mission_mode="PATROL",
        current_speed_mps=5.0,
        distance_to_base_m=0.0,
        distance_to_perimeter_m=180.0,
        patrol_distance_remaining_m=590.0,
        track_time_remaining_s=300.0,
        tier1_engagement_time_remaining_s=180.0,
    )

    position = derive_vehicle_position( scene, state, reference )
    patrol_entry = scene.patrol_route[ 0 ]

    assert distance_m( scene.base, position ) < distance_m( patrol_entry, position )


def test_live_phase_uses_mission_mode_over_preinitialized_remaining_timers() -> None:
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    state = _State(
        mission_time_s=80.0,
        mission_mode="PATROL",
        current_speed_mps=5.0,
        distance_to_base_m=0.0,
        distance_to_perimeter_m=0.0,
        patrol_distance_remaining_m=600.0,
        track_time_remaining_s=300.0,
        tier1_engagement_time_remaining_s=180.0,
    )

    assert resolve_live_phase( state, reference ) == "patrol"


def test_live_phase_does_not_infer_return_from_positive_distance_to_base_alone() -> None:
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    state = _State(
        mission_time_s=12.0,
        mission_mode="PATROL",
        current_speed_mps=5.0,
        distance_to_base_m=300.0,
        distance_to_perimeter_m=0.0,
        patrol_distance_remaining_m=420.0,
        track_time_remaining_s=300.0,
        tier1_engagement_time_remaining_s=180.0,
    )

    assert resolve_live_phase( state, reference ) == "patrol"


def test_live_phase_does_not_enter_return_before_mode_changes() -> None:
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    state = _State(
        mission_time_s=458.0,
        mission_mode="PATROL",
        current_speed_mps=5.0,
        distance_to_base_m=0.0,
        distance_to_perimeter_m=0.0,
        patrol_distance_remaining_m=0.0,
        track_time_remaining_s=0.0,
        tier1_engagement_time_remaining_s=0.0,
        low_battery_triggered=True,
        returned_early=True,
    )

    assert resolve_live_phase( state, reference ) == "patrol"


def test_live_projection_advances_patrol_on_successive_mission_ticks() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    patrol_at_80 = projection.advance(
        scene,
        _State(
            mission_time_s=80.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-patrol",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    patrol_at_120 = projection.advance(
        scene,
        _State(
            mission_time_s=120.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-patrol",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )

    assert distance_m( patrol_at_80.vehicle_position, patrol_at_120.vehicle_position ) > 80.0


def test_live_projection_track_phase_spawns_incursion_near_vehicle() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    projection.advance(
        scene,
        _State(
            mission_time_s=120.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=360.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-track-patrol",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    track_result = projection.advance(
        scene,
        _State(
            mission_time_s=176.0,
            mission_mode="TRACK",
            current_speed_mps=5.0,
            distance_to_base_m=220.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=260.0,
            track_time_remaining_s=124.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-track-patrol",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )

    patrol_samples = sample_path_points( scene.patrol_route, 8.0 )
    closest_patrol_distance = min( distance_m( track_result.vehicle_position, sample ) for sample in patrol_samples )

    assert closest_patrol_distance < 80.0
    assert track_result.incursion_position is not None
    assert distance_m( track_result.vehicle_position, track_result.incursion_position ) < 80.0


def test_live_projection_incursion_render_moves_faster_than_modeled_track_window() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    projection.advance(
        scene,
        _State(
            mission_time_s=176.0,
            mission_mode="TRACK",
            current_speed_mps=5.0,
            distance_to_base_m=220.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=260.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-incursion-speed",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    mid_track = projection.advance(
        scene,
        _State(
            mission_time_s=326.0,
            mission_mode="TRACK",
            current_speed_mps=5.0,
            distance_to_base_m=220.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=260.0,
            track_time_remaining_s=150.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-incursion-speed",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )

    assert mid_track.incursion_position is not None
    assert distance_m( mid_track.incursion_position, scene.incursion_route[-1] ) < 10.0


def test_live_projection_holds_position_without_new_mission_tick() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    first = projection.advance(
        scene,
        _State(
            mission_time_s=80.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-static",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    second = projection.advance(
        scene,
        _State(
            mission_time_s=80.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-static",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )

    assert distance_m( first.vehicle_position, second.vehicle_position ) < 0.5


def test_live_projection_advances_outbound_from_base_before_patrol() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    at_start = projection.advance(
        scene,
        _State(
            mission_time_s=0.0,
            mission_mode="IDLE",
            current_speed_mps=0.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=300.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-outbound",
        fallback_speed_mps=8.0,
        incursion_speed_mps=4.0,
    )
    at_ten = projection.advance(
        scene,
        _State(
            mission_time_s=10.0,
            mission_mode="PATROL",
            current_speed_mps=8.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=220.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-outbound",
        fallback_speed_mps=8.0,
        incursion_speed_mps=4.0,
    )

    assert distance_m( scene.base, at_start.vehicle_position ) < 5.0
    assert distance_m( scene.base, at_ten.vehicle_position ) > 20.0


def test_live_projection_track_phase_does_not_reset_vehicle_to_base() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    patrol = projection.advance(
        scene,
        _State(
            mission_time_s=80.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=300.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-track",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    track = projection.advance(
        scene,
        _State(
            mission_time_s=120.0,
            mission_mode="TRACK",
            current_speed_mps=5.0,
            distance_to_base_m=300.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=600.0,
            track_time_remaining_s=260.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-track",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )

    assert distance_m( scene.base, patrol.vehicle_position ) > 25.0
    assert distance_m( scene.base, track.vehicle_position ) > 25.0
    assert distance_m( patrol.vehicle_position, track.vehicle_position ) > 10.0


def test_reference_scene_incursion_route_starts_on_patrol_perimeter() -> None:
    scene = build_reference_scene()
    patrol_samples = [
        sample.__class__( lon=sample.lon, lat=sample.lat, alt_m=0.0 )
        for sample in sample_path_points( scene.patrol_route, 4.0 )
    ]

    closest_perimeter_distance = min(
        distance_m( scene.incursion_route[ 0 ], sample )
        for sample in patrol_samples
    )

    assert closest_perimeter_distance < 2.0


def test_reference_scene_matches_single_run_timing_geometry() -> None:
    scene = build_reference_scene()

    patrol_length_m = path_distance_m( scene.patrol_route )
    outbound_distance_m = distance_m( scene.base, scene.patrol_route[ 0 ] )
    return_distance_m = distance_m( scene.patrol_route[ -1 ], scene.base )

    assert abs( patrol_length_m - 600.0 ) < 8.0
    assert abs( outbound_distance_m - 300.0 ) < 8.0
    assert abs( return_distance_m - 300.0 ) < 8.0


def test_live_projection_track_phase_spawns_incursion_at_perimeter_entry() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    track_result = projection.advance(
        scene,
        _State(
            mission_time_s=176.0,
            mission_mode="TRACK",
            current_speed_mps=5.0,
            distance_to_base_m=220.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=260.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-track-entry",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )

    assert track_result.incursion_position is not None
    assert distance_m( track_result.incursion_position, scene.incursion_route[ 0 ] ) < 1.0


def test_live_projection_patrol_rejoin_moves_from_engagement_anchor_without_teleport() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    projection.advance(
        scene,
        _State(
            mission_time_s=140.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=330.0,
            track_time_remaining_s=300.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-rejoin",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    projection.advance(
        scene,
        _State(
            mission_time_s=176.0,
            mission_mode="TRACK",
            current_speed_mps=5.0,
            distance_to_base_m=220.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=260.0,
            track_time_remaining_s=124.0,
            tier1_engagement_time_remaining_s=180.0,
        ),
        reference,
        session_id="pytest-rejoin",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    engage_result = projection.advance(
        scene,
        _State(
            mission_time_s=230.0,
            mission_mode="TIER_1_ENGAGE",
            current_speed_mps=5.0,
            distance_to_base_m=220.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=220.0,
            track_time_remaining_s=60.0,
            tier1_engagement_time_remaining_s=126.0,
        ),
        reference,
        session_id="pytest-rejoin",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    resumed_patrol = projection.advance(
        scene,
        _State(
            mission_time_s=232.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=180.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=180.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-rejoin",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    resumed_patrol_later = projection.advance(
        scene,
        _State(
            mission_time_s=242.0,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=170.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=130.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-rejoin",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )

    assert distance_m( engage_result.vehicle_position, resumed_patrol.vehicle_position ) < 35.0
    assert distance_m( resumed_patrol.vehicle_position, resumed_patrol_later.vehicle_position ) > 20.0


def test_live_projection_return_phase_uses_remaining_time_to_fly_back_to_base() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
    )
    projection = LiveMissionProjection()

    patrol_end = projection.advance(
        scene,
        _State(
            mission_time_s=457.5,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=180.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=0.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-return",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    return_started = projection.advance(
        scene,
        _State(
            mission_time_s=458.0,
            mission_mode="TRANSIT_TO_BASE",
            current_speed_mps=8.0,
            distance_to_base_m=300.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=0.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-return",
        fallback_speed_mps=8.0,
        incursion_speed_mps=4.0,
    )
    return_mid = projection.advance(
        scene,
        _State(
            mission_time_s=470.0,
            mission_mode="TRANSIT_TO_BASE",
            current_speed_mps=8.0,
            distance_to_base_m=204.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=0.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-return",
        fallback_speed_mps=8.0,
        incursion_speed_mps=4.0,
    )

    assert distance_m( patrol_end.vehicle_position, return_started.vehicle_position ) < 35.0
    assert distance_m( scene.base, return_started.vehicle_position ) > 200.0
    assert distance_m( scene.base, return_mid.vehicle_position ) < distance_m( scene.base, return_started.vehicle_position ) - 60.0


def test_live_projection_return_transition_does_not_teleport_when_first_tick_reports_zero_distance() -> None:
    scene = build_reference_scene()
    reference = ReferenceMetrics(
        distance_to_perimeter_start_m=300.0,
        patrol_distance_start_m=600.0,
        track_time_start_s=300.0,
        tier1_engagement_start_s=180.0,
        distance_to_base_start_m=300.0,
    )
    projection = LiveMissionProjection()

    patrol_end = projection.advance(
        scene,
        _State(
            mission_time_s=457.5,
            mission_mode="PATROL",
            current_speed_mps=5.0,
            distance_to_base_m=180.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=0.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-return-zero",
        fallback_speed_mps=5.0,
        incursion_speed_mps=4.0,
    )
    return_started = projection.advance(
        scene,
        _State(
            mission_time_s=458.0,
            mission_mode="TRANSIT_TO_BASE",
            current_speed_mps=8.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=0.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-return-zero",
        fallback_speed_mps=8.0,
        incursion_speed_mps=4.0,
    )
    return_later = projection.advance(
        scene,
        _State(
            mission_time_s=470.0,
            mission_mode="TRANSIT_TO_BASE",
            current_speed_mps=8.0,
            distance_to_base_m=0.0,
            distance_to_perimeter_m=0.0,
            patrol_distance_remaining_m=0.0,
            track_time_remaining_s=0.0,
            tier1_engagement_time_remaining_s=0.0,
        ),
        reference,
        session_id="pytest-return-zero",
        fallback_speed_mps=8.0,
        incursion_speed_mps=4.0,
    )

    assert distance_m( patrol_end.vehicle_position, return_started.vehicle_position ) < 20.0
    assert distance_m( scene.base, return_started.vehicle_position ) > 200.0
    assert distance_m( scene.base, return_later.vehicle_position ) < distance_m( scene.base, return_started.vehicle_position ) - 60.0
