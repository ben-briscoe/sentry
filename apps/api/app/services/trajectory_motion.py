from __future__ import annotations

from dataclasses import dataclass
from math import acos, atan2, ceil, cos, exp, pi, radians, sin, sqrt

from app.schemas import Coordinate


# This module is a SENTRY-local adaptation of the multirotor medium-fidelity
# motion path/sampling stack from the trajectory planner project. The goal is
# to keep live playback on the same kind of sampled motion foundation rather
# than using ad hoc route-progress approximations.

_EPSILON = 1e-9
_PATH_INTEGRATION_STEP_S = 0.02
_CENTRIPETAL_ALPHA = 0.5
WGS84_A_M = 6_378_137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * ( 2.0 - WGS84_F )
WGS84_B_M = WGS84_A_M * ( 1.0 - WGS84_F )
WGS84_EP2 = ( WGS84_A_M ** 2 - WGS84_B_M ** 2 ) / ( WGS84_B_M ** 2 )

MULTIROTOR_MED_PROFILE = {
    "family": "multirotor",
    "fidelityVariant": "medFidelity",
    "motionProfile": {
        "speed": {
            "minMps": 0.0,
            "nominalMps": 18.0,
            "maxMps": 28.0,
        },
        "acceleration": {
            "nominalAccelMps2": 3.5,
            "maxAccelMps2": 6.5,
            "nominalDecelMps2": 3.0,
            "maxDecelMps2": 6.0,
            "maxLateralAccelMps2": 5.0,
            "responseTimeConstantS": 0.7,
        },
        "climb": {
            "nominalClimbMps": 4.0,
            "maxClimbMps": 7.0,
            "nominalDescentMps": 3.5,
            "maxDescentMps": 6.0,
            "minOperatingAltitudeM": 0.0,
            "maxOperatingAltitudeM": 5000.0,
        },
        "turn": {
            "nominalTurnRadiusM": 12.0,
            "minTurnRadiusM": 3.0,
            "nominalBankAngleDeg": 18.0,
            "maxBankAngleDeg": 35.0,
            "maxTurnRateDegPerS": 90.0,
            "maxLoadFactor": 2.2,
        },
    },
    "familyProfile": {
        "hoverAllowed": True,
        "rotorCount": 4,
        "maxTiltAngleDeg": 35.0,
        "maxYawRateDegPerS": 160.0,
        "maxHorizontalAccelMps2": 5.5,
        "maxVerticalAccelUpMps2": 5.0,
        "maxVerticalAccelDownMps2": 4.5,
        "maxJerkMps3": 12.0,
    },
}


@dataclass( frozen=True )
class GeodeticPoint:
    lat: float
    lon: float
    h: float


@dataclass( frozen=True )
class EcefPoint:
    x: float
    y: float
    z: float


@dataclass( frozen=True )
class LocalPoint:
    x: float
    y: float
    z: float


@dataclass( frozen=True )
class ControlPoint:
    waypoint_id: str
    geodetic: GeodeticPoint
    trajectory_local: LocalPoint
    action: str
    loiter_time_s: float
    speed_intent: str = "nominal"
    target_speed_mps: float | None = None


@dataclass( frozen=True )
class MotionSpan:
    kind: str
    segment_index: int
    start_local: LocalPoint
    end_local: LocalPoint
    length_m: float
    dwell_time_s: float = 0.0
    center_local: LocalPoint | None = None
    radius_m: float | None = None
    start_angle_rad: float | None = None
    end_angle_rad: float | None = None
    sweep_angle_rad: float | None = None
    turn_direction: int | None = None
    speed_limit_mps: float | None = None


@dataclass( frozen=True )
class IntegratedMotionSample:
    time_s: float
    trajectory_local: LocalPoint
    velocity_local: LocalPoint
    segment_index: int


@dataclass( frozen=True )
class MotionPlan:
    family: str
    fidelity_variant: str
    path_model: str
    samples: list[ IntegratedMotionSample ]
    resolved_speed_mps: float | None
    diagnostics: dict[ str, float | int | str ]

    @property
    def total_duration_s( self ) -> float:
        return self.samples[ -1 ].time_s if self.samples else 0.0


@dataclass( frozen=True )
class TimedCoordinateSample:
    time_s: float
    position: Coordinate


def geodetic_to_ecef( point: GeodeticPoint ) -> EcefPoint:
    lat_rad = radians( point.lat )
    lon_rad = radians( point.lon )
    sin_lat = sin( lat_rad )
    cos_lat = cos( lat_rad )
    sin_lon = sin( lon_rad )
    cos_lon = cos( lon_rad )
    normal_radius = WGS84_A_M / sqrt( 1.0 - WGS84_E2 * sin_lat * sin_lat )
    return EcefPoint(
        x=( normal_radius + point.h ) * cos_lat * cos_lon,
        y=( normal_radius + point.h ) * cos_lat * sin_lon,
        z=( normal_radius * ( 1.0 - WGS84_E2 ) + point.h ) * sin_lat,
    )


