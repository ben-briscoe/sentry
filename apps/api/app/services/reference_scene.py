from __future__ import annotations

from app.schemas import Coordinate, RenderScene

SCENE_LON_OFFSET = -0.00055
SCENE_LAT_OFFSET = -0.00140


def _point( lon: float, lat: float, alt_m: float = 0.0 ) -> Coordinate:
    return Coordinate(
        lon=lon + SCENE_LON_OFFSET,
        lat=lat + SCENE_LAT_OFFSET,
        alt_m=alt_m,
    )


def _closed( points: list[ Coordinate ] ) -> list[ Coordinate ]:
    if not points:
        return []
    if points[ 0 ] == points[ -1 ]:
        return points
    return [ *points, points[ 0 ] ]


def _lifted( points: list[ tuple[ float, float ] ], altitude_m: float ) -> list[ Coordinate ]:
    return [ _point( lon, lat, altitude_m ) for lon, lat in points ]


def build_reference_scene() -> RenderScene:
    # The laydown is intentionally simplified for the single representative playback:
    # a defended stadium-adjacent zone, a visible patrol perimeter outside it, and
    # an incursion that starts on the perimeter near the model's halfway-to-track
    # transition point. The geometry is tuned to the default single-run timing:
    # ~300 m outbound, ~600 m patrol path, ~300 m return.
    base = _point( -85.48845, 32.60665, 0.0 )

    patrol_area = _closed( [
        _point( -85.48922, 32.60318 ),
        _point( -85.48822, 32.60330 ),
        _point( -85.48736, 32.60296 ),
        _point( -85.48734, 32.60216 ),
        _point( -85.48808, 32.60176 ),
        _point( -85.48906, 32.60182 ),
        _point( -85.48948, 32.60244 ),
    ] )

    patrol_route = _lifted( [
        ( -85.48975, 32.60415 ),
        ( -85.48982, 32.60355 ),
        ( -85.48985, 32.60305 ),
        ( -85.48982, 32.60270 ),
        ( -85.48945, 32.60248 ),
        ( -85.48895, 32.60235 ),
        ( -85.48845, 32.60230 ),
        ( -85.48795, 32.60235 ),
        ( -85.48745, 32.60248 ),
        ( -85.48710, 32.60270 ),
        ( -85.48707, 32.60305 ),
        ( -85.48704, 32.60355 ),
        ( -85.48712, 32.60415 ),
    ], altitude_m=42.0 )

    incursion_route = [
        _point( -85.48845, 32.60230, 0.0 ),
        _point( -85.48826, 32.60243, 0.0 ),
        _point( -85.48805, 32.60254, 0.0 ),
        _point( -85.48784, 32.60263, 0.0 ),
        _point( -85.48766, 32.60274, 0.0 ),
    ]

    return RenderScene(
        id="jordan_hare_event_corridor_v1",
        description=(
            "Representative Auburn event-security playback with a defended stadium-adjacent "
            "area, a visible patrol perimeter, and a nearby perimeter incursion crossing."
        ),
        base=base,
        patrol_area=patrol_area,
        patrol_route=patrol_route,
        incursion_route=incursion_route,
        structures=[],
    )
