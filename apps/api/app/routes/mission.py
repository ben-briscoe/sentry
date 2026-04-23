from __future__ import annotations

from fastapi import APIRouter, Body, Response, status

from app.schemas import (
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
    MissionSyncRequest,
    MissionSyncResponse,
)
from app.services.mission_control import store


router = APIRouter( prefix="/api/mission", tags=["mission"] )


@router.post( "/session", response_model=MissionServiceSnapshot )
def create_mission_session(
    request: MissionServiceCreateRequest = Body(default_factory=MissionServiceCreateRequest),
) -> MissionServiceSnapshot:
    return store.create( request )


@router.get( "", response_model=list[ MissionServiceSessionSummary ] )
def list_mission_sessions() -> list[ MissionServiceSessionSummary ]:
    return store.list()


@router.get( "/{session_id}", response_model=MissionServiceSnapshot )
def get_mission_session( session_id: str ) -> MissionServiceSnapshot:
    return store.get( session_id ).snapshot()


@router.get( "/{session_id}/view", response_model=MissionServiceSessionView )
def get_mission_session_view( session_id: str ) -> MissionServiceSessionView:
    return store.get( session_id ).view()


@router.get( "/{session_id}/bridge", response_model=MissionServiceSessionView )
def get_mission_bridge_view( session_id: str ) -> MissionServiceSessionView:
    return store.get( session_id ).view()


@router.post( "/{session_id}/command", response_model=MissionCommandResponse )
def apply_command( session_id: str, request: MissionCommandRequest ) -> MissionCommandResponse:
    return store.get( session_id ).apply_command( request )


@router.post( "/{session_id}/perturbation", response_model=MissionPerturbationResponse )
def apply_perturbation( session_id: str, request: MissionPerturbationRequest ) -> MissionPerturbationResponse:
    return store.get( session_id ).apply_perturbation( request )


@router.post( "/{session_id}/sync", response_model=MissionSyncResponse )
def sync_modeled_state( session_id: str, request: MissionSyncRequest ) -> MissionSyncResponse:
    return store.get( session_id ).sync_modeled_state( request )


@router.post( "/{session_id}/bridge/ack", response_model=MissionBridgeAckResponse )
def acknowledge_bridge_updates( session_id: str, request: MissionBridgeAckRequest ) -> MissionBridgeAckResponse:
    return store.get( session_id ).acknowledge_bridge_updates( request )


@router.delete( "/{session_id}", status_code=status.HTTP_204_NO_CONTENT )
def delete_mission_session( session_id: str ) -> Response:
    store.terminate( session_id )
    return Response( status_code=status.HTTP_204_NO_CONTENT )