def ecef_to_geodetic( point: EcefPoint ) -> GeodeticPoint:
    p = sqrt( point.x * point.x + point.y * point.y )
    theta = atan2( point.z * WGS84_A_M, p * WGS84_B_M )
    sin_theta = sin( theta )
    cos_theta = cos( theta )
    lon_rad = atan2( point.y, point.x )
    lat_rad = atan2(
        point.z + WGS84_EP2 * WGS84_B_M * sin_theta ** 3,
        p - WGS84_E2 * WGS84_A_M * cos_theta ** 3,
    )
    sin_lat = sin( lat_rad )
    normal_radius = WGS84_A_M / sqrt( 1.0 - WGS84_E2 * sin_lat * sin_lat )
    h = p / max( cos( lat_rad ), _EPSILON ) - normal_radius
    return GeodeticPoint( lat=lat_rad * 180.0 / pi, lon=lon_rad * 180.0 / pi, h=h )


def geodetic_to_local( point: GeodeticPoint, origin: GeodeticPoint ) -> LocalPoint:
    origin_ecef = geodetic_to_ecef( origin )
    point_ecef = geodetic_to_ecef( point )
    dx = point_ecef.x - origin_ecef.x
    dy = point_ecef.y - origin_ecef.y
    dz = point_ecef.z - origin_ecef.z
    lat_rad = radians( origin.lat )
    lon_rad = radians( origin.lon )
    sin_lat = sin( lat_rad )
    cos_lat = cos( lat_rad )
    sin_lon = sin( lon_rad )
    cos_lon = cos( lon_rad )
    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
    return LocalPoint( x=east, y=north, z=up )


def local_to_geodetic( point: LocalPoint, origin: GeodeticPoint ) -> GeodeticPoint:
    lat_rad = radians( origin.lat )
    lon_rad = radians( origin.lon )
    sin_lat = sin( lat_rad )
    cos_lat = cos( lat_rad )
    sin_lon = sin( lon_rad )
    cos_lon = cos( lon_rad )
    east = point.x
    north = point.y
    up = point.z
    dx = -sin_lon * east - sin_lat * cos_lon * north + cos_lat * cos_lon * up
    dy = cos_lon * east - sin_lat * sin_lon * north + cos_lat * sin_lon * up
    dz = cos_lat * north + sin_lat * up
    origin_ecef = geodetic_to_ecef( origin )
    return ecef_to_geodetic(
        EcefPoint(
            x=origin_ecef.x + dx,
            y=origin_ecef.y + dy,
            z=origin_ecef.z + dz,
        )
    )


def build_multirotor_route_samples(
    waypoints: list[ Coordinate ],
    *,
    speed_mps: float,
    loop: bool,
    total_duration_s: float | None = None,
    time_step_s: float = 0.25,
) -> list[ TimedCoordinateSample ]:
    if not waypoints:
        return []
    if len( waypoints ) == 1:
        return [ TimedCoordinateSample( time_s=0.0, position=waypoints[ 0 ] ) ]

    local_origin = GeodeticPoint( lat=waypoints[ 0 ].lat, lon=waypoints[ 0 ].lon, h=waypoints[ 0 ].alt_m )
    trajectory_waypoints = list( waypoints )
    if loop and waypoints[ 0 ] != waypoints[ -1 ]:
        trajectory_waypoints = [ *trajectory_waypoints, waypoints[ 0 ] ]

    control_points = _build_control_points( trajectory_waypoints, local_origin )
    motion_plan = build_multirotor_motion_plan( control_points, speed_mps=speed_mps )
    resampled = resample_motion_plan_by_time( motion_plan.samples, time_step_s )
    samples = [
        TimedCoordinateSample(
            time_s=sample.time_s,
            position=_coordinate_from_geodetic( local_to_geodetic( sample.trajectory_local, local_origin ) ),
        )
        for sample in resampled
    ]
    if total_duration_s is not None and total_duration_s > 0.0:
        samples = _scale_timed_samples( samples, total_duration_s )
    return samples


def sample_timed_coordinates( samples: list[ TimedCoordinateSample ], time_s: float, *, loop: bool ) -> Coordinate:
    if not samples:
        return Coordinate( lon=0.0, lat=0.0, alt_m=0.0 )
    if len( samples ) == 1:
        return samples[ 0 ].position

    total_duration_s = samples[ -1 ].time_s
    if total_duration_s <= _EPSILON:
        return samples[ -1 ].position
    effective_time_s = time_s % total_duration_s if loop else min( max( time_s, 0.0 ), total_duration_s )
    return _sample_coordinate_at_time( samples, effective_time_s )


