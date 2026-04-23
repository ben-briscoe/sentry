import type {
  MissionServiceSessionSummary,
  MissionServiceSessionView,
  MissionState,
  ReferenceMetrics,
  RenderScene,
} from '../../types';


export type ConsoleMode = 'open_loop' | 'interactive';
export type MetricTone = 'neutral' | 'good' | 'warn';
export type InteractiveCommandKind =
  | 'assign_patrol'
  | 'recall'
  | 'authorize_tier1'
  | 'resume_patrol'
  | 'intercept_incursion';
export type InteractivePerturbationKind =
  | 'incursion_spawn'
  | 'route_deviation'
  | 'incursion_speed_change'
  | 'all_clear';
export type InteractivePerturbationOptions = {
  direction?: 'left' | 'right';
  offset_m?: number;
  speed_mps?: number;
};
export type MissionHistoryPoint = {
  currentLoadW: number | null;
  currentSpeedMps: number | null;
  currentTotalPowerW: number | null;
  missionTimeS: number;
  remainingEnergyJ: number | null;
};

export const HISTORY_LIMIT = 240;
export const DEFAULT_REFERENCE_METRICS: ReferenceMetrics = {
  distanceToBaseStartM: null,
  distanceToPerimeterStartM: null,
  patrolDistanceStartM: null,
  trackTimeStartS: null,
  tier1EngagementStartS: null,
};
export const PLAYBACK_SPEED_OPTIONS = [ 1, 2, 4 ] as const;

const MISSION_MODE_LABELS: Array<[ string, string ]> = [
  [ 'MISSION_SUCCESS', 'Mission Success' ],
  [ 'MISSION_FAIL', 'Mission Fail' ],
  [ 'TIER_1_ENGAGE', 'Tier 1 Engage' ],
  [ 'TIER1_ENGAGE', 'Tier 1 Engage' ],
  [ 'TIER1', 'Tier 1 Engage' ],
  [ 'TRACK', 'Track' ],
  [ 'PATROL', 'Patrol' ],
  [ 'TRANSIT_TO_PERIMETER', 'Transit To Perimeter' ],
  [ 'RETURN_TO_BASE', 'Return To Base' ],
  [ 'RETURN', 'Return To Base' ],
  [ 'IDLE', 'Idle' ],
];


export function numericText( value: number | null | undefined, digits = 1, suffix = '' ): string {
  if ( value === null || value === undefined || Number.isNaN( value ) ) {
    return 'n/a';
  }
  return `${value.toFixed( digits )}${suffix}`;
}


export function displayMissionMode( missionMode: string | null | undefined ): string {
  if ( missionMode === null || missionMode === undefined || missionMode.trim() === '' ) {
    return 'Waiting on Cameo';
  }

  for ( const [ token, label ] of MISSION_MODE_LABELS ) {
    if ( missionMode.includes( token ) ) {
      return label;
    }
  }

  const trailingToken = missionMode
    .split( /[:.]/ )
    .map( ( part ) => part.trim() )
    .filter( Boolean )
    .at( -1 );

  if ( trailingToken ) {
    return trailingToken
      .replace( /_/g, ' ' )
      .replace( /\s+/g, ' ' )
      .trim()
      .replace( /\b\w/g, ( character ) => character.toUpperCase() );
  }

  return missionMode;
}


export function sceneTitle( scene: RenderScene | null ): string {
  if ( scene === null ) {
    return 'Mission Workspace';
  }
  if ( scene.id === 'jordan_hare_event_corridor_v1' ) {
    return 'Jordan-Hare Event Corridor';
  }
  return scene.id
    .replace( /_/g, ' ' )
    .replace( /\s+/g, ' ' )
    .trim()
    .replace( /\b\w/g, ( character ) => character.toUpperCase() );
}


