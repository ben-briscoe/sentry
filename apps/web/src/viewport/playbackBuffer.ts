import type {
  Coordinate,
  MissionState,
  RenderScene,
  RenderState,
} from '../types';
import {
  DEFAULT_COORDINATE,
  cloneCoordinate,
  coordinateDistanceM,
  headingBetween,
  interpolateNullableCoordinate,
  interpolateNullableNumber,
  isFiniteCoordinate,
  lerpCoordinate,
} from './sceneMath';


type BufferedRenderFrame = {
  incursion: {
    active: boolean;
    position: Coordinate | null;
    radiusM: number;
  };
  missionState: MissionState | null;
  modelTimeMs: number;
  renderState: RenderState | null;
  vehicle: {
    label: string;
    position: Coordinate;
    speakerOn: boolean;
    speedMps: number | null;
    spotlightOn: boolean;
  };
};

type PlaybackSegment = {
  durationMs: number;
  endFrame: BufferedRenderFrame;
  startFrame: BufferedRenderFrame;
  startedAtMs: number;
};

export type WorkspacePlaybackSnapshot = {
  missionState: MissionState | null;
  modelTimeMs: number | null;
  renderState: RenderState | null;
};


function cloneMissionState( missionState: MissionState | null ): MissionState | null {
  if ( missionState === null ) {
    return null;
  }
  return {
    ...missionState,
    attributes: { ...missionState.attributes },
  };
}


function interpolateMissionState(
  start: MissionState | null,
  end: MissionState | null,
  alpha: number,
): MissionState | null {
  if ( start === null || end === null ) {
    return cloneMissionState( alpha < 0.5 ? start : end );
  }
  return {
    ...start,
    time_ms: interpolateNullableNumber( start.time_ms, end.time_ms, alpha ),
    mission_time_s: interpolateNullableNumber( start.mission_time_s, end.mission_time_s, alpha ),
    real_time: start.real_time,
    playback_speed: interpolateNullableNumber( start.playback_speed, end.playback_speed, alpha ),
    simulation_rate_hz: interpolateNullableNumber( start.simulation_rate_hz, end.simulation_rate_hz, alpha ),
    current_speed_mps: interpolateNullableNumber( start.current_speed_mps, end.current_speed_mps, alpha ),
    current_propulsion_power_w: interpolateNullableNumber( start.current_propulsion_power_w, end.current_propulsion_power_w, alpha ),
    current_total_power_w: interpolateNullableNumber( start.current_total_power_w, end.current_total_power_w, alpha ),
    current_load_w: interpolateNullableNumber( start.current_load_w, end.current_load_w, alpha ),
    remaining_energy_j: interpolateNullableNumber( start.remaining_energy_j, end.remaining_energy_j, alpha ),
    distance_to_base_m: interpolateNullableNumber( start.distance_to_base_m, end.distance_to_base_m, alpha ),
    distance_to_perimeter_m: interpolateNullableNumber( start.distance_to_perimeter_m, end.distance_to_perimeter_m, alpha ),
    patrol_distance_remaining_m: interpolateNullableNumber( start.patrol_distance_remaining_m, end.patrol_distance_remaining_m, alpha ),
    track_time_remaining_s: interpolateNullableNumber( start.track_time_remaining_s, end.track_time_remaining_s, alpha ),
    tier1_engagement_time_remaining_s: interpolateNullableNumber( start.tier1_engagement_time_remaining_s, end.tier1_engagement_time_remaining_s, alpha ),
    mission_mode: start.mission_mode,
    attributes: { ...start.attributes },
  };
}


function cloneRenderState( renderState: RenderState | null ): RenderState | null {
  if ( renderState === null ) {
    return null;
  }
  return {
    vehicle: {
      ...renderState.vehicle,
      position: cloneCoordinate( renderState.vehicle.position ),
    },
    incursion: {
      ...renderState.incursion,
      position: renderState.incursion.position === null ? null : cloneCoordinate( renderState.incursion.position ),
    },
  };
}