def build_multirotor_motion_plan( control_points: list[ ControlPoint ], *, speed_mps: float ) -> MotionPlan:
    resolved_speed_mps = max( speed_mps, _EPSILON )
    spans, diagnostics = build_multirotor_smoothed_spans(
        control_points,
        entity=MULTIROTOR_MED_PROFILE,
        resolved_speed_mps=resolved_speed_mps,
    )
    max_horizontal_accel_mps2 = max( float( MULTIROTOR_MED_PROFILE[ "familyProfile" ][ "maxHorizontalAccelMps2" ] ), _EPSILON )
    constrained_spans = [
        MotionSpan(
            kind=span.kind,
            segment_index=span.segment_index,
            start_local=span.start_local,
            end_local=span.end_local,
            length_m=span.length_m,
            dwell_time_s=span.dwell_time_s,
            center_local=span.center_local,
            radius_m=span.radius_m,
            start_angle_rad=span.start_angle_rad,
            end_angle_rad=span.end_angle_rad,
            sweep_angle_rad=span.sweep_angle_rad,
            turn_direction=span.turn_direction,
            speed_limit_mps=constrained_speed_limit_for_span(
                MULTIROTOR_MED_PROFILE,
                span,
                default_speed_mps=resolved_speed_mps if span.kind != "turn" else min(
                    resolved_speed_mps,
                    (
                        max_horizontal_accel_mps2
                        * max(
                            span.radius_m or float( MULTIROTOR_MED_PROFILE[ "motionProfile" ][ "turn" ][ "minTurnRadiusM" ] ),
                            _EPSILON,
                        )
                    ) ** 0.5,
                ),
            ),
        )
        for span in spans
    ]
    samples = integrate_path_spans( constrained_spans, MULTIROTOR_MED_PROFILE, resolved_speed_mps )
    return MotionPlan(
        family="multirotor",
        fidelity_variant="medFidelity",
        path_model="multirotor-sequence-spline",
        samples=samples,
        resolved_speed_mps=resolved_speed_mps,
        diagnostics=diagnostics,
    )


def _build_control_points( waypoints: list[ Coordinate ], local_origin: GeodeticPoint ) -> list[ ControlPoint ]:
    control_points: list[ ControlPoint ] = []
    for index, point in enumerate( waypoints ):
        geodetic = GeodeticPoint( lat=point.lat, lon=point.lon, h=point.alt_m )
        is_last = index == len( waypoints ) - 1
        control_points.append(
            ControlPoint(
                waypoint_id=f"wp-{index + 1}",
                geodetic=geodetic,
                trajectory_local=geodetic_to_local( geodetic, local_origin ),
                action="stop" if is_last else "flyThrough",
                loiter_time_s=0.0,
                speed_intent="nominal",
                target_speed_mps=None,
            )
        )
    return control_points


def _coordinate_from_geodetic( point: GeodeticPoint ) -> Coordinate:
    return Coordinate( lon=point.lon, lat=point.lat, alt_m=point.h )


def _scale_timed_samples( samples: list[ TimedCoordinateSample ], total_duration_s: float ) -> list[ TimedCoordinateSample ]:
    if not samples:
        return samples
    source_duration_s = samples[ -1 ].time_s
    if source_duration_s <= _EPSILON:
        return [ TimedCoordinateSample( time_s=0.0 if index == 0 else total_duration_s, position=sample.position ) for index, sample in enumerate( samples ) ]
    scale = total_duration_s / source_duration_s
    return [ TimedCoordinateSample( time_s=sample.time_s * scale, position=sample.position ) for sample in samples ]


def _sample_coordinate_at_time( samples: list[ TimedCoordinateSample ], target_time_s: float ) -> Coordinate:
    if target_time_s <= samples[ 0 ].time_s + _EPSILON:
        return samples[ 0 ].position
    for index in range( len( samples ) - 1 ):
        start_sample = samples[ index ]
        end_sample = samples[ index + 1 ]
        if target_time_s <= end_sample.time_s + _EPSILON:
            delta_t = max( end_sample.time_s - start_sample.time_s, _EPSILON )
            ratio = min( 1.0, max( 0.0, ( target_time_s - start_sample.time_s ) / delta_t ) )
            return Coordinate(
                lon=start_sample.position.lon + ( end_sample.position.lon - start_sample.position.lon ) * ratio,
                lat=start_sample.position.lat + ( end_sample.position.lat - start_sample.position.lat ) * ratio,
                alt_m=start_sample.position.alt_m + ( end_sample.position.alt_m - start_sample.position.alt_m ) * ratio,
            )
    return samples[ -1 ].position


