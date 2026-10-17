"""Routing endpoint — the backend side of the frontend's `fetchRouteOptions`."""
from fastapi import APIRouter

from ..models import RouteOption, RouteRequest
from ..routing.engine import RouteEngine
from ..routing.stub_engine import StubRouteEngine

router = APIRouter(prefix="/api", tags=["routes"])

# Single engine instance. Swap `StubRouteEngine` for `CppRouteEngine` later;
# the rest of the app does not change.
engine: RouteEngine = StubRouteEngine()


@router.post("/routes", response_model=list[RouteOption])
def get_routes(req: RouteRequest) -> list[RouteOption]:
    return engine.query_routes(req.from_, req.to, req.profile)