function interpolateRenderState(
  start: RenderState | null,
  end: RenderState | null,
  alpha: number,
): RenderState | null {
  if ( start === null || end === null ) {
    return cloneRenderState( alpha < 0.5 ? start : end );
  }
  return {
    vehicle: {
      label: start.vehicle.label,
      position: lerpCoordinate( start.vehicle.position, end.vehicle.position, alpha ),
      speed_mps: interpolateNullableNumber( start.vehicle.speed_mps, end.vehicle.speed_mps, alpha ),
      spotlight_on: start.vehicle.spotlight_on,
      speaker_on: start.vehicle.speaker_on,
    },
    incursion: {
      label: start.incursion.label,
      position: interpolateNullableCoordinate( start.incursion.position, end.incursion.position, alpha ),
      active: start.incursion.active,
      radius_m: interpolateNullableNumber( start.incursion.radius_m, end.incursion.radius_m, alpha ) ?? start.incursion.radius_m,
    },
  };
}


function segmentAlpha( segment: PlaybackSegment | null, nowMs: number ): number {
  if ( segment === null ) {
    return 1;
  }
  if ( segment.durationMs <= 0 ) {
    return 1;
  }
  return Math.min( Math.max( ( nowMs - segment.startedAtMs ) / segment.durationMs, 0 ), 1 );
}


function desiredStartupBufferMs( simulationRateHz: number ): number {
  const modelTickMs = 1000 / Math.max( simulationRateHz, 0.1 );
  return Math.min( Math.max( modelTickMs * 4, 1200 ), 3200 );
}


function desiredResumeBufferMs( simulationRateHz: number ): number {
  const modelTickMs = 1000 / Math.max( simulationRateHz, 0.1 );
  return Math.min( Math.max( modelTickMs * 1.5, 350 ), 1400 );
}


function desiredStartupFrameCount( simulationRateHz: number ): number {
  if ( simulationRateHz >= 3 ) {
    return 6;
  }
  if ( simulationRateHz >= 1.5 ) {
    return 5;
  }
  return 4;
}


function desiredResumeFrameCount( simulationRateHz: number ): number {
  return simulationRateHz >= 2 ? 3 : 2;
}


function playbackSegmentDurationMs(
  startFrame: BufferedRenderFrame,
  endFrame: BufferedRenderFrame,
  playbackSpeed: number,
): number {
  const modelDeltaMs = Math.max( endFrame.modelTimeMs - startFrame.modelTimeMs, 0 );
  const distanceM = coordinateDistanceM( startFrame.vehicle.position, endFrame.vehicle.position );
  const nominalSpeedMps = Math.max(
    startFrame.vehicle.speedMps ?? endFrame.vehicle.speedMps ?? 5.0,
    0.1,
  );
  const kinematicDurationMs = ( distanceM / nominalSpeedMps ) * 1000;
  const baseDurationMs = Math.max( modelDeltaMs, kinematicDurationMs );
  if ( baseDurationMs <= 0 ) {
    return 0;
  }
  return Math.min( Math.max( baseDurationMs / Math.max( playbackSpeed, 0.1 ), 180 ), 5000 );
}


export class PlaybackBuffer {
  private displayedFrame: BufferedRenderFrame | null = null;
  private frameBuffer: BufferedRenderFrame[] = [];
  private playbackPrimed = false;
  private playbackSegment: PlaybackSegment | null = null;
  private vehicleHeadingDeg = 0;
  private latestPlaybackSpeed = 1;
  private latestSimulationRateHz = 1;
  private lastReceivedModelTimeMs: number | null = null;

  reset(): void {
    this.displayedFrame = null;
    this.frameBuffer = [];
    this.playbackPrimed = false;
    this.playbackSegment = null;
    this.vehicleHeadingDeg = 0;
    this.lastReceivedModelTimeMs = null;
  }

  setTiming( playbackSpeed: number, simulationRateHz: number ): void {
    this.latestPlaybackSpeed = Math.max( playbackSpeed, 0.1 );
    this.latestSimulationRateHz = Math.max( simulationRateHz, 0.1 );
  }