def build_multirotor_smoothed_spans(
    control_points: list[ ControlPoint ],
    *,
    entity: dict,
    resolved_speed_mps: float,
) -> tuple[ list[ MotionSpan ], dict[ str, float | int ] ]:
    if len( control_points ) <= 1:
        return append_dwell_spans( [], control_points ), { "chainCount": 0, "splineSampleSpacingM": 0.0 }
    sample_spacing_m = _spline_sample_spacing_m( entity )
    max_speed_mps = float( entity[ "motionProfile" ][ "speed" ][ "maxMps" ] )
    max_horizontal_accel_mps2 = max( float( entity[ "familyProfile" ][ "maxHorizontalAccelMps2" ] ), _EPSILON )
    max_yaw_rate_rad_s = radians( float( entity[ "familyProfile" ][ "maxYawRateDegPerS" ] ) )
    move_spans: list[ MotionSpan ] = []
    chain_count = 0
    for chain_start_index, chain_end_index in _movement_chain_ranges( control_points ):
        if chain_end_index <= chain_start_index:
            continue
        chain_count += 1
        move_spans.extend(
            _build_chain_spans(
                control_points[ chain_start_index:chain_end_index + 1 ],
                start_segment_index=chain_start_index,
                sample_spacing_m=sample_spacing_m,
                resolved_speed_mps=resolved_speed_mps,
                max_speed_mps=max_speed_mps,
                max_horizontal_accel_mps2=max_horizontal_accel_mps2,
                max_yaw_rate_rad_s=max_yaw_rate_rad_s,
            )
        )
    return append_dwell_spans( move_spans, control_points ), {
        "chainCount": chain_count,
        "splineSampleSpacingM": round( sample_spacing_m, 3 ),
    }


def append_dwell_spans( spans: list[ MotionSpan ], control_points: list[ ControlPoint ] ) -> list[ MotionSpan ]:
    dwell_spans: list[ MotionSpan ] = []
    for index, control_point in enumerate( control_points ):
        if control_point.action == "stop":
            dwell_spans.append(
                MotionSpan(
                    kind="dwell",
                    segment_index=index,
                    start_local=control_point.trajectory_local,
                    end_local=control_point.trajectory_local,
                    length_m=0.0,
                    dwell_time_s=0.0,
                )
            )
    if not dwell_spans:
        return spans
    merged_spans = list( spans )
    for dwell_span in dwell_spans:
        merged_spans.append( dwell_span )
    return merged_spans


def constrained_speed_limit_for_span( entity: dict, span: MotionSpan, *, default_speed_mps: float ) -> float:
    return min(
        span.speed_limit_mps if span.speed_limit_mps is not None else default_speed_mps,
        vertical_rate_speed_limit_for_span( entity, span ),
    )


def vertical_rate_speed_limit_for_span( entity: dict, span: MotionSpan ) -> float:
    if span.length_m <= _EPSILON:
        return float( entity[ "motionProfile" ][ "speed" ][ "maxMps" ] )
    vertical_delta_m = span.end_local.z - span.start_local.z
    if abs( vertical_delta_m ) <= _EPSILON:
        return float( entity[ "motionProfile" ][ "speed" ][ "maxMps" ] )
    climb_profile = entity[ "motionProfile" ][ "climb" ]
    max_vertical_rate_mps = float( climb_profile[ "maxClimbMps" ] ) if vertical_delta_m >= 0.0 else float( climb_profile[ "maxDescentMps" ] )
    vertical_fraction = abs( vertical_delta_m ) / span.length_m
    return max_vertical_rate_mps / vertical_fraction if vertical_fraction > _EPSILON else float( entity[ "motionProfile" ][ "speed" ][ "maxMps" ] )


def integrate_path_spans( spans: list[ MotionSpan ], entity: dict, resolved_speed_mps: float ) -> list[ IntegratedMotionSample ]:
    traced_spans = trace_spans( spans )
    max_decel_mps2 = float( entity[ "motionProfile" ][ "acceleration" ][ "maxDecelMps2" ] )
    end_speed_limits_mps = build_span_end_speed_limits(
        traced_spans,
        resolved_speed_mps=resolved_speed_mps,
        max_decel_mps2=max_decel_mps2,
    )
    first_span = traced_spans[ 0 ].span
    max_speed_mps = float( entity[ "motionProfile" ][ "speed" ][ "maxMps" ] )
    current_distance_m = 0.0
    current_time_s = 0.0
    current_speed_mps = min( resolved_speed_mps, first_span.speed_limit_mps or resolved_speed_mps, max_speed_mps )
    previous_local = first_span.start_local
    samples = [
        IntegratedMotionSample(
            time_s=0.0,
            trajectory_local=previous_local,
            velocity_local=LocalPoint( x=0.0, y=0.0, z=0.0 ),
            segment_index=first_span.segment_index,
        )
    ]
    for span_index, traced_span in enumerate( traced_spans ):
        span = traced_span.span
        if span.kind == "dwell":
            continue
        while current_distance_m < traced_span.end_distance_m - _EPSILON:
            target_speed_mps = target_speed_limit_for_traced_span(
                traced_span,
                current_distance_m=current_distance_m,
                desired_speed_mps=min( resolved_speed_mps, span.speed_limit_mps or resolved_speed_mps ),
                required_speed_at_span_end_mps=end_speed_limits_mps[ span_index ],
                max_decel_mps2=max_decel_mps2,
            )
            target_speed_mps = min( max( target_speed_mps, 0.0 ), max_speed_mps )
            proposed_speed_mps = step_speed_toward_target( current_speed_mps, target_speed_mps, entity, _PATH_INTEGRATION_STEP_S )
            average_speed_mps = max( 0.0, 0.5 * ( current_speed_mps + proposed_speed_mps ) )
            if average_speed_mps <= _EPSILON:
                average_speed_mps = max( target_speed_mps, _EPSILON )
            distance_step_m = average_speed_mps * _PATH_INTEGRATION_STEP_S
            remaining_distance_m = traced_span.end_distance_m - current_distance_m
            if distance_step_m > remaining_distance_m:
                distance_step_m = remaining_distance_m
                time_step_s = distance_step_m / max( average_speed_mps, _EPSILON )
                proposed_speed_mps = step_speed_toward_target( current_speed_mps, target_speed_mps, entity, time_step_s )
            else:
                time_step_s = _PATH_INTEGRATION_STEP_S
            next_distance_m = current_distance_m + distance_step_m
            next_local = path_local_at_distance( traced_span, next_distance_m )
            velocity_local = LocalPoint(
                x=( next_local.x - previous_local.x ) / max( time_step_s, _EPSILON ),
                y=( next_local.y - previous_local.y ) / max( time_step_s, _EPSILON ),
                z=( next_local.z - previous_local.z ) / max( time_step_s, _EPSILON ),
            )
            current_time_s += time_step_s
            samples.append(
                IntegratedMotionSample(
                    time_s=current_time_s,
                    trajectory_local=next_local,
                    velocity_local=velocity_local,
                    segment_index=span.segment_index,
                )
            )
            previous_local = next_local
            current_distance_m = next_distance_m
            current_speed_mps = min( max( proposed_speed_mps, 0.0 ), max_speed_mps )
    return dedupe_motion_samples( samples )


