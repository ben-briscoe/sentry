import { useEffect, useRef, useState } from 'react';

import { createCesiumWorkspace, type WorkspacePlaybackSnapshot } from '../../viewport/cesiumWorkspace';
import { HISTORY_LIMIT, missionSessionStatus, type MissionHistoryPoint } from './model';
import { ControlRail, TelemetryRail, WorkspacePanel } from './components';
import { useMissionConsole } from './useMissionConsole';
import { useTelemetryRailLayout } from './useTelemetryRailLayout';


export function MissionConsole() {
  const viewportRef = useRef<HTMLDivElement | null>( null );
  const workspaceRef = useRef<ReturnType<typeof createCesiumWorkspace> | null>( null );
  const playbackHistoryKeyRef = useRef<string | null>( null );
  const playbackHistorySessionRef = useRef<string | null>( null );
  const controller = useMissionConsole();
  const telemetryRailLayout = useTelemetryRailLayout();
  const [ playbackSnapshot, setPlaybackSnapshot ] = useState<WorkspacePlaybackSnapshot | null>( null );
  const [ playbackHistory, setPlaybackHistory ] = useState<MissionHistoryPoint[]>( [] );
  const activePlaybackSnapshot = playbackSnapshot?.missionState?.session_id === controller.sessionId
    ? playbackSnapshot
    : null;
  const displayedMissionState = activePlaybackSnapshot?.missionState ?? controller.missionState;
  const displayedRenderState = activePlaybackSnapshot?.renderState ?? controller.renderState;
  const sessionStatus = missionSessionStatus(
    controller.sessionId,
    controller.availableMissionSessions,
    displayedMissionState?.mission_mode,
  );

  useEffect( () => {
    if ( viewportRef.current === null ) {
      return;
    }
    const workspace = createCesiumWorkspace( viewportRef.current );
    workspaceRef.current = workspace;
    const playbackTimer = window.setInterval( () => {
      setPlaybackSnapshot( workspace.currentPlaybackSnapshot() );
    }, 80 );
    return () => {
      window.clearInterval( playbackTimer );
      workspace.destroy();
      workspaceRef.current = null;
    };
  }, [] );

  useEffect( () => {
    if ( controller.sessionId === null || displayedMissionState === null ) {
      return;
    }
    const sessionChanged = playbackHistorySessionRef.current !== controller.sessionId;
    if ( sessionChanged ) {
      playbackHistorySessionRef.current = controller.sessionId;
      playbackHistoryKeyRef.current = null;
    }
    const missionTimeS = displayedMissionState.mission_time_s ?? ( displayedMissionState.time_ms !== null ? displayedMissionState.time_ms / 1000.0 : null );
    if ( missionTimeS === null ) {
      return;
    }
    const sampleBucket = Math.round( missionTimeS * 2 ) / 2;
    const sampleKey = `${controller.sessionId}:${sampleBucket}:${displayedMissionState.mission_mode ?? ''}`;
    if ( playbackHistoryKeyRef.current === sampleKey ) {
      return;
    }
    playbackHistoryKeyRef.current = sampleKey;
    setPlaybackHistory( ( current ) => [
      ...( sessionChanged ? [] : current ),
      {
        currentLoadW: displayedMissionState.current_load_w,
        currentSpeedMps: displayedMissionState.current_speed_mps,
        currentTotalPowerW: displayedMissionState.current_total_power_w,
        missionTimeS: sampleBucket,
        remainingEnergyJ: displayedMissionState.remaining_energy_j,
      },
    ].slice( -HISTORY_LIMIT ) );
  }, [ controller.sessionId, displayedMissionState ] );

  useEffect( () => {
    workspaceRef.current?.render(
      controller.scene,
      controller.missionState,
      controller.referenceMetrics,
      controller.renderState,
    );
  }, [ controller.missionState, controller.referenceMetrics, controller.renderState, controller.scene ] );

  return (
    <div className="mission-console">
      <header className="mission-banner">
        <div className="mission-banner__heading">
          <p className="eyebrow">SENTRY</p>
          <h1>Mission Scenario Playback</h1>
        </div>
        <p className="mission-banner__copy">
          Simulation driven by the Digital Engineering (DE) model of the Surveillance &amp; ENforcemenT Response sYstem (SENTRY). This representative project demonstrates how DE can support trade-space analysis during the early design of emerging systems. The interface is intended to reflect the mission activity being executed by the Cameo model.
        </p>
      </header>

      <div
        className="mission-console__layout"
        data-telemetry-collapsed={telemetryRailLayout.collapsed ? 'true' : 'false'}
        style={telemetryRailLayout.layoutStyle}
      >
        <ControlRail
          activeRouteKind={controller.activeRouteKind}
          applyInteractivePerturbation={controller.applyInteractivePerturbation}
          availableMissionSessions={controller.availableMissionSessions}
          bridgeState={controller.bridgeState}
          busy={controller.busy}
          consoleMode={controller.consoleMode}
          errorText={controller.errorText}
          healthText={controller.healthText}
          issueInteractiveCommand={controller.issueInteractiveCommand}
          lastEvent={controller.lastEvent}
          missionMode={displayedMissionState?.mission_mode}
          playbackSpeed={displayedMissionState?.playback_speed}
          refreshBridgeLink={controller.refreshBridgeLink}
          sessionId={controller.sessionId}
          setConsoleMode={controller.setConsoleMode}
          setPlaybackSpeed={controller.setPlaybackSpeed}
          startMission={controller.startMission}
        />

        <WorkspacePanel scene={controller.scene}>
          <div ref={viewportRef} className="viewport-canvas" />
        </WorkspacePanel>

        {!telemetryRailLayout.collapsed ? (
          <button
            type="button"
            className="telemetry-resize-handle"
            aria-label="Resize telemetry rail"
            onPointerDown={telemetryRailLayout.beginResize}
          />
        ) : null}

        <TelemetryRail
          collapsed={telemetryRailLayout.collapsed}
          history={playbackHistory.length > 0 ? playbackHistory : controller.history}
          missionState={displayedMissionState}
          onToggleCollapsed={telemetryRailLayout.toggleCollapsed}
          renderState={displayedRenderState}
          sessionStatus={sessionStatus}
        />
      </div>
    </div>
  );
}
