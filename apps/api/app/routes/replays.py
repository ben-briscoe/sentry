from fastapi import APIRouter, Query

from app.schemas import ReplayTraceDescriptor
from app.services.replay_sessions import list_trace_candidates


router = APIRouter( prefix="/api/replays", tags=["replays"] )


@router.get( "/traces", response_model=list[ ReplayTraceDescriptor ] )
def list_replay_traces( root: str | None = Query( default=None ) ) -> list[ ReplayTraceDescriptor ]:
    return list_trace_candidates( root=root )
