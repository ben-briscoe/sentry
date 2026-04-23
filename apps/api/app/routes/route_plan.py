from fastapi import APIRouter

from app.schemas import RoutePlanRequest, RoutePlanResponse
from app.services.mission_routes import plan_route_request


router = APIRouter( prefix="/api/route", tags=["route"] )


@router.post( "/plan", response_model=RoutePlanResponse )
def plan_route( request: RoutePlanRequest ) -> RoutePlanResponse:
    return plan_route_request( request )