@dataclass( frozen=True )
class TracedSpan:
    span: MotionSpan
    start_distance_m: float
    end_distance_m: float


def trace_spans( spans: list[ MotionSpan ] ) -> list[ TracedSpan ]:
    traced_spans: list[ TracedSpan ] = []
    cumulative_distance_m = 0.0
    for span in spans:
        traced_spans.append(
            TracedSpan(
                span=span,
                start_distance_m=cumulative_distance_m,
                end_distance_m=cumulative_distance_m + span.length_m,
            )
        )
        cumulative_distance_m += span.length_m
    return traced_spans


def path_local_at_distance( traced_span: TracedSpan, distance_m: float ) -> LocalPoint:
    span = traced_span.span
    if span.length_m <= _EPSILON:
        return span.end_local
    ratio = min( 1.0, max( 0.0, ( distance_m - traced_span.start_distance_m ) / span.length_m ) )
    return span_local_at_ratio( span, ratio )


def span_local_at_ratio( span: MotionSpan, ratio: float ) -> LocalPoint:
    if (
        span.kind == "turn"
        and span.center_local is not None
        and span.radius_m is not None
        and span.start_angle_rad is not None
        and span.sweep_angle_rad is not None
        and span.turn_direction is not None
    ):
        angle_rad = span.start_angle_rad + span.turn_direction * span.sweep_angle_rad * ratio
        return LocalPoint(
            x=span.center_local.x + span.radius_m * cos( angle_rad ),
            y=span.center_local.y + span.radius_m * sin( angle_rad ),
            z=span.start_local.z + ( span.end_local.z - span.start_local.z ) * ratio,
        )
    return lerp_local( span.start_local, span.end_local, ratio )


def lerp_local( start: LocalPoint, end: LocalPoint, ratio: float ) -> LocalPoint:
    return LocalPoint(
        x=start.x + ( end.x - start.x ) * ratio,
        y=start.y + ( end.y - start.y ) * ratio,
        z=start.z + ( end.z - start.z ) * ratio,
    )


def distance_between( start: LocalPoint, end: LocalPoint ) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    dz = end.z - start.z
    return sqrt( dx * dx + dy * dy + dz * dz )


def build_span_end_speed_limits(
    traced_spans: list[ TracedSpan ],
    *,
    resolved_speed_mps: float,
    max_decel_mps2: float,
) -> list[ float ]:
    if not traced_spans:
        return []
    end_speed_limits_mps = [ 0.0 for _ in traced_spans ]
    required_speed_at_span_end_mps = 0.0
    for span_index in range( len( traced_spans ) - 1, -1, -1 ):
        traced_span = traced_spans[ span_index ]
        desired_speed_mps = traced_span.span.speed_limit_mps or resolved_speed_mps
        if span_index == len( traced_spans ) - 1 and traced_span.span.kind != "dwell":
            required_speed_at_span_end_mps = desired_speed_mps
        end_speed_limits_mps[ span_index ] = required_speed_at_span_end_mps
        if traced_span.span.kind == "dwell":
            required_speed_at_span_end_mps = 0.0
            continue
        required_speed_at_span_end_mps = min(
            desired_speed_mps,
            ( required_speed_at_span_end_mps ** 2 + 2.0 * max( max_decel_mps2, _EPSILON ) * traced_span.span.length_m ) ** 0.5,
        )
    return end_speed_limits_mps


