import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ApiError,
  applyMissionPerturbation,
  getHealth,
  getMissionBridgeView,
  listMissionServiceSessions,
  sendMissionCommand,
} from '../../api/client';
import type {
  MissionBridgeState,
  MissionServiceSessionSummary,
  MissionServiceSessionView,
  MissionState,
  ReferenceMetrics,
  RenderScene,
  RenderState,
} from '../../types';
import {
  DEFAULT_REFERENCE_METRICS,
  HISTORY_LIMIT,
  type ConsoleMode,
  type InteractiveCommandKind,
  type InteractivePerturbationKind,
  type InteractivePerturbationOptions,
  type MissionHistoryPoint,
  livePollIntervalMs,
  modeledStateToMissionState,
  updateReferenceMetrics,
} from './model';


type MissionConsoleState = {
  activeRouteKind: string | null;
  availableMissionSessions: MissionServiceSessionSummary[];
  bridgeState: MissionBridgeState | null;
  busy: boolean;
  consoleMode: ConsoleMode;
  errorText: string | null;
  healthText: string;
  history: MissionHistoryPoint[];
  lastEvent: string | null;
  missionState: MissionState | null;
  referenceMetrics: ReferenceMetrics;
  renderState: RenderState | null;
  scene: RenderScene | null;
  sessionId: string | null;
};

type MissionConsoleActions = {
  applyInteractivePerturbation: (
    kind: InteractivePerturbationKind,
    options?: InteractivePerturbationOptions,
  ) => Promise<void>;
  issueInteractiveCommand: ( kind: InteractiveCommandKind ) => Promise<void>;
  refreshBridgeLink: () => Promise<MissionServiceSessionSummary[]>;
  setConsoleMode: ( mode: ConsoleMode ) => void;
  setPlaybackSpeed: ( playbackSpeed: number ) => Promise<void>;
  startMission: () => Promise<void>;
};

export type MissionConsoleController = MissionConsoleState & MissionConsoleActions;


