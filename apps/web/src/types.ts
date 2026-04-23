export type Coordinate = {
  lon: number;
  lat: number;
  alt_m: number;
};

export type RenderBoxDimensions = {
  length_m: number;
  width_m: number;
  height_m: number;
};

export type RenderStructure = {
  id: string;
  kind: 'building' | 'barrier' | 'tower';
  label: string;
  center: Coordinate;
  dimensions_m: RenderBoxDimensions;
  heading_deg: number;
  color: string | null;
};

export type RenderScene = {
  id: string;
  description: string;
  base: Coordinate;
  patrol_area: Coordinate[];
  patrol_route: Coordinate[];
  incursion_route: Coordinate[];
  structures: RenderStructure[];
};

export type RenderEntityState = {
  label: string;
  position: Coordinate;
  speed_mps: number | null;
  spotlight_on: boolean;
  speaker_on: boolean;
};

export type RenderIncursionState = {
  label: string;
  position: Coordinate | null;
  active: boolean;
  radius_m: number;
};

export type RenderState = {
  vehicle: RenderEntityState;
  incursion: RenderIncursionState;
};

export type RoutePlanRequest = {
  kind: 'patrol_loop' | 'recall' | 'intercept' | 'track';
  start?: Coordinate | null;
  end?: Coordinate | null;
  patrol_area?: Coordinate[];
  target_route?: Coordinate[];
  ownship_speed_mps?: number;
  target_speed_mps?: number;
  patrol_inset_ratio?: number;
  route_offset_m?: number;
};

export type RoutePlanResponse = {
  kind: string;
  waypoints: Coordinate[];
  note: string;
  estimated_distance_m: number | null;
  estimated_duration_s: number | null;
  intercept_point: Coordinate | null;
};

export type MissionState = {
  session_id: string;
  step_index: number;
  time_ms: number | null;
  mission_mode: string | null;
  mission_time_s: number | null;
  real_time: boolean | null;
  playback_speed: number | null;
  simulation_rate_hz: number | null;
  current_speed_mps: number | null;
  current_propulsion_power_w: number | null;
  current_total_power_w: number | null;
  current_load_w: number | null;
  remaining_energy_j: number | null;
  distance_to_base_m: number | null;
  distance_to_perimeter_m: number | null;
  patrol_distance_remaining_m: number | null;
  track_time_remaining_s: number | null;
  tier1_engagement_time_remaining_s: number | null;
  attributes: Record<string, unknown>;
};

export type ModeledMissionSnapshot = {
  time_ms?: number | null;
  mission_mode?: string | null;
  mission_time_s?: number | null;
  real_time?: boolean | null;
  playback_speed?: number | null;
  simulation_rate_hz?: number | null;
  current_speed_mps?: number | null;
  current_propulsion_power_w?: number | null;
  current_total_power_w?: number | null;
  current_load_w?: number | null;
  remaining_energy_j?: number | null;
  distance_to_base_m?: number | null;
  distance_to_perimeter_m?: number | null;
  patrol_distance_remaining_m?: number | null;
  track_time_remaining_s?: number | null;
  tier1_engagement_time_remaining_s?: number | null;
  flight_feasible?: boolean | null;
  endurance_feasible?: boolean | null;
  configuration_suitable?: boolean | null;
  low_battery_triggered?: boolean | null;
  returned_early?: boolean | null;
  mission_complete?: boolean | null;
  attributes?: Record<string, unknown>;
};

export type SessionCreated = {
  session_id: string;
  mode: string;
  trace_csv: string;
  scene_profile: string;
};

export type ReplayTraceDescriptor = {
  name: string;
  path: string;
  rows_hint: number | null;
  terminal_mode: string | null;
  duration_ms: number | null;
  recommended: boolean;
};

export type InitializeResponse = {
  session_id: string;
  mode: string;
  trace_csv: string;
  scene: RenderScene;
  render_state: RenderState;
  total_steps: number;
  state: MissionState;
};

export type StepResponse = {
  session_id: string;
  total_steps: number;
  render_state: RenderState;
  state: MissionState;
  done: boolean;
};

export type ApiHealth = {
  status: string;
};

export type MissionServiceSnapshot = {
  session_id: string;
  scene: RenderScene;
  sentry_position: Coordinate;
  sentry_speed_mps: number;
  active_route_kind: string | null;
  active_route: Coordinate[];
  patrol_assigned: boolean;
  recall_active: boolean;
  escalation_authorized: boolean;
  incursion_active: boolean;
  incursion_position: Coordinate | null;
  incursion_route: Coordinate[];
  incursion_speed_mps: number;
  last_event: string | null;
  notes: string[];
};

export type MissionServiceSessionSummary = {
  session_id: string;
  mission_mode: string | null;
  mission_complete: boolean | null;
  last_event: string | null;
};

export type MissionBridgeState = {
  pending_command_kind: string | null;
  pending_command_note: string | null;
  pending_real_time: boolean | null;
  pending_playback_speed: number | null;
  command_revision: number;
  command_revision_applied: number;
  route_revision: number;
  route_revision_applied: number;
};

export type MissionServiceSessionView = {
  snapshot: MissionServiceSnapshot;
  modeled_state: ModeledMissionSnapshot | null;
  render_state: RenderState;
  bridge_state: MissionBridgeState;
};

export type MissionBridgeAckRequest = {
  command_revision_applied?: number | null;
  route_revision_applied?: number | null;
  note?: string | null;
};

export type MissionBridgeAckResponse = {
  session_id: string;
  bridge_state: MissionBridgeState;
  note: string;
};

export type MissionServiceCreateRequest = {
  scene_profile?: string;
  base?: Coordinate | null;
  patrol_area?: Coordinate[];
  patrol_route?: Coordinate[];
  incursion_route?: Coordinate[];
  sentry_position?: Coordinate | null;
  sentry_speed_mps?: number;
  incursion_speed_mps?: number;
};

export type MissionCommandRequest = {
  kind: 'assign_patrol' | 'recall' | 'authorize_tier1' | 'clear_recall' | 'resume_patrol' | 'intercept_incursion' | 'set_playback_speed';
  current_position?: Coordinate | null;
  patrol_area?: Coordinate[];
  target_route?: Coordinate[];
  sentry_speed_mps?: number | null;
  playback_speed?: number | null;
  real_time?: boolean | null;
};

export type MissionCommandResponse = {
  session_id: string;
  applied: boolean;
  command: string;
  snapshot: MissionServiceSnapshot;
  route_plan: RoutePlanResponse | null;
  note: string;
};

export type MissionPerturbationRequest = {
  kind: 'incursion_spawn' | 'route_deviation' | 'incursion_speed_change' | 'all_clear';
  route?: Coordinate[];
  offset_m?: number;
  direction?: 'left' | 'right';
  speed_mps?: number | null;
};

export type MissionPerturbationResponse = {
  session_id: string;
  applied: boolean;
  perturbation: string;
  snapshot: MissionServiceSnapshot;
  route_plan: RoutePlanResponse | null;
  note: string;
};

export type MissionSyncResponse = {
  session_id: string;
  modeled_state: ModeledMissionSnapshot;
  snapshot: MissionServiceSnapshot;
  recommended_route: RoutePlanResponse | null;
  suggested_command: string | null;
  note: string;
};

export type ReferenceMetrics = {
  distanceToBaseStartM: number | null;
  distanceToPerimeterStartM: number | null;
  patrolDistanceStartM: number | null;
  trackTimeStartS: number | null;
  tier1EngagementStartS: number | null;
};