def target_speed_limit_for_traced_span(
    traced_span: TracedSpan,
    *,
    current_distance_m: float,
    desired_speed_mps: float,
    required_speed_at_span_end_mps: float,
    max_decel_mps2: float,
) -> float:
    if traced_span.span.kind == "dwell":
        return 0.0
    remaining_distance_m = max( 0.0, traced_span.end_distance_m - current_distance_m )
    return min(
        desired_speed_mps,
        ( required_speed_at_span_end_mps ** 2 + 2.0 * max( max_decel_mps2, _EPSILON ) * remaining_distance_m ) ** 0.5,
    )


def step_speed_toward_target( current_speed_mps: float, target_speed_mps: float, entity: dict, dt_s: float ) -> float:
    acceleration = entity[ "motionProfile" ][ "acceleration" ]
    max_speed_mps = float( entity[ "motionProfile" ][ "speed" ][ "maxMps" ] )
    target_speed_mps = min( max( target_speed_mps, 0.0 ), max_speed_mps )
    current_speed_mps = min( max( current_speed_mps, 0.0 ), max_speed_mps )
    response_time_constant_s = max( float( acceleration[ "responseTimeConstantS" ] ), dt_s, _EPSILON )
    alpha = 1.0 - exp( -dt_s / response_time_constant_s )
    lagged_target_speed_mps = current_speed_mps + ( target_speed_mps - current_speed_mps ) * alpha
    if lagged_target_speed_mps >= current_speed_mps:
        max_delta_speed_mps = float( acceleration[ "maxAccelMps2" ] ) * dt_s
        return min( current_speed_mps + max_delta_speed_mps, lagged_target_speed_mps, max_speed_mps )
    max_delta_speed_mps = float( acceleration[ "maxDecelMps2" ] ) * dt_s
    return max( 0.0, current_speed_mps - max_delta_speed_mps, target_speed_mps )


def dedupe_motion_samples( samples: list[ IntegratedMotionSample ] ) -> list[ IntegratedMotionSample ]:
    deduped: list[ IntegratedMotionSample ] = []
    for sample in samples:
        if deduped and abs( deduped[ -1 ].time_s - sample.time_s ) <= _EPSILON and distance_between( deduped[ -1 ].trajectory_local, sample.trajectory_local ) <= _EPSILON:
            deduped[ -1 ] = sample
            continue
        deduped.append( sample )
    return deduped


def resample_motion_plan_by_time( samples: list[ IntegratedMotionSample ], step_s: float ) -> list[ IntegratedMotionSample ]:
    if len( samples ) <= 1:
        return samples
    total_duration_s = samples[ -1 ].time_s
    target_times_s = [ 0.0 ]
    next_time_s = step_s
    while next_time_s < total_duration_s - _EPSILON:
        target_times_s.append( next_time_s )
        next_time_s += step_s
    if abs( target_times_s[ -1 ] - total_duration_s ) > _EPSILON:
        target_times_s.append( total_duration_s )
    return [ _sample_motion_at_time( samples, target_time_s ) for target_time_s in target_times_s ]


def _sample_motion_at_time( samples: list[ IntegratedMotionSample ], target_time_s: float ) -> IntegratedMotionSample:
    if target_time_s <= samples[ 0 ].time_s + _EPSILON:
        return samples[ 0 ]
    for index in range( len( samples ) - 1 ):
        start_sample = samples[ index ]
        end_sample = samples[ index + 1 ]
        if target_time_s <= end_sample.time_s + _EPSILON:
            delta_t = max( end_sample.time_s - start_sample.time_s, _EPSILON )
            ratio = min( 1.0, max( 0.0, ( target_time_s - start_sample.time_s ) / delta_t ) )
            return IntegratedMotionSample(
                time_s=target_time_s,
                trajectory_local=lerp_local( start_sample.trajectory_local, end_sample.trajectory_local, ratio ),
                velocity_local=lerp_local( start_sample.velocity_local, end_sample.velocity_local, ratio ),
                segment_index=end_sample.segment_index if ratio >= 0.5 else start_sample.segment_index,
            )
    return samples[ -1 ]


def _movement_chain_ranges( control_points: list[ ControlPoint ] ) -> list[ tuple[ int, int ] ]:
    ranges: list[ tuple[ int, int ] ] = []
    chain_start_index = 0
    for index in range( 1, len( control_points ) ):
        if control_points[ index ].action in { "stop", "loiter" }:
            ranges.append( ( chain_start_index, index ) )
            chain_start_index = index
    if chain_start_index < len( control_points ) - 1:
        ranges.append( ( chain_start_index, len( control_points ) - 1 ) )
    return ranges


