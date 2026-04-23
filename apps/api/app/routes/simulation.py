from fastapi import APIRouter

from app.schemas import (
    CreateSessionRequest,
    InitializeResponse,
    SessionCreated,
    StepRequest,
    StepResponse,
    TerminateResponse,
)
from app.services.replay_sessions import store


router = APIRouter( prefix="/api/simulation", tags=["simulation"] )


@router.post( "/session", response_model=SessionCreated )
def create_session( request: CreateSessionRequest ) -> SessionCreated:
    return store.create_session( trace_csv=request.trace_csv, mode=request.mode )


@router.post( "/{session_id}/initialize", response_model=InitializeResponse )
def initialize_session( session_id: str ) -> InitializeResponse:
    session = store.get( session_id )
    return InitializeResponse(
        session_id=session.session_id,
        mode=session.mode,
        trace_csv=session.trace_csv,
        scene=session.scene,
        render_state=session.current_render_state(),
        total_steps=session.total_steps,
        state=session.current_state(),
    )


@router.post( "/{session_id}/step", response_model=StepResponse )
def step_session( session_id: str, request: StepRequest ) -> StepResponse:
    session = store.get( session_id )
    state = session.advance( request.step_count )
    return StepResponse(
        session_id=session.session_id,
        total_steps=session.total_steps,
        render_state=session.current_render_state(),
        state=state,
        done=session.current_index >= session.total_steps - 1,
    )


@router.post( "/{session_id}/terminate", response_model=TerminateResponse )
def terminate_session( session_id: str ) -> TerminateResponse:
    terminated = store.terminate( session_id )
    return TerminateResponse( session_id=session_id, terminated=terminated )