  heading( nowMs: number ): number {
    this.frame( nowMs );
    return this.vehicleHeadingDeg;
  }

  vehiclePosition( nowMs: number ): Coordinate {
    return cloneCoordinate( this.frame( nowMs )?.vehicle.position ?? DEFAULT_COORDINATE );
  }

  incursionPosition( nowMs: number ): Coordinate {
    return cloneCoordinate( this.frame( nowMs )?.incursion.position ?? DEFAULT_COORDINATE );
  }

  motionNeighbors( nowMs: number ): {
    current: Coordinate;
    next: Coordinate | null;
    previous: Coordinate | null;
  } {
    const current = cloneCoordinate( this.frame( nowMs )?.vehicle.position ?? DEFAULT_COORDINATE );
    return {
      current,
      previous: this.playbackSegment?.startFrame.vehicle.position ?? this.displayedFrame?.vehicle.position ?? null,
      next: this.playbackSegment?.endFrame.vehicle.position ?? this.frameBuffer[0]?.vehicle.position ?? null,
    };
  }

  ingest( scene: RenderScene, state: MissionState | null, renderState: RenderState | null ): void {
    const nextModelTimeMs = state?.time_ms ?? null;
    if ( nextModelTimeMs === null || renderState === null || nextModelTimeMs === this.lastReceivedModelTimeMs ) {
      return;
    }

    if ( this.lastReceivedModelTimeMs !== null && nextModelTimeMs < this.lastReceivedModelTimeMs ) {
      this.reset();
    }

    const nextVehiclePosition = renderState.vehicle.position ?? scene.base;
    const safeVehiclePosition = isFiniteCoordinate( nextVehiclePosition ) ? nextVehiclePosition : scene.base;
    const nextIncursionPosition = renderState.incursion.position;
    const safeIncursionPosition = nextIncursionPosition !== null && isFiniteCoordinate( nextIncursionPosition )
      ? nextIncursionPosition
      : null;

    this.frameBuffer.push( {
      missionState: cloneMissionState( state ),
      modelTimeMs: nextModelTimeMs,
      renderState: cloneRenderState( renderState ),
      vehicle: {
        label: renderState.vehicle.label ?? `SENTRY${state?.mission_mode ? ` | ${state.mission_mode}` : ''}`,
        position: safeVehiclePosition,
        speakerOn: renderState.vehicle.speaker_on ?? false,
        speedMps: renderState.vehicle.speed_mps ?? state?.current_speed_mps ?? null,
        spotlightOn: renderState.vehicle.spotlight_on ?? false,
      },
      incursion: {
        active: renderState.incursion.active ?? false,
        position: safeIncursionPosition,
        radiusM: renderState.incursion.radius_m ?? 14,
      },
    } );
    this.lastReceivedModelTimeMs = nextModelTimeMs;
  }

