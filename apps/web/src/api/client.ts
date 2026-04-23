import type {
  ApiHealth,
  InitializeResponse,
  MissionBridgeAckRequest,
  MissionBridgeAckResponse,
  MissionCommandRequest,
  MissionCommandResponse,
  MissionPerturbationRequest,
  MissionPerturbationResponse,
  MissionServiceCreateRequest,
  MissionServiceSnapshot,
  MissionServiceSessionSummary,
  MissionServiceSessionView,
  MissionSyncResponse,
  ModeledMissionSnapshot,
  ReplayTraceDescriptor,
  RoutePlanRequest,
  RoutePlanResponse,
  SessionCreated,
  StepResponse,
} from '../types';


const defaultApiBaseUrl = 'http://127.0.0.1:8000';


export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor( status: number, message: string, detail?: unknown ) {
    super( message );
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}


function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? defaultApiBaseUrl;
}


async function readJson<T>( response: Response, path: string ): Promise<T> {
  if ( !response.ok ) {
    const text = await response.text();
    let detail: unknown = text;
    let message = `Request failed (${response.status}) for ${path}`;
    try {
      const parsed = JSON.parse( text ) as { detail?: unknown; message?: string };
      detail = parsed.detail ?? parsed;
      if ( typeof parsed.message === 'string' ) {
        message = parsed.message;
      } else if (
        typeof detail === 'object'
        && detail !== null
        && 'detail' in detail
        && typeof ( detail as { detail?: unknown } ).detail === 'string'
      ) {
        message = String( ( detail as { detail: string } ).detail );
      }
    } catch {
      if ( text.trim().length > 0 ) {
        message = text;
      }
    }
    throw new ApiError( response.status, message, detail );
  }
  return response.json() as Promise<T>;
}


async function getJson<T>( path: string ): Promise<T> {
  const response = await fetch( `${apiBaseUrl()}${path}` );
  return readJson<T>( response, path );
}


async function postJson<T>( path: string, body?: unknown ): Promise<T> {
  const response = await fetch( `${apiBaseUrl()}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify( body ),
  } );
  return readJson<T>( response, path );
}


async function deleteJson<T>( path: string ): Promise<T> {
  const response = await fetch( `${apiBaseUrl()}${path}`, {
    method: 'DELETE',
  } );
  if ( response.status === 204 ) {
    return undefined as T;
  }
  return readJson<T>( response, path );
}


export function getHealth(): Promise<ApiHealth> {
  return getJson<ApiHealth>( '/api/health' );
}


export function listReplayTraces(): Promise<ReplayTraceDescriptor[]> {
  return getJson<ReplayTraceDescriptor[]>( '/api/replays/traces' );
}


export function createReplaySession( traceCsv: string ): Promise<SessionCreated> {
  return postJson<SessionCreated>( '/api/simulation/session', {
    mode: 'replay',
    trace_csv: traceCsv,
    scene_profile: 'reference_mission_v1',
  } );
}


export function initializeSession( sessionId: string ): Promise<InitializeResponse> {
  return postJson<InitializeResponse>( `/api/simulation/${sessionId}/initialize` );
}


export function stepSession( sessionId: string, stepCount = 1 ): Promise<StepResponse> {
  return postJson<StepResponse>( `/api/simulation/${sessionId}/step`, {
    step_count: stepCount,
  } );
}


export function terminateSession( sessionId: string ): Promise<{ session_id: string; terminated: boolean }> {
  return postJson<{ session_id: string; terminated: boolean }>( `/api/simulation/${sessionId}/terminate` );
}


export function planRoute( request: RoutePlanRequest ): Promise<RoutePlanResponse> {
  return postJson<RoutePlanResponse>( '/api/route/plan', request );
}


export function createMissionServiceSession(
  request: MissionServiceCreateRequest = {},
): Promise<MissionServiceSnapshot> {
  return postJson<MissionServiceSnapshot>( '/api/mission/session', request );
}


export function getMissionServiceSession( sessionId: string ): Promise<MissionServiceSnapshot> {
  return getJson<MissionServiceSnapshot>( `/api/mission/${sessionId}` );
}


export function listMissionServiceSessions(): Promise<MissionServiceSessionSummary[]> {
  return getJson<MissionServiceSessionSummary[]>( '/api/mission' );
}


export function getMissionServiceSessionView( sessionId: string ): Promise<MissionServiceSessionView> {
  return getJson<MissionServiceSessionView>( `/api/mission/${sessionId}/view` );
}


export function getMissionBridgeView( sessionId: string ): Promise<MissionServiceSessionView> {
  return getJson<MissionServiceSessionView>( `/api/mission/${sessionId}/bridge` );
}


export function syncMissionServiceSession(
  sessionId: string,
  modeledState: ModeledMissionSnapshot,
): Promise<MissionSyncResponse> {
  return postJson<MissionSyncResponse>( `/api/mission/${sessionId}/sync`, {
    modeled_state: modeledState,
  } );
}


export function sendMissionCommand(
  sessionId: string,
  request: MissionCommandRequest,
): Promise<MissionCommandResponse> {
  return postJson<MissionCommandResponse>( `/api/mission/${sessionId}/command`, request );
}


export function applyMissionPerturbation(
  sessionId: string,
  request: MissionPerturbationRequest,
): Promise<MissionPerturbationResponse> {
  return postJson<MissionPerturbationResponse>( `/api/mission/${sessionId}/perturbation`, request );
}


export function acknowledgeMissionBridge(
  sessionId: string,
  request: MissionBridgeAckRequest,
): Promise<MissionBridgeAckResponse> {
  return postJson<MissionBridgeAckResponse>( `/api/mission/${sessionId}/bridge/ack`, request );
}


export function deleteMissionServiceSession( sessionId: string ): Promise<void> {
  return deleteJson<void>( `/api/mission/${sessionId}` );
}