export function useMissionConsole(): MissionConsoleController {
  const lastHistoryKeyRef = useRef<string | null>( null );

  const [ consoleMode, setConsoleMode ] = useState<ConsoleMode>( 'open_loop' );
  const [ availableMissionSessions, setAvailableMissionSessions ] = useState<MissionServiceSessionSummary[]>( [] );
  const [ healthText, setHealthText ] = useState( 'checking' );
  const [ busy, setBusy ] = useState( false );
  const [ errorText, setErrorText ] = useState<string | null>( null );
  const [ referenceMetrics, setReferenceMetrics ] = useState<ReferenceMetrics>( DEFAULT_REFERENCE_METRICS );
  const [ sessionId, setSessionId ] = useState<string | null>( null );
  const [ sessionView, setSessionView ] = useState<MissionServiceSessionView | null>( null );
  const [ history, setHistory ] = useState<MissionHistoryPoint[]>( [] );

  const missionState = sessionId !== null && sessionView !== null
    ? modeledStateToMissionState( sessionId, sessionView )
    : null;
  const scene = sessionView?.snapshot.scene ?? null;
  const renderState = sessionView?.render_state ?? null;
  const bridgeState = sessionView?.bridge_state ?? null;
  const activeRouteKind = sessionView?.snapshot.active_route_kind ?? null;
  const lastEvent = sessionView?.snapshot.last_event ?? null;
  const pollIntervalMs = livePollIntervalMs( missionState );

  useEffect( () => {
    if ( sessionId === null || missionState === null ) {
      return;
    }
    const missionTimeS = missionState.mission_time_s ?? ( missionState.time_ms !== null ? missionState.time_ms / 1000.0 : null );
    if ( missionTimeS === null ) {
      return;
    }
    const sampleKey = `${sessionId}:${missionState.time_ms ?? missionTimeS}:${missionState.mission_mode ?? ''}`;
    if ( lastHistoryKeyRef.current === sampleKey ) {
      return;
    }
    lastHistoryKeyRef.current = sampleKey;
    setHistory( ( current ) => [
      ...current,
      {
        currentLoadW: missionState.current_load_w,
        currentSpeedMps: missionState.current_speed_mps,
        currentTotalPowerW: missionState.current_total_power_w,
        missionTimeS,
        remainingEnergyJ: missionState.remaining_energy_j,
      },
    ].slice( -HISTORY_LIMIT ) );
  }, [ missionState, sessionId ] );

  const resetAttachedMissionState = useCallback( (): void => {
    setHistory( [] );
    setReferenceMetrics( DEFAULT_REFERENCE_METRICS );
    setSessionView( null );
    lastHistoryKeyRef.current = null;
  }, [] );

  const detachMissingMissionSession = useCallback( ( message?: string ): void => {
    setSessionId( null );
    resetAttachedMissionState();
    if ( message ) {
      setErrorText( message );
    }
  }, [ resetAttachedMissionState ] );

  const pollLiveMissionSession = useCallback( async ( liveSessionId: string, foreground = true ): Promise<void> => {
    try {
      const view = await getMissionBridgeView( liveSessionId );
      const nextMissionState = modeledStateToMissionState( liveSessionId, view );
      setSessionView( view );
      if ( nextMissionState !== null ) {
        setReferenceMetrics( ( current ) => updateReferenceMetrics( current, nextMissionState ) );
      }
      if ( foreground ) {
        setErrorText( null );
      }
    } catch ( error ) {
      if ( error instanceof ApiError && error.status === 404 ) {
        detachMissingMissionSession( 'The attached mission session expired after the bridge server restarted. Create a new mission session in MSOSA and start live sync again.' );
        return;
      }
      if ( foreground ) {
        setErrorText( error instanceof Error ? error.message : 'Unable to attach to the live mission session.' );
      }
    }
  }, [ detachMissingMissionSession ] );

  const refreshBridgeLink = useCallback( async (): Promise<MissionServiceSessionSummary[]> => {
    try {
      const sessions = await listMissionServiceSessions();
      setAvailableMissionSessions( sessions );
      if ( sessionId !== null && sessions.some( ( session ) => session.session_id === sessionId ) ) {
        await pollLiveMissionSession( sessionId, false );
      } else if ( sessionId !== null ) {
        detachMissingMissionSession( 'The previously attached mission session is no longer available. Start a fresh mission session from MSOSA.' );
      }
      return sessions;
    } catch {
      return [];
    }
  }, [ detachMissingMissionSession, pollLiveMissionSession, sessionId ] );

  useEffect( () => {
    void getHealth()
      .then( ( response ) => {
        setHealthText( response.status );
      } )
      .catch( ( error: unknown ) => {
        setHealthText( 'down' );
        setErrorText( error instanceof Error ? error.message : 'Unable to reach the bridge API.' );
      } );

    const initialRefreshTimer = window.setTimeout( () => {
      void refreshBridgeLink();
    }, 0 );
    const sessionTimer = window.setInterval( () => {
      void refreshBridgeLink();
    }, 5000 );

    return () => {
      window.clearTimeout( initialRefreshTimer );
      window.clearInterval( sessionTimer );
    };
  }, [ refreshBridgeLink ] );

  useEffect( () => {
    if ( sessionId === null ) {
      return;
    }
    const timer = window.setInterval( () => {
      void pollLiveMissionSession( sessionId, false );
    }, pollIntervalMs );

    return () => {
      window.clearInterval( timer );
    };
  }, [ pollIntervalMs, pollLiveMissionSession, sessionId ] );

  async function startMission(): Promise<void> {
    setBusy( true );
    setErrorText( null );
    try {
      const sessions = await refreshBridgeLink();
      const targetSessionId = sessionId !== null && sessions.some( ( session ) => session.session_id === sessionId )
        ? sessionId
        : sessions[0]?.session_id ?? null;
      if ( targetSessionId === null ) {
        throw new Error( 'No active Cameo mission session detected. In MSOSA, create a mission session and start live DRMAnalysis sync first.' );
      }
      if ( targetSessionId !== sessionId ) {
        resetAttachedMissionState();
      }
      setSessionId( targetSessionId );
      await pollLiveMissionSession( targetSessionId );
    } catch ( error ) {
      setErrorText( error instanceof Error ? error.message : 'Unable to attach to the active mission session.' );
    } finally {
      setBusy( false );
    }
  }

  async function setPlaybackSpeed( playbackSpeed: number ): Promise<void> {
    if ( sessionId === null ) {
      return;
    }
    setBusy( true );
    setErrorText( null );
    try {
      await sendMissionCommand( sessionId, {
        kind: 'set_playback_speed',
        playback_speed: playbackSpeed,
        real_time: true,
      } );
      await pollLiveMissionSession( sessionId, false );
    } catch ( error ) {
      setErrorText( error instanceof Error ? error.message : 'Unable to update playback speed.' );
    } finally {
      setBusy( false );
    }
  }

  async function issueInteractiveCommand( kind: InteractiveCommandKind ): Promise<void> {
    if ( sessionId === null ) {
      return;
    }
    setBusy( true );
    setErrorText( null );
    try {
      await sendMissionCommand( sessionId, {
        kind,
        current_position: renderState?.vehicle.position ?? undefined,
        patrol_area: scene?.patrol_area ?? [],
        target_route: scene?.incursion_route ?? [],
        sentry_speed_mps: missionState?.current_speed_mps ?? renderState?.vehicle.speed_mps ?? undefined,
      } );
      await pollLiveMissionSession( sessionId, false );
    } catch ( error ) {
      setErrorText( error instanceof Error ? error.message : 'Unable to issue the mission command.' );
    } finally {
      setBusy( false );
    }
  }

  async function applyInteractivePerturbation(
    kind: InteractivePerturbationKind,
    options?: InteractivePerturbationOptions,
  ): Promise<void> {
    if ( sessionId === null ) {
      return;
    }
    setBusy( true );
    setErrorText( null );
    try {
      await applyMissionPerturbation( sessionId, {
        kind,
        route: kind === 'incursion_spawn' ? ( scene?.incursion_route ?? [] ) : undefined,
        direction: options?.direction,
        offset_m: options?.offset_m,
        speed_mps: options?.speed_mps,
      } );
      await pollLiveMissionSession( sessionId, false );
    } catch ( error ) {
      setErrorText( error instanceof Error ? error.message : 'Unable to apply the interactive scenario update.' );
    } finally {
      setBusy( false );
    }
  }

  return {
    activeRouteKind,
    applyInteractivePerturbation,
    availableMissionSessions,
    bridgeState,
    busy,
    consoleMode,
    errorText,
    healthText,
    history,
    issueInteractiveCommand,
    lastEvent,
    missionState,
    referenceMetrics,
    refreshBridgeLink,
    renderState,
    scene,
    sessionId,
    setConsoleMode,
    setPlaybackSpeed,
    startMission,
  };
}
