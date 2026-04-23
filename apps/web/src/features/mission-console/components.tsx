import type { ReactNode } from 'react';

import type {
  MissionBridgeState,
  MissionServiceSessionSummary,
  MissionState,
  RenderScene,
  RenderState,
} from '../../types';
import {
  PLAYBACK_SPEED_OPTIONS,
  activeMissionSessionLabel,
  displayMissionMode,
  missionSessionStatus,
  numericText,
  playbackModeText,
  sceneTitle,
  toneForMissionMode,
  type ConsoleMode,
  type InteractiveCommandKind,
  type InteractivePerturbationKind,
  type InteractivePerturbationOptions,
  type MetricTone,
  type MissionHistoryPoint,
} from './model';


type MetricCardProps = {
  label: string;
  tone?: MetricTone;
  value: string;
};

type StatusLineProps = {
  label: string;
  value: string;
};

type TrendPlotProps = {
  accentClassName: string;
  currentValue: string;
  forceZeroMin?: boolean;
  label: string;
  samples: MissionHistoryPoint[];
  valueAccessor: ( sample: MissionHistoryPoint ) => number | null;
};

type ControlRailProps = {
  activeRouteKind: string | null;
  availableMissionSessions: MissionServiceSessionSummary[];
  bridgeState: MissionBridgeState | null;
  busy: boolean;
  consoleMode: ConsoleMode;
  errorText: string | null;
  healthText: string;
  issueInteractiveCommand: ( kind: InteractiveCommandKind ) => Promise<void>;
  lastEvent: string | null;
  missionMode: string | null | undefined;
  refreshBridgeLink: () => Promise<unknown>;
  sessionId: string | null;
  setConsoleMode: ( mode: ConsoleMode ) => void;
  setPlaybackSpeed: ( speed: number ) => Promise<void>;
  startMission: () => Promise<void>;
  playbackSpeed: number | null | undefined;
  applyInteractivePerturbation: (
    kind: InteractivePerturbationKind,
    options?: InteractivePerturbationOptions,
  ) => Promise<void>;
};

type WorkspacePanelProps = {
  children: ReactNode;
  scene: RenderScene | null;
};

type TelemetryRailProps = {
  collapsed: boolean;
  history: MissionHistoryPoint[];
  missionState: MissionState | null;
  onToggleCollapsed: () => void;
  renderState: RenderState | null;
  sessionStatus: string;
};

const INTERACTIVE_BUTTONS: Array<{
  action: InteractiveCommandKind | InteractivePerturbationKind;
  kind: 'command' | 'perturbation';
  label: string;
  options?: InteractivePerturbationOptions;
}> = [
  { action: 'assign_patrol', kind: 'command', label: 'Assign Patrol' },
  { action: 'recall', kind: 'command', label: 'Recall' },
  { action: 'authorize_tier1', kind: 'command', label: 'Authorize Tier 1' },
  { action: 'resume_patrol', kind: 'command', label: 'Resume Patrol' },
  { action: 'intercept_incursion', kind: 'command', label: 'Intercept' },
  { action: 'incursion_spawn', kind: 'perturbation', label: 'Spawn Incursion' },
  { action: 'route_deviation', kind: 'perturbation', label: 'Deviate Left', options: { direction: 'left', offset_m: 28 } },
  { action: 'route_deviation', kind: 'perturbation', label: 'Deviate Right', options: { direction: 'right', offset_m: 28 } },
  { action: 'incursion_speed_change', kind: 'perturbation', label: 'Speed Up Incursion', options: { speed_mps: 6.0 } },
  { action: 'all_clear', kind: 'perturbation', label: 'All Clear' },
];


function MetricCard( { label, tone = 'neutral', value }: MetricCardProps ) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <span className="metric-card__label">{label}</span>
      <strong className="metric-card__value">{value}</strong>
    </article>
  );
}


function StatusLine( { label, value }: StatusLineProps ) {
  return (
    <p className="status-line">
      <span>{label}</span>
      <strong>{value}</strong>
    </p>
  );
}