  frame( nowMs: number ): BufferedRenderFrame | null {
    if ( this.displayedFrame === null && this.frameBuffer.length > 0 ) {
      this.displayedFrame = this.frameBuffer.shift() ?? null;
    }

    const latestBufferedFrame = this.frameBuffer.at( -1 ) ?? this.displayedFrame;
    if ( this.displayedFrame !== null && latestBufferedFrame !== undefined && latestBufferedFrame !== null ) {
      const availableBufferMs = latestBufferedFrame.modelTimeMs - this.displayedFrame.modelTimeMs;
      const startupBufferMs = desiredStartupBufferMs( this.latestSimulationRateHz );
      const resumeBufferMs = desiredResumeBufferMs( this.latestSimulationRateHz );
      const requiredBufferMs = this.playbackPrimed ? resumeBufferMs : startupBufferMs;
      const bufferedFrameCount = this.frameBuffer.length + 1;
      const requiredFrameCount = this.playbackPrimed
        ? desiredResumeFrameCount( this.latestSimulationRateHz )
        : desiredStartupFrameCount( this.latestSimulationRateHz );
      if ( availableBufferMs >= requiredBufferMs && bufferedFrameCount >= requiredFrameCount ) {
        this.playbackPrimed = true;
      }
    }

    while ( true ) {
      if ( this.playbackSegment === null ) {
        if ( !this.playbackPrimed || this.displayedFrame === null || this.frameBuffer.length === 0 ) {
          break;
        }
        const latestBuffered = this.frameBuffer.at( -1 ) ?? this.displayedFrame;
        const availableBufferMs = latestBuffered.modelTimeMs - this.displayedFrame.modelTimeMs;
        if ( availableBufferMs < desiredResumeBufferMs( this.latestSimulationRateHz ) ) {
          break;
        }
        const nextFrame = this.frameBuffer[ 0 ];
        this.vehicleHeadingDeg = headingBetween( this.displayedFrame.vehicle.position, nextFrame.vehicle.position, this.vehicleHeadingDeg );
        this.playbackSegment = {
          startFrame: this.displayedFrame,
          endFrame: nextFrame,
          startedAtMs: nowMs,
          durationMs: playbackSegmentDurationMs( this.displayedFrame, nextFrame, this.latestPlaybackSpeed ),
        };
      }

      if ( this.playbackSegment === null || segmentAlpha( this.playbackSegment, nowMs ) < 1 ) {
        break;
      }

      this.displayedFrame = this.frameBuffer.shift() ?? this.playbackSegment.endFrame;
      this.playbackSegment = null;
    }

    if ( this.playbackSegment !== null ) {
      const alpha = segmentAlpha( this.playbackSegment, nowMs );
      return {
        missionState: interpolateMissionState(
          this.playbackSegment.startFrame.missionState,
          this.playbackSegment.endFrame.missionState,
          alpha,
        ),
        modelTimeMs: this.playbackSegment.startFrame.modelTimeMs,
        renderState: interpolateRenderState(
          this.playbackSegment.startFrame.renderState,
          this.playbackSegment.endFrame.renderState,
          alpha,
        ),
        vehicle: {
          label: this.playbackSegment.startFrame.vehicle.label,
          position: lerpCoordinate( this.playbackSegment.startFrame.vehicle.position, this.playbackSegment.endFrame.vehicle.position, alpha ),
          speakerOn: this.playbackSegment.startFrame.vehicle.speakerOn,
          speedMps: this.playbackSegment.startFrame.vehicle.speedMps,
          spotlightOn: this.playbackSegment.startFrame.vehicle.spotlightOn,
        },
        incursion: {
          active: this.playbackSegment.startFrame.incursion.active,
          position: interpolateNullableCoordinate(
            this.playbackSegment.startFrame.incursion.position,
            this.playbackSegment.endFrame.incursion.position,
            alpha,
          ),
          radiusM: this.playbackSegment.startFrame.incursion.radiusM,
        },
      };
    }

    return this.displayedFrame;
  }

  snapshot( nowMs: number ): WorkspacePlaybackSnapshot | null {
    const frame = this.frame( nowMs );
    if ( frame === null ) {
      return null;
    }
    if ( this.playbackSegment !== null ) {
      const alpha = segmentAlpha( this.playbackSegment, nowMs );
      return {
        modelTimeMs: interpolateNullableNumber(
          this.playbackSegment.startFrame.modelTimeMs,
          this.playbackSegment.endFrame.modelTimeMs,
          alpha,
        ),
        missionState: interpolateMissionState(
          this.playbackSegment.startFrame.missionState,
          this.playbackSegment.endFrame.missionState,
          alpha,
        ),
        renderState: interpolateRenderState(
          this.playbackSegment.startFrame.renderState,
          this.playbackSegment.endFrame.renderState,
          alpha,
        ),
      };
    }
    return {
      modelTimeMs: frame.modelTimeMs,
      missionState: cloneMissionState( frame.missionState ),
      renderState: cloneRenderState( frame.renderState ),
    };
  }
}
