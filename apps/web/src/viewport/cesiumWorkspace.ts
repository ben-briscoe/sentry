import {
  CallbackPositionProperty,
  CallbackProperty,
  Cartesian2,
  Cartesian3,
  Color,
  ColorMaterialProperty,
  EllipsoidTerrainProvider,
  HeadingPitchRoll,
  LabelStyle,
  Math as CesiumMath,
  OpenStreetMapImageryProvider,
  Quaternion,
  Rectangle,
  Transforms,
  Viewer,
  VerticalOrigin,
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';

import { PlaybackBuffer, type WorkspacePlaybackSnapshot } from './playbackBuffer';
import {
  resolveCylinderQuaternionBetweenPoints,
  resolveVelocityAlignedQuaternion,
} from './playbackOrientation';
import {
  cloneCoordinate,
  DEFAULT_COORDINATE,
  flattenCoordinateToAltitude,
  midpointCoordinate,
  offsetCoordinate,
  sceneBounds,
  sceneCenter,
  structureCenter,
  toCartesian,
} from './sceneMath';
import type {
  Coordinate,
  MissionState,
  ReferenceMetrics,
  RenderScene,
  RenderState,
  RenderStructure,
} from '../types';


export type { WorkspacePlaybackSnapshot } from './playbackBuffer';


type WorkspaceHandle = {
  currentPlaybackSnapshot: () => WorkspacePlaybackSnapshot | null;
  destroy: () => void;
  render: ( scene: RenderScene | null, state: MissionState | null, reference: ReferenceMetrics, renderState?: RenderState | null ) => void;
};


function sceneCoordinates( scene: RenderScene ): Coordinate[] {
  return [
    scene.base,
    ...scene.patrol_area,
    ...scene.patrol_route,
    ...scene.incursion_route,
    ...scene.structures.map( ( structure ) => structure.center ),
  ];
}


function structureOrientation( structure: RenderStructure ): CallbackProperty {
  return new CallbackProperty( () => {
    const center = toCartesian( {
      ...structure.center,
      alt_m: structure.center.alt_m + ( structure.dimensions_m.height_m / 2 ),
    } );
    return Transforms.headingPitchRollQuaternion(
      center,
      HeadingPitchRoll.fromDegrees( structure.heading_deg, 0, 0 ),
    );
  }, false );
}

export function createCesiumWorkspace( container: HTMLElement ): WorkspaceHandle {
  const viewer = new Viewer( container, {
    animation: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    infoBox: false,
    navigationHelpButton: false,
    sceneModePicker: false,
    selectionIndicator: false,
    terrainProvider: new EllipsoidTerrainProvider(),
    timeline: false,
  } );
  viewer.imageryLayers.removeAll();
  viewer.imageryLayers.addImageryProvider( new OpenStreetMapImageryProvider( {
    url: 'https://tile.openstreetmap.org/',
  } ) );

  const playbackBuffer = new PlaybackBuffer();
  let sceneKey: string | null = null;
  let lastVehicleOrientation: Quaternion | null = null;

  function clearPlaybackState(): void {
    playbackBuffer.reset();
    lastVehicleOrientation = null;
  }

  function currentVehiclePosition(): Coordinate {
    return playbackBuffer.vehiclePosition( performance.now() );
  }

  function currentIncursionPosition(): Coordinate {
    return playbackBuffer.incursionPosition( performance.now() );
  }

  function currentMotionNeighbors( nowMs: number ): {
    current: Coordinate;
    next: Coordinate | null;
    previous: Coordinate | null;
  } {
    return playbackBuffer.motionNeighbors( nowMs );
  }

  function currentPlaybackSnapshot( nowMs: number ): WorkspacePlaybackSnapshot | null {
    return playbackBuffer.snapshot( nowMs );
  }

  function vehicleOrientation(): CallbackProperty {
    return new CallbackProperty( () => {
      const nowMs = performance.now();
      const headingDeg = playbackBuffer.heading( nowMs );
      const { current, previous, next } = currentMotionNeighbors( nowMs );
      const position = toCartesian( current );
      const flattenedPrevious = previous ? flattenCoordinateToAltitude( previous, current.alt_m ) : null;
      const flattenedNext = next ? flattenCoordinateToAltitude( next, current.alt_m ) : null;
      const resolvedOrientation = resolveVelocityAlignedQuaternion(
        position,
        flattenedPrevious ? toCartesian( flattenedPrevious ) : null,
        flattenedNext ? toCartesian( flattenedNext ) : null,
        0.0,
      );
      if ( resolvedOrientation ) {
        lastVehicleOrientation = resolvedOrientation;
        return resolvedOrientation;
      }
      return lastVehicleOrientation ?? Transforms.headingPitchRollQuaternion(
        position,
        HeadingPitchRoll.fromDegrees( headingDeg, 0, 0 ),
      );
    }, false );
  }

  function rotorPositionProperty( forwardM: number, rightM: number, upM: number ): CallbackPositionProperty {
    return new CallbackPositionProperty( () => {
      const headingDeg = playbackBuffer.heading( performance.now() );
      const rotorCoordinate = offsetCoordinate( currentVehiclePosition(), forwardM, rightM, upM, headingDeg );
      return toCartesian( rotorCoordinate );
    }, false );
  }

  function armPositionsProperty( forwardM: number, rightM: number, upM: number ): CallbackProperty {
    return new CallbackProperty( () => {
      const base = currentVehiclePosition();
      const headingDeg = playbackBuffer.heading( performance.now() );
      const armBase = offsetCoordinate( base, forwardM * 0.45, rightM * 0.45, upM * 0.45, headingDeg );
      const rotor = offsetCoordinate( base, forwardM, rightM, upM, headingDeg );
      return [ toCartesian( armBase ), toCartesian( rotor ) ];
    }, false );
  }

  function ensureScene( scene: RenderScene ): void {
    if ( sceneKey === scene.id ) {
      return;
    }

    viewer.entities.removeAll();
    sceneKey = scene.id;
    clearPlaybackState();

    const bounds = sceneBounds( sceneCoordinates( scene ) );
    const center = sceneCenter( bounds );
    const latSpan = Math.max( bounds.north - bounds.south, 0.0012 );
    const lonSpan = Math.max( bounds.east - bounds.west, 0.0012 );
    const latPadding = Math.max( latSpan * 0.22, 0.00065 );
    const lonPadding = Math.max( lonSpan * 0.22, 0.00075 );

    viewer.entities.add( {
      id: 'reference-plane',
      rectangle: {
        coordinates: Rectangle.fromDegrees(
          bounds.west - lonPadding,
          bounds.south - latPadding,
          bounds.east + lonPadding,
          bounds.north + latPadding,
        ),
        fill: true,
        height: 0,
        material: Color.fromCssColorString( '#31463c' ).withAlpha( 0.16 ),
        outline: true,
        outlineColor: Color.fromCssColorString( '#77886f' ).withAlpha( 0.42 ),
      },
    } );

    viewer.entities.add( {
      position: toCartesian( scene.base ),
      point: {
        color: Color.fromCssColorString( '#f4c95d' ),
        pixelSize: 15,
        outlineColor: Color.fromCssColorString( '#2b1e11' ),
        outlineWidth: 2,
      },
      label: {
        text: 'Support Base',
        fillColor: Color.WHITE,
        font: '700 14px "Trebuchet MS"',
        pixelOffset: new Cartesian2( 0, -22 ),
        showBackground: true,
        style: LabelStyle.FILL,
        verticalOrigin: VerticalOrigin.BOTTOM,
      },
    } );

    viewer.entities.add( {
      polyline: {
        positions: scene.patrol_route.map( ( point ) => toCartesian( { ...point, alt_m: 3 } ) ),
        width: 6,
        material: Color.fromCssColorString( '#ffb15a' ).withAlpha( 0.96 ),
      },
    } );

    scene.structures.forEach( ( structure ) => {
      const boxColor = structure.kind === 'barrier'
        ? Color.fromCssColorString( structure.color ?? '#b88a57' )
        : structure.kind === 'tower'
          ? Color.fromCssColorString( structure.color ?? '#cad4e0' )
          : Color.fromCssColorString( structure.color ?? '#7f8fa6' );
      viewer.entities.add( {
        id: structure.id,
        position: toCartesian( structureCenter( structure ) ),
        orientation: structureOrientation( structure ),
        box: {
          dimensions: new Cartesian3(
            structure.dimensions_m.length_m,
            structure.dimensions_m.width_m,
            structure.dimensions_m.height_m,
          ),
          material: boxColor.withAlpha( 0.84 ),
          outline: true,
          outlineColor: Color.fromCssColorString( '#eef3fb' ).withAlpha( 0.76 ),
        },
      } );
    } );

    const orientationProperty = vehicleOrientation();
    viewer.entities.add( {
      id: 'sentry-body',
      position: new CallbackPositionProperty( () => toCartesian( currentVehiclePosition() ), false ),
      orientation: orientationProperty,
      box: {
        dimensions: new Cartesian3( 16, 7, 3.2 ),
        material: Color.fromCssColorString( '#a9c7dd' ).withAlpha( 0.96 ),
        outline: true,
        outlineColor: Color.fromCssColorString( '#eef4fb' ).withAlpha( 0.9 ),
      },
    } );

    viewer.entities.add( {
      id: 'sentry-beacon',
      position: new CallbackPositionProperty( () => toCartesian( currentVehiclePosition() ), false ),
      point: {
        color: Color.fromCssColorString( '#ffb55f' ).withAlpha( 0.96 ),
        pixelSize: 12,
        outlineColor: Color.fromCssColorString( '#26150a' ).withAlpha( 0.94 ),
        outlineWidth: 3,
      },
    } );

    [
      [ 9, 9, 2.4 ],
      [ 9, -9, 2.4 ],
      [ -9, 9, 2.4 ],
      [ -9, -9, 2.4 ],
    ].forEach( ( [ forwardM, rightM, upM ], index ) => {
      viewer.entities.add( {
        id: `sentry-arm-${index + 1}`,
        polyline: {
          positions: armPositionsProperty( forwardM, rightM, upM ),
          width: 3,
          material: Color.fromCssColorString( '#dfe8f5' ).withAlpha( 0.96 ),
        },
      } );
      viewer.entities.add( {
        id: `sentry-rotor-${index + 1}`,
        position: rotorPositionProperty( forwardM, rightM, upM ),
        ellipsoid: {
          radii: new Cartesian3( 1.9, 1.9, 0.52 ),
          material: Color.fromCssColorString( '#f3f7fb' ).withAlpha( 0.9 ),
        },
      } );
    } );

    viewer.entities.add( {
      id: 'sentry-label',
      position: new CallbackPositionProperty( () => {
        const headingDeg = playbackBuffer.heading( performance.now() );
        const position = offsetCoordinate( currentVehiclePosition(), 0, 0, 7, headingDeg );
        return toCartesian( position );
      }, false ),
      label: {
        fillColor: Color.WHITE,
        font: '700 15px "Trebuchet MS"',
        pixelOffset: new Cartesian2( 0, -18 ),
        showBackground: true,
        style: LabelStyle.FILL,
        text: new CallbackProperty( () => playbackBuffer.frame( performance.now() )?.vehicle.label ?? 'SENTRY', false ),
        verticalOrigin: VerticalOrigin.BOTTOM,
      },
    } );

    viewer.entities.add( {
      id: 'sentry-spotlight',
      position: new CallbackPositionProperty( () => {
        const nowMs = performance.now();
        const frame = playbackBuffer.frame( nowMs );
        const vehiclePosition = cloneCoordinate( frame?.vehicle.position ?? DEFAULT_COORDINATE );
        const target = frame?.vehicle.spotlightOn === true && frame.incursion.active && frame.incursion.position !== null
          ? frame.incursion.position
          : { ...vehiclePosition, alt_m: 0 };
        return toCartesian( midpointCoordinate( vehiclePosition, target ) );
      }, false ),
      orientation: new CallbackProperty( () => {
        const nowMs = performance.now();
        const frame = playbackBuffer.frame( nowMs );
        const vehiclePosition = cloneCoordinate( frame?.vehicle.position ?? DEFAULT_COORDINATE );
        const target = frame?.vehicle.spotlightOn === true && frame.incursion.active && frame.incursion.position !== null
          ? frame.incursion.position
          : { ...vehiclePosition, alt_m: 0 };
        return resolveCylinderQuaternionBetweenPoints(
          toCartesian( midpointCoordinate( vehiclePosition, target ) ),
          toCartesian( target ),
          toCartesian( vehiclePosition ),
        ) ?? Transforms.headingPitchRollQuaternion(
          toCartesian( midpointCoordinate( vehiclePosition, target ) ),
          HeadingPitchRoll.fromDegrees( playbackBuffer.heading( nowMs ), -90, 0 ),
        );
      }, false ),
      cylinder: {
        length: new CallbackProperty( () => {
          const nowMs = performance.now();
          const frame = playbackBuffer.frame( nowMs );
          const vehiclePosition = cloneCoordinate( frame?.vehicle.position ?? DEFAULT_COORDINATE );
          const target = frame?.vehicle.spotlightOn === true && frame.incursion.active && frame.incursion.position !== null
            ? frame.incursion.position
            : { ...vehiclePosition, alt_m: 0 };
          return Math.max( Cartesian3.distance( toCartesian( vehiclePosition ), toCartesian( target ) ), 4 );
        }, false ),
        topRadius: 0.35,
        bottomRadius: new CallbackProperty( () => {
          const incursionRadiusM = playbackBuffer.frame( performance.now() )?.incursion.radiusM ?? 14;
          return Math.max( incursionRadiusM * 0.7, 7 );
        }, false ),
        material: new ColorMaterialProperty(
          new CallbackProperty( () => {
            const spotlightOn = playbackBuffer.frame( performance.now() )?.vehicle.spotlightOn ?? false;
            return Color.fromCssColorString( '#ffe08a' ).withAlpha( spotlightOn ? 0.22 : 0 );
          }, false ),
        ),
        outline: true,
        outlineColor: new CallbackProperty( () => {
          const spotlightOn = playbackBuffer.frame( performance.now() )?.vehicle.spotlightOn ?? false;
          return Color.fromCssColorString( '#ffe5ab' ).withAlpha( spotlightOn ? 0.42 : 0 );
        }, false ),
      },
    } );

    viewer.entities.add( {
      id: 'sentry-speaker-ring',
      position: new CallbackPositionProperty( () => {
        const position = currentVehiclePosition();
        return toCartesian( { ...position, alt_m: Math.max( position.alt_m - 1.8, 1 ) } );
      }, false ),
      ellipsoid: {
        radii: new Cartesian3( 10, 10, 0.55 ),
        material: new ColorMaterialProperty(
          new CallbackProperty( () => {
            const speakerOn = playbackBuffer.frame( performance.now() )?.vehicle.speakerOn ?? false;
            const pulse = 0.14 + ( ( Math.sin( performance.now() / 220 ) + 1 ) * 0.08 );
            return Color.fromCssColorString( '#ff8364' ).withAlpha( speakerOn ? pulse : 0 );
          }, false ),
        ),
        outline: true,
        outlineColor: new CallbackProperty( () => {
          const speakerOn = playbackBuffer.frame( performance.now() )?.vehicle.speakerOn ?? false;
          return Color.fromCssColorString( '#ffd4cb' ).withAlpha( speakerOn ? 0.7 : 0 );
        }, false ),
      },
    } );

    viewer.entities.add( {
      id: 'incursion-disc',
      position: new CallbackPositionProperty( () => toCartesian( currentIncursionPosition() ), false ),
      ellipsoid: {
        radii: new CallbackProperty( () => {
          const incursionRadiusM = playbackBuffer.frame( performance.now() )?.incursion.radiusM ?? 14;
          return new Cartesian3( incursionRadiusM, incursionRadiusM, 0.7 );
        }, false ),
        material: new ColorMaterialProperty(
          new CallbackProperty( () => {
            const incursionActive = playbackBuffer.frame( performance.now() )?.incursion.active ?? false;
            const pulse = 0.32 + ( ( Math.sin( performance.now() / 260 ) + 1 ) * 0.08 );
            return Color.fromCssColorString( '#d7263d' ).withAlpha( incursionActive ? pulse : 0 );
          }, false ),
        ),
        outline: true,
        outlineColor: Color.fromCssColorString( '#ffd8de' ).withAlpha( 0.82 ),
      },
    } );

    viewer.entities.add( {
      id: 'incursion-label',
      position: new CallbackPositionProperty( () => {
        const position = currentIncursionPosition();
        return toCartesian( { ...position, alt_m: position.alt_m + 3 } );
      }, false ),
      label: {
        text: new CallbackProperty( () => ( playbackBuffer.frame( performance.now() )?.incursion.active ?? false ) ? 'Incursion Group' : '', false ),
        fillColor: Color.fromCssColorString( '#fff1f3' ),
        font: '700 13px "Trebuchet MS"',
        pixelOffset: new Cartesian2( 0, -14 ),
        showBackground: true,
        style: LabelStyle.FILL,
        verticalOrigin: VerticalOrigin.BOTTOM,
      },
    } );

    void viewer.camera.flyTo( {
      destination: Cartesian3.fromDegrees(
        center.lon - ( lonSpan * 0.08 ),
        center.lat - ( latSpan * 0.88 ),
        360 + Math.max( latSpan, lonSpan ) * 170_000,
      ),
      orientation: {
        heading: CesiumMath.toRadians( 10 ),
        pitch: CesiumMath.toRadians( -54 ),
        roll: 0,
      },
      duration: 0.8,
    } );
  }

  return {
    currentPlaybackSnapshot() {
      return currentPlaybackSnapshot( performance.now() );
    },
    destroy() {
      viewer.destroy();
    },
    render( scene, state, reference, renderState ) {
      if ( scene === null ) {
        return;
      }
      void reference;
      ensureScene( scene );

      playbackBuffer.setTiming( state?.playback_speed ?? 1, state?.simulation_rate_hz ?? 1 );
      playbackBuffer.ingest( scene, state, renderState ?? null );
      playbackBuffer.frame( performance.now() );
      viewer.scene.requestRender();
    },
  };
}
