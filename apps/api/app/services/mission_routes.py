from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.schemas import Coordinate, RoutePlanRequest, RoutePlanResponse

from .geometry import centroid, distance_m, move_toward, offset_path_laterally, path_distance_m, rotate_path_to_anchor, sample_path


@dataclass( frozen=True )
class _InterceptSolution:
    intercept_point: Coordinate
    target_distance_m: float
    intercept_index: int
    feasible: bool


def _closed_loop( points: list[ Coordinate ] ) -> list[ Coordinate ]:
    if not points:
        return []
    if points[ 0 ] == points[ -1 ]:
        return list( points )
    return [ *points, points[ 0 ] ]


def _segment_lengths( points: list[ Coordinate ] ) -> list[ float ]:
    return [ distance_m( points[ index - 1 ], points[ index ] ) for index in range( 1, len( points ) ) ]


def _plan_patrol_loop( request: RoutePlanRequest ) -> RoutePlanResponse:
    if len( request.patrol_area ) < 3:
        raise HTTPException( status_code=400, detail="patrol_loop requires at least 3 patrol-area points" )

    area_loop = _closed_loop( request.patrol_area )
    center = centroid( area_loop[ :-1 ] if area_loop[ 0 ] == area_loop[ -1 ] else area_loop )
    interior_ratio = 1.0 - request.patrol_inset_ratio
    route = [ move_toward( point, center, request.patrol_inset_ratio ) for point in area_loop ]
    route = _closed_loop( route )

    if request.start is not None:
        route = rotate_path_to_anchor( route, request.start )

    estimated_distance_m = path_distance_m( route )
    return RoutePlanResponse(
        kind=request.kind,
        waypoints=route,
        note=(
            "Inset patrol loop generated from the provided patrol area. "
            f"Vertices are moved {request.patrol_inset_ratio:.0%} toward the patrol-area centroid "
            f"to create a representative interior route ({interior_ratio:.0%} of the original radius)."
        ),
        estimated_distance_m=estimated_distance_m,
        estimated_duration_s=estimated_distance_m / request.ownship_speed_mps if request.ownship_speed_mps > 0.0 else None,
    )


def _plan_recall_route( request: RoutePlanRequest ) -> RoutePlanResponse:
    if request.start is None or request.end is None:
        raise HTTPException( status_code=400, detail="recall requires start and end coordinates" )

    waypoints = [ request.start, request.end ]
    estimated_distance_m = path_distance_m( waypoints )
    return RoutePlanResponse(
        kind=request.kind,
        waypoints=waypoints,
        note="Direct recall route from the current sentry position back to base.",
        estimated_distance_m=estimated_distance_m,
        estimated_duration_s=estimated_distance_m / request.ownship_speed_mps if request.ownship_speed_mps > 0.0 else None,
    )


def _find_intercept( request: RoutePlanRequest ) -> _InterceptSolution:
    if request.start is None:
        raise HTTPException( status_code=400, detail=f"{request.kind} requires a start coordinate" )
    if len( request.target_route ) < 2:
        raise HTTPException( status_code=400, detail=f"{request.kind} requires at least 2 target-route coordinates" )

    step_m = max( min( request.route_offset_m, 50.0 ), 5.0 )
    segment_lengths = _segment_lengths( request.target_route )
    total_distance_m = sum( segment_lengths )
    sampled_distance_m = 0.0
    sample_index = 0
    last_sample = request.target_route[ -1 ]

    while sampled_distance_m <= total_distance_m + 1e-6:
        candidate = sample_path( request.target_route, sampled_distance_m )
        target_time_s = sampled_distance_m / request.target_speed_mps if request.target_speed_mps > 0.0 else 0.0
        sentry_time_s = distance_m( request.start, candidate ) / request.ownship_speed_mps
        if sentry_time_s <= target_time_s:
            return _InterceptSolution(
                intercept_point=candidate,
                target_distance_m=sampled_distance_m,
                intercept_index=sample_index,
                feasible=True,
            )
        last_sample = candidate
        sampled_distance_m += step_m
        sample_index += 1

    return _InterceptSolution(
        intercept_point=last_sample,
        target_distance_m=total_distance_m,
        intercept_index=sample_index,
        feasible=False,
    )


def _plan_intercept_or_track( request: RoutePlanRequest ) -> RoutePlanResponse:
    solution = _find_intercept( request )
    assert request.start is not None  # guarded in _find_intercept

    if request.kind == "intercept":
        waypoints = [ request.start, solution.intercept_point ]
    else:
        waypoints = [ request.start, solution.intercept_point, request.target_route[ -1 ] ]

    estimated_distance_m = path_distance_m( waypoints )
    note = (
        "Predicted intercept route based on current ownship and incursion speeds."
        if solution.feasible
        else "Fallback track route to the end of the incursion path because no earlier intercept point was reachable."
    )
    if request.kind == "track":
        note = note.replace( "intercept route", "track route" )

    return RoutePlanResponse(
        kind=request.kind,
        waypoints=waypoints,
        note=note,
        estimated_distance_m=estimated_distance_m,
        estimated_duration_s=estimated_distance_m / request.ownship_speed_mps if request.ownship_speed_mps > 0.0 else None,
        intercept_point=solution.intercept_point,
    )


def plan_route_request( request: RoutePlanRequest ) -> RoutePlanResponse:
    if request.kind == "patrol_loop":
        return _plan_patrol_loop( request )

    if request.kind == "recall":
        return _plan_recall_route( request )

    if request.kind in { "intercept", "track" }:
        return _plan_intercept_or_track( request )

    raise HTTPException( status_code=400, detail=f"Unsupported route kind: {request.kind}" )


def deviate_route( route: list[ Coordinate ], *, offset_m: float, direction: str ) -> list[ Coordinate ]:
    return offset_path_laterally( route, offset_m, direction=direction )