export function updateReferenceMetrics( current: ReferenceMetrics, state: MissionState ): ReferenceMetrics {
  return {
    distanceToBaseStartM: current.distanceToBaseStartM ?? state.distance_to_base_m,
    distanceToPerimeterStartM: current.distanceToPerimeterStartM ?? state.distance_to_perimeter_m,
    patrolDistanceStartM: current.patrolDistanceStartM ?? state.patrol_distance_remaining_m,
    trackTimeStartS: current.trackTimeStartS ?? state.track_time_remaining_s,
    tier1EngagementStartS: current.tier1EngagementStartS ?? state.tier1_engagement_time_remaining_s,
  };
}


export function modeledStateToMissionState( sessionId: string, view: MissionServiceSessionView ): MissionState | null {
  const modeled = view.modeled_state;
  if ( modeled === null ) {
    return null;
  }
  return {
    session_id: sessionId,
    step_index: 0,
    time_ms: modeled.time_ms ?? null,
    mission_mode: modeled.mission_mode ?? null,
    mission_time_s: modeled.mission_time_s ?? null,
    real_time: modeled.real_time ?? null,
    playback_speed: modeled.playback_speed ?? null,
    simulation_rate_hz: modeled.simulation_rate_hz ?? null,
    current_speed_mps: modeled.current_speed_mps ?? null,
    current_propulsion_power_w: modeled.current_propulsion_power_w ?? null,
    current_total_power_w: modeled.current_total_power_w ?? null,
    current_load_w: modeled.current_load_w ?? null,
    remaining_energy_j: modeled.remaining_energy_j ?? null,
    distance_to_base_m: modeled.distance_to_base_m ?? null,
    distance_to_perimeter_m: modeled.distance_to_perimeter_m ?? null,
    patrol_distance_remaining_m: modeled.patrol_distance_remaining_m ?? null,
    track_time_remaining_s: modeled.track_time_remaining_s ?? null,
    tier1_engagement_time_remaining_s: modeled.tier1_engagement_time_remaining_s ?? null,
    attributes: modeled.attributes ?? {},
  };
}


export function livePollIntervalMs( state: MissionState | null ): number {
  if ( state === null ) {
    return 220;
  }
  if ( state.real_time !== true ) {
    return 180;
  }
  const rate = state.simulation_rate_hz ?? 1.0;
  const playback = state.playback_speed ?? 1.0;
  const tickMs = 1000.0 / Math.max( rate * playback, 0.1 );
  return Math.max( 80, Math.min( 240, Math.round( tickMs * 0.25 ) ) );
}


export function isMissionTerminal( missionMode: string | null | undefined ): boolean {
  if ( missionMode === null || missionMode === undefined ) {
    return false;
  }
  return missionMode.includes( 'MISSION_SUCCESS' ) || missionMode.includes( 'MISSION_FAIL' );
}


export function toneForMissionMode( missionMode: string | null | undefined ): MetricTone {
  if ( missionMode === null || missionMode === undefined ) {
    return 'neutral';
  }
  if ( missionMode.includes( 'SUCCESS' ) ) {
    return 'good';
  }
  if ( missionMode.includes( 'FAIL' ) ) {
    return 'warn';
  }
  return 'neutral';
}


export function playbackModeText( state: MissionState | null ): string {
  if ( state?.real_time === true ) {
    return 'Realtime';
  }
  if ( state?.real_time === false ) {
    return 'Accelerated';
  }
  return 'n/a';
}


export function missionSessionStatus(
  sessionId: string | null,
  availableMissionSessions: MissionServiceSessionSummary[],
  missionMode: string | null | undefined,
): string {
  if ( sessionId !== null ) {
    return isMissionTerminal( missionMode ) ? 'Complete' : 'Attached';
  }
  return availableMissionSessions.length > 0 ? 'Ready To Start' : 'Awaiting Cameo Session';
}


export function activeMissionSessionLabel(
  sessionId: string | null,
  availableMissionSessions: MissionServiceSessionSummary[],
): string {
  return sessionId ?? availableMissionSessions[0]?.session_id ?? 'none detected';
}
