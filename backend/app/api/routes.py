"""Routing endpoint — the backend side of the frontend's `fetchRouteOptions`."""
from fastapi import APIRouter, HTTPException

from ..models import RouteOption, RouteRequest
from ..routing.engine import RouteEngine
from ..routing.factory import make_engine
from ..routing.multi import query_multi

router = APIRouter(prefix="/api", tags=["routes"])

# ROUTE_ENGINE picks it (default: real timetable + street graph). The stub is the old mock.
engine: RouteEngine = make_engine()


@router.post("/routes", response_model=list[RouteOption])
def get_routes(req: RouteRequest) -> list[RouteOption]:
    try:
        if req.via:
            return query_multi(engine, req.from_, req.to, req.via, req.order, req.profile, when=req.when, search=req)
        return engine.query_routes(req.from_, req.to, req.profile, when=req.when, search=req)
    except FileNotFoundError as exc:
        raise HTTPException(503, f"timetable data is missing: {exc}")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