function TrendPlot( { accentClassName, currentValue, forceZeroMin = false, label, samples, valueAccessor }: TrendPlotProps ) {
  const width = 320;
  const height = 122;
  const padding = 12;

  const points = samples
    .map( ( sample, index ) => {
      const value = valueAccessor( sample );
      if ( value === null || Number.isNaN( value ) ) {
        return null;
      }
      return {
        index,
        time: Number.isFinite( sample.missionTimeS ) ? sample.missionTimeS : index,
        value,
      };
    } )
    .filter( ( point ): point is { index: number; time: number; value: number } => point !== null );

  const finiteValues = points.map( ( point ) => point.value );
  const dataMin = finiteValues.length > 0 ? Math.min( ...finiteValues ) : 0;
  const max = finiteValues.length > 0 ? Math.max( ...finiteValues ) : 1;
  const min = forceZeroMin ? Math.min( 0, dataMin ) : dataMin;
  const range = Math.max( max - min, 1 );
  const startTime = points.length > 0 ? points[0].time : 0;
  const endTime = points.length > 0 ? points[points.length - 1].time : 1;
  const timeRange = Math.max( endTime - startTime, 1 );

  const chartPoints = points.map( ( point ) => {
    const x = padding + ( ( point.time - startTime ) / timeRange ) * ( width - padding * 2 );
    const y = height - padding - ( ( point.value - min ) / range ) * ( height - padding * 2 );
    return { x, y };
  } );

  const linePath = chartPoints.length > 0
    ? chartPoints
      .map( ( point, index ) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed( 2 )} ${point.y.toFixed( 2 )}` )
      .join( ' ' )
    : '';
  const areaPath = chartPoints.length > 1
    ? `${linePath} L ${chartPoints[chartPoints.length - 1].x.toFixed( 2 )} ${( height - padding ).toFixed( 2 )} L ${chartPoints[0].x.toFixed( 2 )} ${( height - padding ).toFixed( 2 )} Z`
    : '';

  return (
    <section className="trend-card">
      <div className="trend-card__header">
        <div>
          <p className="eyebrow">{label}</p>
          <strong className="trend-card__value">{currentValue}</strong>
        </div>
        <div className="trend-card__range">
          <span>{numericText( max, 0 )}</span>
          <span>{numericText( min, 0 )}</span>
        </div>
      </div>
      <svg className={`trend-card__plot ${accentClassName}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} trend`}>
        <line className="trend-card__grid" x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line className="trend-card__grid" x1={padding} y1={padding} x2={width - padding} y2={padding} />
        {areaPath ? <path className="trend-card__area" d={areaPath} /> : null}
        {linePath ? <path className="trend-card__line" d={linePath} /> : null}
      </svg>
    </section>
  );
}


function TelemetryChevronIcon( props: { collapsed: boolean } ) {
  const { collapsed } = props;

  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      {collapsed
        ? <path d="M10 4L6 8L10 12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />
        : <path d="M6 4L10 8L6 12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" />}
    </svg>
  );
}


export function ControlRail( {
  activeRouteKind,
  applyInteractivePerturbation,
  availableMissionSessions,
  bridgeState,
  busy,
  consoleMode,
  errorText,
  healthText,
  issueInteractiveCommand,
  lastEvent,
  missionMode,
  playbackSpeed,
  refreshBridgeLink,
  sessionId,
  setConsoleMode,
  setPlaybackSpeed,
  startMission,
}: ControlRailProps ) {
  const activeMissionSession = activeMissionSessionLabel( sessionId, availableMissionSessions );
  const sessionStatus = missionSessionStatus( sessionId, availableMissionSessions, missionMode );
  const missionAttached = sessionId !== null;
  const selectedPlaybackSpeed = playbackSpeed ?? 1;
  const primaryButtonLabel = busy
    ? 'Linking Mission...'
    : missionAttached
      ? 'Mission Linked'
      : 'Start Mission';

  return (
    <aside className="control-rail">
      <section className="console-panel">
        <p className="eyebrow">Simulation Type</p>
        <div className="mode-toggle">
          <button
            type="button"
            className={consoleMode === 'open_loop' ? 'mode-toggle__button mode-toggle__button--active' : 'mode-toggle__button'}
            onClick={() => setConsoleMode( 'open_loop' )}
          >
            Open Loop Run
          </button>
          <button
            type="button"
            className={consoleMode === 'interactive' ? 'mode-toggle__button mode-toggle__button--active' : 'mode-toggle__button'}
            onClick={() => setConsoleMode( 'interactive' )}
          >
            Dispatch Operator Control
          </button>
        </div>
        <p className="panel-note">
          This console follows the active Cameo-driven mission session. Start Mission links the browser to the newest live session exposed through the bridge.
        </p>
        <div className="button-stack">
          <button
            type="button"
            className={missionAttached ? 'primary-button primary-button--linked' : 'primary-button'}
            onClick={() => void startMission()}
            disabled={busy}
          >
            {primaryButtonLabel}
          </button>
          <button type="button" className="secondary-button" onClick={() => void refreshBridgeLink()} disabled={busy}>
            Rescan Cameo Session
          </button>
        </div>
      </section>

      <section className="console-panel">
        <p className="eyebrow">Playback Speed</p>
        <div className="speed-toggle">
          {PLAYBACK_SPEED_OPTIONS.map( ( option ) => (
            <button
              key={option}
              type="button"
              className={selectedPlaybackSpeed === option ? 'speed-toggle__button speed-toggle__button--active' : 'speed-toggle__button'}
              onClick={() => void setPlaybackSpeed( option )}
              disabled={busy || sessionId === null}
            >
              {option}x
            </button>
          ) )}
        </div>
      </section>

      {consoleMode === 'interactive' ? (
        <section className="console-panel">
          <p className="eyebrow">Operator Controls</p>
          <div className="button-grid">
            {INTERACTIVE_BUTTONS.map( ( button ) => (
              <button
                key={`${button.kind}:${button.label}`}
                type="button"
                className="secondary-button"
                onClick={() => {
                  if ( button.kind === 'command' ) {
                    void issueInteractiveCommand( button.action as InteractiveCommandKind );
                    return;
                  }
                  void applyInteractivePerturbation( button.action as InteractivePerturbationKind, button.options );
                }}
                disabled={busy || sessionId === null}
              >
                {button.label}
              </button>
            ) )}
          </div>
        </section>
      ) : null}

      <section className="console-panel">
        <p className="eyebrow">Mission Link</p>
        <div className="status-stack">
          <StatusLine label="Bridge API" value={healthText} />
          <StatusLine label="Mission Session" value={activeMissionSession} />
          <StatusLine label="Playback Status" value={sessionStatus} />
          <StatusLine label="Simulation Type" value={consoleMode === 'open_loop' ? 'Open Loop Run' : 'Dispatch Operator Control'} />
          <StatusLine label="Active Route" value={activeRouteKind ?? 'n/a'} />
          <StatusLine label="Last Event" value={lastEvent ?? 'n/a'} />
          <StatusLine label="Pending Command" value={bridgeState?.pending_command_kind ?? 'none'} />
        </div>
        {errorText ? <p className="error-banner">{errorText}</p> : null}
      </section>
    </aside>
  );
}


export function WorkspacePanel( { children, scene }: WorkspacePanelProps ) {
  return (
    <main className="workspace-column">
      <section className="workspace-panel">
        <div className="workspace-panel__header">
          <div>
            <p className="eyebrow">Mission Workspace</p>
            <h2>{sceneTitle( scene )}</h2>
          </div>
        </div>
        {children}
      </section>
    </main>
  );
}


export function TelemetryRail( {
  collapsed,
  history,
  missionState,
  onToggleCollapsed,
  renderState,
  sessionStatus,
}: TelemetryRailProps ) {
  const rawMissionMode = missionState?.mission_mode ?? null;
  const missionMode = displayMissionMode( rawMissionMode );
  const displayedSpeedMps = missionState?.current_speed_mps ?? renderState?.vehicle.speed_mps ?? null;
  const spotlightState = renderState?.vehicle.spotlight_on ?? false;
  const speakerState = renderState?.vehicle.speaker_on ?? false;
  const metricCards: MetricCardProps[] = [
    { label: 'Mission Mode', value: missionMode, tone: toneForMissionMode( rawMissionMode ) },
    { label: 'Mission Time', value: numericText( missionState?.mission_time_s ?? null, 1, ' s' ) },
    { label: 'Playback', value: playbackModeText( missionState ), tone: missionState?.real_time === true ? 'good' : 'neutral' },
    { label: 'Playback Speed', value: numericText( missionState?.playback_speed ?? null, 1, 'x' ) },
    { label: 'Simulation Rate', value: numericText( missionState?.simulation_rate_hz ?? null, 1, ' Hz' ) },
    { label: 'Speed', value: numericText( displayedSpeedMps, 1, ' m/s' ) },
    { label: 'Propulsion Power', value: numericText( missionState?.current_propulsion_power_w ?? null, 1, ' W' ) },
    { label: 'Total Power', value: numericText( missionState?.current_total_power_w ?? null, 1, ' W' ) },
    { label: 'Payload Load', value: numericText( missionState?.current_load_w ?? null, 1, ' W' ) },
    { label: 'Spotlight', value: spotlightState ? 'ON' : 'OFF', tone: spotlightState ? 'good' : 'neutral' },
    { label: 'Speaker', value: speakerState ? 'ON' : 'OFF', tone: speakerState ? 'warn' : 'neutral' },
    { label: 'To Perimeter', value: numericText( missionState?.distance_to_perimeter_m ?? null, 1, ' m' ) },
    { label: 'Patrol Remaining', value: numericText( missionState?.patrol_distance_remaining_m ?? null, 1, ' m' ) },
    { label: 'Track Timer', value: numericText( missionState?.track_time_remaining_s ?? null, 1, ' s' ) },
    { label: 'Tier 1 Timer', value: numericText( missionState?.tier1_engagement_time_remaining_s ?? null, 1, ' s' ) },
    { label: 'Mission Status', value: sessionStatus, tone: sessionStatus === 'Complete' ? 'good' : 'neutral' },
  ];
  const visibleMetricCards = metricCards.filter( ( card ) => card.value !== 'n/a' );

  return (
    <aside className="detail-rail" data-collapsed={collapsed ? 'true' : 'false'}>
      <div className="detail-rail__toggle-row">
        <button
          type="button"
          className="detail-rail__toggle"
          aria-label={collapsed ? 'Show telemetry rail' : 'Hide telemetry rail'}
          onClick={onToggleCollapsed}
        >
          <TelemetryChevronIcon collapsed={collapsed} />
        </button>
      </div>

      {!collapsed ? (
        <div className="detail-rail__body">
          <section className="console-panel">
            <p className="eyebrow">Mission Telemetry</p>
            <div className="metric-grid">
              {visibleMetricCards.map( ( card ) => (
                <MetricCard key={card.label} label={card.label} tone={card.tone} value={card.value} />
              ) )}
            </div>
          </section>

          <section className="console-panel">
            <p className="eyebrow">Live Mission Trends</p>
            <div className="trend-stack">
              <TrendPlot
                accentClassName="trend-card--energy"
                currentValue={numericText( missionState?.remaining_energy_j ?? null, 0, ' J' )}
                forceZeroMin
                label="Remaining Energy"
                samples={history}
                valueAccessor={( sample ) => sample.remainingEnergyJ}
              />
            </div>
          </section>
        </div>
      ) : null}
    </aside>
  );
}