def _build_chain_spans(
    control_points: list[ ControlPoint ],
    *,
    start_segment_index: int,
    sample_spacing_m: float,
    resolved_speed_mps: float,
    max_speed_mps: float,
    max_horizontal_accel_mps2: float,
    max_yaw_rate_rad_s: float,
) -> list[ MotionSpan ]:
    if len( control_points ) < 2:
        return []
    vertices = _build_chain_vertices(
        control_points,
        start_segment_index=start_segment_index,
        sample_spacing_m=sample_spacing_m,
        resolved_speed_mps=resolved_speed_mps,
    )
    if len( vertices ) < 2:
        return []
    curvatures_m_inv = _horizontal_curvatures( vertices )
    spans: list[ MotionSpan ] = []
    for index, ( start_vertex, end_vertex ) in enumerate( zip( vertices[ :-1 ], vertices[ 1: ], strict=True ) ):
        length_m = distance_between( start_vertex.local, end_vertex.local )
        if length_m <= _EPSILON:
            continue
        curvature_m_inv = max( curvatures_m_inv[ index ], curvatures_m_inv[ index + 1 ] )
        curvature_speed_limit_mps = max_speed_mps
        yaw_rate_speed_limit_mps = max_speed_mps
        if curvature_m_inv > _EPSILON:
            curvature_speed_limit_mps = sqrt( max_horizontal_accel_mps2 / curvature_m_inv )
            yaw_rate_speed_limit_mps = max_yaw_rate_rad_s / curvature_m_inv
        spans.append(
            MotionSpan(
                kind="move",
                segment_index=end_vertex.segment_index,
                start_local=start_vertex.local,
                end_local=end_vertex.local,
                length_m=length_m,
                speed_limit_mps=min(
                    end_vertex.segment_speed_limit_mps,
                    curvature_speed_limit_mps,
                    yaw_rate_speed_limit_mps,
                    max_speed_mps,
                ),
            )
        )
    return spans


@dataclass( frozen=True )
class SmoothedPathVertex:
    local: LocalPoint
    segment_index: int
    segment_speed_limit_mps: float


def _build_chain_vertices(
    control_points: list[ ControlPoint ],
    *,
    start_segment_index: int,
    sample_spacing_m: float,
    resolved_speed_mps: float,
) -> list[ SmoothedPathVertex ]:
    if len( control_points ) == 2:
        return _build_linear_chain_vertices(
            control_points,
            start_segment_index=start_segment_index,
            sample_spacing_m=sample_spacing_m,
            resolved_speed_mps=resolved_speed_mps,
        )
    vertices: list[ SmoothedPathVertex ] = []
    for local_segment_index in range( len( control_points ) - 1 ):
        start_control_point = control_points[ local_segment_index ]
        end_control_point = control_points[ local_segment_index + 1 ]
        segment_index = start_segment_index + local_segment_index
        segment_speed_limit_mps = float( end_control_point.target_speed_mps or resolved_speed_mps )
        segment_points = _sample_catmull_rom_segment(
            _chain_support_point( control_points, local_segment_index - 1, extrapolate_from=0, toward=1 ),
            start_control_point.trajectory_local,
            end_control_point.trajectory_local,
            _chain_support_point( control_points, local_segment_index + 2, extrapolate_from=-1, toward=-2 ),
            sample_count=_segment_sample_count(
                start_control_point.trajectory_local,
                end_control_point.trajectory_local,
                sample_spacing_m,
            ),
        )
        if local_segment_index == 0:
            vertices.append(
                SmoothedPathVertex(
                    local=segment_points[ 0 ],
                    segment_index=segment_index,
                    segment_speed_limit_mps=segment_speed_limit_mps,
                )
            )
        for point in segment_points[ 1: ]:
            vertices.append(
                SmoothedPathVertex(
                    local=point,
                    segment_index=segment_index,
                    segment_speed_limit_mps=segment_speed_limit_mps,
                )
            )
    return vertices


def _build_linear_chain_vertices(
    control_points: list[ ControlPoint ],
    *,
    start_segment_index: int,
    sample_spacing_m: float,
    resolved_speed_mps: float,
) -> list[ SmoothedPathVertex ]:
    start_control_point = control_points[ 0 ]
    end_control_point = control_points[ 1 ]
    segment_speed_limit_mps = float( end_control_point.target_speed_mps or resolved_speed_mps )
    segment_index = start_segment_index
    sample_count = _segment_sample_count( start_control_point.trajectory_local, end_control_point.trajectory_local, sample_spacing_m )
    vertices = [
        SmoothedPathVertex(
            local=start_control_point.trajectory_local,
            segment_index=segment_index,
            segment_speed_limit_mps=segment_speed_limit_mps,
        )
    ]
    for sample_index in range( 1, sample_count + 1 ):
        ratio = sample_index / sample_count
        vertices.append(
            SmoothedPathVertex(
                local=lerp_local( start_control_point.trajectory_local, end_control_point.trajectory_local, ratio ),
                segment_index=segment_index,
                segment_speed_limit_mps=segment_speed_limit_mps,
            )
        )
    return vertices


