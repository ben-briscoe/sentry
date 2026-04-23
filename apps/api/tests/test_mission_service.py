from __future__ import annotations

from app.services.geometry import distance_m
from app.schemas import (
    Coordinate,
    MissionBridgeAckRequest,
    MissionCommandRequest,
    MissionPerturbationRequest,
    MissionServiceCreateRequest,
    MissionSyncRequest,
    ModeledMissionSnapshot,
    RoutePlanRequest,
)
from app.services.mission_control import MissionServiceStore
from app.services.mission_routes import plan_route_request


def test_route_plan_patrol_loop_returns_distance_and_closed_waypoints() -> None:
    response = plan_route_request(
        RoutePlanRequest(
            kind="patrol_loop",
            start=Coordinate( lon=-85.4890, lat=32.6025, alt_m=0.0 ),
            patrol_area=[
                Coordinate( lon=-85.4925, lat=32.6045, alt_m=0.0 ),
                Coordinate( lon=-85.4855, lat=32.6045, alt_m=0.0 ),
                Coordinate( lon=-85.4855, lat=32.6005, alt_m=0.0 ),
                Coordinate( lon=-85.4925, lat=32.6005, alt_m=0.0 ),
            ],
        )
    )

    assert response.kind == "patrol_loop"
    assert len( response.waypoints ) == 5
    assert response.waypoints[ 0 ] == response.waypoints[ -1 ]
    assert response.estimated_distance_m is not None and response.estimated_distance_m > 0.0
    assert "Inset patrol loop" in response.note


def test_mission_session_command_and_perturbation_flow() -> None:
    store = MissionServiceStore()
    snapshot = store.create( MissionServiceCreateRequest() )
    session = store.get( snapshot.session_id )

    assigned = session.apply_command( MissionCommandRequest( kind="assign_patrol" ) )
    assert assigned.snapshot.active_route_kind == "patrol_loop"
    assert assigned.snapshot.patrol_assigned is True
    assert session.bridge_state().pending_command_kind == "assign_patrol"
    assert session.bridge_state().command_revision == 1
    assert session.bridge_state().route_revision == 1

    intercept = session.apply_command( MissionCommandRequest( kind="intercept_incursion" ) )
    assert intercept.snapshot.active_route_kind == "track"
    assert intercept.route_plan is not None and intercept.route_plan.intercept_point is not None
    assert session.bridge_state().pending_command_kind == "intercept_incursion"

    playback = session.apply_command(
        MissionCommandRequest( kind="set_playback_speed", playback_speed=4.0, real_time=True )
    )
    assert playback.command == "set_playback_speed"
    assert session.bridge_state().pending_command_kind == "set_playback_speed"
    assert session.bridge_state().pending_playback_speed == 4.0
    assert session.bridge_state().pending_real_time is True

    perturb = session.apply_perturbation(
        MissionPerturbationRequest( kind="route_deviation", offset_m=25.0, direction="left" )
    )
    assert perturb.snapshot.active_route_kind == "track"
    assert "Incursion route laterally deviated" in perturb.note
    assert session.bridge_state().pending_command_kind == "route_deviation"

    cleared = session.apply_perturbation( MissionPerturbationRequest( kind="all_clear" ) )
    assert cleared.snapshot.incursion_active is False
    assert cleared.snapshot.active_route_kind == "patrol_loop"
    assert session.bridge_state().pending_command_kind == "all_clear"

    ack = session.acknowledge_bridge_updates(
        MissionBridgeAckRequest(
            command_revision_applied=session.bridge_state().command_revision,
            route_revision_applied=session.bridge_state().route_revision,
        )
    )
    assert ack.bridge_state.pending_command_kind is None
    assert ack.bridge_state.command_revision_applied == ack.bridge_state.command_revision


def test_mission_sync_tracks_modeled_open_loop_state() -> None:
    store = MissionServiceStore()
    snapshot = store.create( MissionServiceCreateRequest() )
    session = store.get( snapshot.session_id )

    patrol_sync = session.sync_modeled_state(
        MissionSyncRequest(
            modeled_state=ModeledMissionSnapshot(
                time_ms=12000.0,
                mission_mode="PATROL",
                mission_time_s=12.0,
                real_time=True,
                playback_speed=2.0,
                simulation_rate_hz=1.0,
                current_speed_mps=5.0,
                current_propulsion_power_w=180.0,
                current_total_power_w=217.0,
                current_load_w=37.0,
                remaining_energy_j=498000.0,
                distance_to_base_m=300.0,
                distance_to_perimeter_m=0.0,
                patrol_distance_remaining_m=420.0,
                track_time_remaining_s=300.0,
                tier1_engagement_time_remaining_s=180.0,
                low_battery_triggered=False,
                returned_early=False,
                mission_complete=False,
                attributes={ "source": "pytest_patrol" },
            )
        )
    )
    assert patrol_sync.snapshot.active_route_kind == "patrol_loop"
    assert patrol_sync.suggested_command is None
    assert patrol_sync.modeled_state.mission_mode == "PATROL"
    assert patrol_sync.modeled_state.real_time is True
    assert patrol_sync.modeled_state.playback_speed == 2.0
    assert patrol_sync.snapshot.scene.structures == []
    assert len( patrol_sync.snapshot.scene.patrol_route ) >= 4

    track_sync = session.sync_modeled_state(
        MissionSyncRequest(
            modeled_state=ModeledMissionSnapshot(
                time_ms=18000.0,
                mission_mode="TRACK",
                mission_time_s=18.0,
                current_speed_mps=8.0,
                distance_to_base_m=300.0,
                patrol_distance_remaining_m=300.0,
                track_time_remaining_s=120.0,
                tier1_engagement_time_remaining_s=180.0,
                mission_complete=False,
                attributes={ "source": "pytest_track" },
            )
        )
    )
    assert track_sync.snapshot.active_route_kind == "track"
    assert track_sync.suggested_command == "intercept_incursion"
    assert track_sync.recommended_route is not None


