from __future__ import annotations

import math

from app.schemas import Coordinate


def _lon_scale_m( latitude_deg: float ) -> float:
    return 111_320.0 * math.cos( math.radians( latitude_deg ) )


def distance_m( start: Coordinate, end: Coordinate ) -> float:
    lon_scale = _lon_scale_m( ( start.lat + end.lat ) / 2.0 )
    lat_scale = 111_132.0
    dx = ( end.lon - start.lon ) * lon_scale
    dy = ( end.lat - start.lat ) * lat_scale
    dz = end.alt_m - start.alt_m
    return math.sqrt( dx * dx + dy * dy + dz * dz )


def path_distance_m( points: list[ Coordinate ] ) -> float:
    if len( points ) < 2:
        return 0.0
    total = 0.0
    for index in range( 1, len( points ) ):
        total += distance_m( points[ index - 1 ], points[ index ] )
    return total


def centroid( points: list[ Coordinate ] ) -> Coordinate:
    if not points:
        return Coordinate( lon=0.0, lat=0.0, alt_m=0.0 )
    lon = sum( point.lon for point in points ) / len( points )
    lat = sum( point.lat for point in points ) / len( points )
    alt = sum( point.alt_m for point in points ) / len( points )
    return Coordinate( lon=lon, lat=lat, alt_m=alt )


def _local_xy_m( origin: Coordinate, point: Coordinate ) -> tuple[ float, float ]:
    lon_scale = _lon_scale_m( origin.lat )
    lat_scale = 111_132.0
    return (
        ( point.lon - origin.lon ) * lon_scale,
        ( point.lat - origin.lat ) * lat_scale,
    )


def _from_local_xy_m( origin: Coordinate, x_m: float, y_m: float, *, alt_m: float ) -> Coordinate:
    lon_scale = _lon_scale_m( origin.lat )
    lat_scale = 111_132.0
    lon = origin.lon + ( x_m / lon_scale if lon_scale else 0.0 )
    lat = origin.lat + ( y_m / lat_scale if lat_scale else 0.0 )
    return Coordinate( lon=lon, lat=lat, alt_m=alt_m )


def move_toward( point: Coordinate, target: Coordinate, ratio: float ) -> Coordinate:
    clamped = min( max( ratio, 0.0 ), 1.0 )
    return Coordinate(
        lon=point.lon + ( target.lon - point.lon ) * clamped,
        lat=point.lat + ( target.lat - point.lat ) * clamped,
        alt_m=point.alt_m + ( target.alt_m - point.alt_m ) * clamped,
    )


def rotate_path_to_anchor( points: list[ Coordinate ], anchor: Coordinate ) -> list[ Coordinate ]:
    if len( points ) < 2:
        return list( points )

    closed = points[ 0 ] == points[ -1 ]
    core = points[ :-1 ] if closed else list( points )
    if not core:
        return list( points )

    best_index = min( range( len( core ) ), key=lambda index: distance_m( anchor, core[ index ] ) )
    rotated = [ *core[ best_index: ], *core[ :best_index ] ]
    if closed:
        rotated.append( rotated[ 0 ] )
    return rotated


def sample_path( points: list[ Coordinate ], distance_along_m: float ) -> Coordinate:
    if not points:
        return Coordinate( lon=0.0, lat=0.0, alt_m=0.0 )
    if len( points ) == 1:
        return points[ 0 ]

    remaining = max( distance_along_m, 0.0 )
    for index in range( 1, len( points ) ):
        start = points[ index - 1 ]
        end = points[ index ]
        segment_length_m = distance_m( start, end )
        if segment_length_m <= 0.0:
            continue
        if remaining <= segment_length_m:
            ratio = remaining / segment_length_m
            return Coordinate(
                lon=start.lon + ( end.lon - start.lon ) * ratio,
                lat=start.lat + ( end.lat - start.lat ) * ratio,
                alt_m=start.alt_m + ( end.alt_m - start.alt_m ) * ratio,
            )
        remaining -= segment_length_m
    return points[ -1 ]


def sample_path_points( points: list[ Coordinate ], step_m: float ) -> list[ Coordinate ]:
    if len( points ) < 2:
        return list( points )

    total_distance_m = path_distance_m( points )
    if total_distance_m <= 0.0 or step_m <= 0.0:
        return list( points )

    sampled = [ points[ 0 ] ]
    distance_cursor_m = step_m
    while distance_cursor_m < total_distance_m:
        sampled.append( sample_path( points, distance_cursor_m ) )
        distance_cursor_m += step_m
    if sampled[ -1 ] != points[ -1 ]:
        sampled.append( points[ -1 ] )
    return sampled


def offset_path_laterally(
    points: list[ Coordinate ],
    offset_m: float,
    *,
    direction: str = "right",
) -> list[ Coordinate ]:
    if len( points ) < 2 or offset_m <= 0.0:
        return list( points )

    origin = points[ 0 ]
    sign = -1.0 if direction == "left" else 1.0
    shifted: list[ Coordinate ] = []
    local_points = [ _local_xy_m( origin, point ) for point in points ]

    for index, point in enumerate( points ):
        prev_x, prev_y = local_points[ index - 1 ] if index > 0 else local_points[ index ]
        next_x, next_y = local_points[ index + 1 ] if index < len( points ) - 1 else local_points[ index ]
        tangent_x = next_x - prev_x
        tangent_y = next_y - prev_y
        tangent_norm = math.hypot( tangent_x, tangent_y )
        if tangent_norm <= 0.0:
            shifted.append( point )
            continue
        normal_x = sign * tangent_y / tangent_norm
        normal_y = -sign * tangent_x / tangent_norm
        point_x, point_y = local_points[ index ]
        shifted.append(
            _from_local_xy_m(
                origin,
                point_x + ( normal_x * offset_m ),
                point_y + ( normal_y * offset_m ),
                alt_m=point.alt_m,
            )
        )
    return shifted