def _segment_sample_count( start_local: LocalPoint, end_local: LocalPoint, sample_spacing_m: float ) -> int:
    return max( 2, int( ceil( distance_between( start_local, end_local ) / max( sample_spacing_m, _EPSILON ) ) ) )


def _chain_support_point(
    control_points: list[ ControlPoint ],
    index: int,
    *,
    extrapolate_from: int,
    toward: int,
) -> LocalPoint:
    if 0 <= index < len( control_points ):
        return control_points[ index ].trajectory_local
    base = control_points[ extrapolate_from ].trajectory_local
    neighbor = control_points[ toward ].trajectory_local
    return LocalPoint(
        x=base.x + ( base.x - neighbor.x ),
        y=base.y + ( base.y - neighbor.y ),
        z=base.z + ( base.z - neighbor.z ),
    )


def _sample_catmull_rom_segment( p0: LocalPoint, p1: LocalPoint, p2: LocalPoint, p3: LocalPoint, *, sample_count: int ) -> list[ LocalPoint ]:
    points = [ p1 ]
    for sample_index in range( 1, sample_count ):
        points.append( _catmull_rom_point( p0, p1, p2, p3, sample_index / sample_count ) )
    points.append( p2 )
    return points


def _catmull_rom_point( p0: LocalPoint, p1: LocalPoint, p2: LocalPoint, p3: LocalPoint, ratio: float ) -> LocalPoint:
    t0 = 0.0
    t1 = _next_knot_parameter( t0, p0, p1 )
    t2 = _next_knot_parameter( t1, p1, p2 )
    t3 = _next_knot_parameter( t2, p2, p3 )
    t = t1 + ( t2 - t1 ) * ratio
    a1 = _interpolate_point( p0, p1, t0, t1, t )
    a2 = _interpolate_point( p1, p2, t1, t2, t )
    a3 = _interpolate_point( p2, p3, t2, t3, t )
    b1 = _interpolate_point( a1, a2, t0, t2, t )
    b2 = _interpolate_point( a2, a3, t1, t3, t )
    return _interpolate_point( b1, b2, t1, t2, t )


def _next_knot_parameter( start_t: float, start: LocalPoint, end: LocalPoint ) -> float:
    return start_t + max( distance_between( start, end ), _EPSILON ) ** _CENTRIPETAL_ALPHA


def _interpolate_point( start: LocalPoint, end: LocalPoint, start_t: float, end_t: float, t: float ) -> LocalPoint:
    span_t = max( end_t - start_t, _EPSILON )
    ratio = ( t - start_t ) / span_t
    return LocalPoint(
        x=start.x + ( end.x - start.x ) * ratio,
        y=start.y + ( end.y - start.y ) * ratio,
        z=start.z + ( end.z - start.z ) * ratio,
    )


def _horizontal_curvatures( vertices: list[ SmoothedPathVertex ] ) -> list[ float ]:
    if len( vertices ) <= 2:
        return [ 0.0 for _ in vertices ]
    curvatures_m_inv = [ 0.0 for _ in vertices ]
    for index in range( 1, len( vertices ) - 1 ):
        curvatures_m_inv[ index ] = _horizontal_curvature_m_inv( vertices[ index - 1 ].local, vertices[ index ].local, vertices[ index + 1 ].local )
    curvatures_m_inv[ 0 ] = curvatures_m_inv[ 1 ]
    curvatures_m_inv[ -1 ] = curvatures_m_inv[ -2 ]
    return curvatures_m_inv


def _horizontal_curvature_m_inv( previous: LocalPoint, current: LocalPoint, following: LocalPoint ) -> float:
    a = _horizontal_distance_m( previous, current )
    b = _horizontal_distance_m( current, following )
    c = _horizontal_distance_m( previous, following )
    if a <= _EPSILON or b <= _EPSILON or c <= _EPSILON:
        return 0.0
    twice_area = abs( ( current.x - previous.x ) * ( following.y - previous.y ) - ( current.y - previous.y ) * ( following.x - previous.x ) )
    if twice_area <= _EPSILON:
        return 0.0
    return 2.0 * twice_area / max( a * b * c, _EPSILON )


def _horizontal_distance_m( start: LocalPoint, end: LocalPoint ) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    return sqrt( dx * dx + dy * dy )


def _spline_sample_spacing_m( entity: dict ) -> float:
    nominal_speed_mps = float( entity[ "motionProfile" ][ "speed" ][ "nominalMps" ] )
    response_time_constant_s = float( entity[ "motionProfile" ][ "acceleration" ][ "responseTimeConstantS" ] )
    min_turn_radius_m = float( entity[ "motionProfile" ][ "turn" ][ "minTurnRadiusM" ] )
    return max( 1.5, min( nominal_speed_mps * response_time_constant_s * 0.35, min_turn_radius_m * 0.45 ) )
