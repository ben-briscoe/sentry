import { Cartesian3 } from 'cesium';

import type { Coordinate, RenderStructure } from '../types';


export const DEFAULT_COORDINATE: Coordinate = { lon: 0, lat: 0, alt_m: 0 };


export function toCartesian( point: Coordinate ): Cartesian3 {
  return Cartesian3.fromDegrees( point.lon, point.lat, point.alt_m );
}


export function cloneCoordinate( point: Coordinate ): Coordinate {
  return { lon: point.lon, lat: point.lat, alt_m: point.alt_m };
}


export function lerpCoordinate( start: Coordinate, end: Coordinate, alpha: number ): Coordinate {
  const clamped = Math.min( Math.max( alpha, 0 ), 1 );
  return {
    lon: start.lon + ( end.lon - start.lon ) * clamped,
    lat: start.lat + ( end.lat - start.lat ) * clamped,
    alt_m: start.alt_m + ( end.alt_m - start.alt_m ) * clamped,
  };
}


export function interpolateNullableCoordinate(
  start: Coordinate | null,
  end: Coordinate | null,
  alpha: number,
): Coordinate | null {
  if ( start !== null && end !== null ) {
    return lerpCoordinate( start, end, alpha );
  }
  return alpha < 0.5 ? start : end;
}


export function interpolateNullableNumber(
  start: number | null | undefined,
  end: number | null | undefined,
  alpha: number,
): number | null {
  if ( start !== null && start !== undefined && end !== null && end !== undefined ) {
    return start + ( end - start ) * Math.min( Math.max( alpha, 0 ), 1 );
  }
  return alpha < 0.5
    ? ( start ?? null )
    : ( end ?? null );
}


export function headingBetween( start: Coordinate, end: Coordinate, fallbackDeg: number ): number {
  const latScale = 111_132;
  const lonScale = 111_320 * Math.max( Math.cos( ( ( start.lat + end.lat ) / 2 ) * Math.PI / 180 ), 0.2 );
  const eastM = ( end.lon - start.lon ) * lonScale;
  const northM = ( end.lat - start.lat ) * latScale;
  if ( Math.hypot( eastM, northM ) < 0.15 ) {
    return fallbackDeg;
  }
  return Math.atan2( eastM, northM ) * 180 / Math.PI;
}


export function coordinateDistanceM( start: Coordinate, end: Coordinate ): number {
  const latScale = 111_132;
  const lonScale = 111_320 * Math.max( Math.cos( ( ( start.lat + end.lat ) / 2 ) * Math.PI / 180 ), 0.2 );
  const eastM = ( end.lon - start.lon ) * lonScale;
  const northM = ( end.lat - start.lat ) * latScale;
  const upM = end.alt_m - start.alt_m;
  return Math.hypot( eastM, northM, upM );
}


export function offsetCoordinate( origin: Coordinate, forwardM: number, rightM: number, upM: number, headingDeg: number ): Coordinate {
  const headingRad = headingDeg * Math.PI / 180;
  const eastM = forwardM * Math.sin( headingRad ) + rightM * Math.cos( headingRad );
  const northM = forwardM * Math.cos( headingRad ) - rightM * Math.sin( headingRad );
  const metersPerDegreeLat = 111_320;
  const lonScale = metersPerDegreeLat * Math.max( Math.cos( origin.lat * Math.PI / 180 ), 0.2 );
  return {
    lon: origin.lon + eastM / lonScale,
    lat: origin.lat + northM / metersPerDegreeLat,
    alt_m: origin.alt_m + upM,
  };
}


export function midpointCoordinate( start: Coordinate, end: Coordinate ): Coordinate {
  return lerpCoordinate( start, end, 0.5 );
}


export function flattenCoordinateToAltitude( point: Coordinate, altitudeM: number ): Coordinate {
  return {
    lon: point.lon,
    lat: point.lat,
    alt_m: altitudeM,
  };
}


export function sceneBounds( coordinates: Coordinate[] ): { east: number; north: number; south: number; west: number } {
  const lons = coordinates.map( ( point ) => point.lon );
  const lats = coordinates.map( ( point ) => point.lat );
  return {
    west: Math.min( ...lons ),
    east: Math.max( ...lons ),
    south: Math.min( ...lats ),
    north: Math.max( ...lats ),
  };
}


export function sceneCenter( bounds: { east: number; north: number; south: number; west: number } ): Coordinate {
  return {
    lon: ( bounds.west + bounds.east ) / 2,
    lat: ( bounds.south + bounds.north ) / 2,
    alt_m: 0,
  };
}


export function structureCenter( structure: RenderStructure ): Coordinate {
  return {
    ...structure.center,
    alt_m: structure.center.alt_m + ( structure.dimensions_m.height_m / 2 ),
  };
}


export function isFiniteCoordinate( point: Coordinate ): boolean {
  return Number.isFinite( point.lon ) && Number.isFinite( point.lat ) && Number.isFinite( point.alt_m );
}
