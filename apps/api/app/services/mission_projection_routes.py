from __future__ import annotations

from app.schemas import Coordinate, RenderScene

from .geometry import distance_m, offset_path_laterally, rotate_path_to_anchor


PATROL_ALTITUDE_M = 42.0
TRACK_ALTITUDE_M = 36.0
ENGAGEMENT_ALTITUDE_M = 30.0
CLIMBOUT_ALTITUDE_M = 18.0
TRANSIT_ALTITUDE_M = 34.0
TRACK_STANDOFF_M = 12.0
ENGAGEMENT_STANDOFF_M = 6.0
TRANSIT_SPEED_MPS = 8.0
PATROL_SPEED_MPS = 5.0
TRACK_SPEED_MPS = 5.5
RETURN_SPEED_MPS = 8.0


def lift_coordinate( point: Coordinate, altitude_m: float ) -> Coordinate:
    return Coordinate( lon=point.lon, lat=point.lat, alt_m=max( point.alt_m, altitude_m ) )


def blend_coordinate( start: Coordinate, end: Coordinate, ratio: float, altitude_m: float ) -> Coordinate:
    clamped = min( max( ratio, 0.0 ), 1.0 )
    return Coordinate(
        lon=start.lon + ( end.lon - start.lon ) * clamped,
        lat=start.lat + ( end.lat - start.lat ) * clamped,
        alt_m=altitude_m,
    )


def patrol_waypoints( scene: RenderScene, *, anchor: Coordinate | None = None ) -> list[ Coordinate ]:
    patrol = [ lift_coordinate( point, PATROL_ALTITUDE_M ) for point in _open_route( scene.patrol_route ) ]
    if anchor is not None and patrol:
        patrol = rotate_path_to_anchor( patrol, lift_coordinate( anchor, PATROL_ALTITUDE_M ) )
    return patrol


def outbound_waypoints( scene: RenderScene, *, start: Coordinate ) -> list[ Coordinate ]:
    patrol = patrol_waypoints( scene )
    patrol_entry = patrol[ 0 ] if patrol else lift_coordinate( scene.base, PATROL_ALTITUDE_M )
    return _dedupe_waypoints( [
        start,
        lift_coordinate( start, CLIMBOUT_ALTITUDE_M ),
        blend_coordinate( start, patrol_entry, 0.26, TRANSIT_ALTITUDE_M ),
        blend_coordinate( start, patrol_entry, 0.62, PATROL_ALTITUDE_M ),
        patrol_entry,
    ] )


def return_waypoints( scene: RenderScene, *, start: Coordinate ) -> list[ Coordinate ]:
    return _dedupe_waypoints( [
        start,
        blend_coordinate( start, scene.base, 0.30, PATROL_ALTITUDE_M ),
        blend_coordinate( start, scene.base, 0.68, TRANSIT_ALTITUDE_M ),
        lift_coordinate( scene.base, CLIMBOUT_ALTITUDE_M ),
        scene.base,
    ] )


def track_waypoints( scene: RenderScene, *, anchor: Coordinate, incursion_anchor: Coordinate | None ) -> list[ Coordinate ]:
    shadow = _shadow_waypoints( scene, stand_off_m=TRACK_STANDOFF_M, altitude_m=TRACK_ALTITUDE_M )
    tail = _route_tail_from_anchor( shadow, incursion_anchor )
    if not tail:
        return [ anchor ]
    join = tail[ 0 ]
    return _dedupe_waypoints( [
        anchor,
        blend_coordinate( anchor, join, 0.38, TRACK_ALTITUDE_M ),
        join,
        *tail[ 1: ],
    ] )


def engagement_waypoints( scene: RenderScene, *, anchor: Coordinate, incursion_anchor: Coordinate | None ) -> list[ Coordinate ]:
    shadow = _shadow_waypoints( scene, stand_off_m=ENGAGEMENT_STANDOFF_M, altitude_m=ENGAGEMENT_ALTITUDE_M )
    tail = _route_tail_from_anchor( shadow, incursion_anchor )
    if not tail:
        return [ anchor ]
    join = tail[ 0 ]
    return _dedupe_waypoints( [
        anchor,
        blend_coordinate( anchor, join, 0.48, ENGAGEMENT_ALTITUDE_M ),
        join,
        *tail[ 1: ],
    ] )


def patrol_rejoin_waypoints( scene: RenderScene, *, anchor: Coordinate ) -> list[ Coordinate ]:
    patrol = patrol_waypoints( scene )
    tail = _route_tail_from_anchor( patrol, lift_coordinate( anchor, PATROL_ALTITUDE_M ) ) if patrol else []
    if not tail:
        return [ anchor ]
    join = tail[ 0 ]
    if distance_m( anchor, join ) <= 5.0:
        return _dedupe_waypoints( [ anchor, *tail[ 1: ] ] )
    return _dedupe_waypoints( [
        anchor,
        blend_coordinate( anchor, join, 0.42, PATROL_ALTITUDE_M ),
        join,
        *tail[ 1: ],
    ] )


def _dedupe_waypoints( points: list[ Coordinate ] ) -> list[ Coordinate ]:
    deduped: list[ Coordinate ] = []
    for point in points:
        if deduped and deduped[ -1 ] == point:
            continue
        deduped.append( point )
    return deduped


def _open_route( points: list[ Coordinate ] ) -> list[ Coordinate ]:
    if len( points ) >= 2 and points[ 0 ] == points[ -1 ]:
        return list( points[ :-1 ] )
    return list( points )


def _closest_index( points: list[ Coordinate ], anchor: Coordinate ) -> int:
    if not points:
        return 0
    return min( range( len( points ) ), key=lambda index: distance_m( anchor, points[ index ] ) )


def _route_tail_from_anchor( points: list[ Coordinate ], anchor: Coordinate | None ) -> list[ Coordinate ]:
    if not points:
        return []
    if anchor is None:
        return list( points )
    start_index = _closest_index( points, anchor )
    return list( points[ start_index: ] )


def _shadow_waypoints( scene: RenderScene, *, stand_off_m: float, altitude_m: float ) -> list[ Coordinate ]:
    return [ lift_coordinate( point, altitude_m ) for point in offset_path_laterally( scene.incursion_route, stand_off_m, direction="left" ) ]