def test_mission_session_list_and_view_reflect_live_sync_state() -> None:
    store = MissionServiceStore()
    snapshot = store.create( MissionServiceCreateRequest() )
    session_id = snapshot.session_id

    listed = store.list()
    assert listed[ 0 ].session_id == session_id
    assert listed[ 0 ].mission_mode is None

    sync = store.get( session_id ).sync_modeled_state(
        MissionSyncRequest(
            modeled_state=ModeledMissionSnapshot(
                mission_mode="PATROL",
                mission_time_s=12.0,
                remaining_energy_j=498000.0,
                patrol_distance_remaining_m=420.0,
            )
        )
    )

    view = store.get( session_id ).view()
    assert view.snapshot.session_id == session_id
    assert view.modeled_state is not None
    assert view.modeled_state.mission_mode == "PATROL"
    assert view.render_state.vehicle.label.startswith( "SENTRY" )
    assert view.render_state.incursion.active is False
    assert view.bridge_state.command_revision == 0

    listed_after_sync = store.list()
    assert listed_after_sync[ 0 ].session_id == session_id
    assert listed_after_sync[ 0 ].mission_mode == "PATROL"
    assert sync.snapshot.active_route_kind == "patrol_loop"


def test_mission_session_render_state_advances_with_live_sync_ticks() -> None:
    store = MissionServiceStore()
    snapshot = store.create( MissionServiceCreateRequest() )
    session = store.get( snapshot.session_id )

    session.sync_modeled_state(
        MissionSyncRequest(
            modeled_state=ModeledMissionSnapshot(
                time_ms=80000.0,
                mission_mode="PATROL",
                mission_time_s=80.0,
                current_speed_mps=5.0,
                distance_to_base_m=0.0,
                distance_to_perimeter_m=0.0,
                patrol_distance_remaining_m=600.0,
                track_time_remaining_s=300.0,
                tier1_engagement_time_remaining_s=180.0,
                mission_complete=False,
            )
        )
    )
    first_view = session.view()

    session.sync_modeled_state(
        MissionSyncRequest(
            modeled_state=ModeledMissionSnapshot(
                time_ms=120000.0,
                mission_mode="PATROL",
                mission_time_s=120.0,
                current_speed_mps=5.0,
                distance_to_base_m=0.0,
                distance_to_perimeter_m=0.0,
                patrol_distance_remaining_m=600.0,
                track_time_remaining_s=300.0,
                tier1_engagement_time_remaining_s=180.0,
                mission_complete=False,
            )
        )
    )
    second_view = session.view()

    assert distance_m( first_view.render_state.vehicle.position, second_view.render_state.vehicle.position ) > 80.0


def test_render_effects_match_track_and_tier1_story() -> None:
    store = MissionServiceStore()
    snapshot = store.create( MissionServiceCreateRequest() )
    session = store.get( snapshot.session_id )

    session.sync_modeled_state(
        MissionSyncRequest(
            modeled_state=ModeledMissionSnapshot(
                time_ms=120000.0,
                mission_mode="TRACK",
                mission_time_s=120.0,
                current_speed_mps=5.0,
                distance_to_base_m=280.0,
                patrol_distance_remaining_m=260.0,
                track_time_remaining_s=120.0,
                tier1_engagement_time_remaining_s=180.0,
                mission_complete=False,
            )
        )
    )
    track_view = session.view()

    assert track_view.render_state.vehicle.spotlight_on is True
    assert track_view.render_state.vehicle.speaker_on is False
    assert track_view.render_state.incursion.active is True
    assert track_view.render_state.incursion.position is not None

    session.sync_modeled_state(
        MissionSyncRequest(
            modeled_state=ModeledMissionSnapshot(
                time_ms=180000.0,
                mission_mode="TIER_1_ENGAGE",
                mission_time_s=180.0,
                current_speed_mps=5.0,
                distance_to_base_m=310.0,
                patrol_distance_remaining_m=180.0,
                track_time_remaining_s=40.0,
                tier1_engagement_time_remaining_s=120.0,
                mission_complete=False,
            )
        )
    )
    engage_view = session.view()

    assert engage_view.render_state.vehicle.spotlight_on is True
    assert engage_view.render_state.vehicle.speaker_on is True
    assert engage_view.render_state.incursion.active is True
