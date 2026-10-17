"""Routing endpoint — the backend side of the frontend's `fetchRouteOptions`."""
import logging

from fastapi import APIRouter, HTTPException

from ..models import RouteOption, RouteRequest
from ..routing.engine import RouteEngine
from ..routing.multi import query_multi
from ..routing.real_engine import RealRouteEngine

router = APIRouter(prefix="/api", tags=["routes"])
log = logging.getLogger("uvicorn.error")

# Real timetable + street graph. The stub stays in the repo as the reference for the old mock.
engine: RouteEngine = RealRouteEngine()


@router.post("/routes", response_model=list[RouteOption])
def get_routes(req: RouteRequest) -> list[RouteOption]:
    log.info("route query %s -> %s", req.from_.label, req.to.label)
    try:
        if req.via:
            return query_multi(engine, req.from_, req.to, req.via, req.order, req.profile, when=req.when)
        return engine.query_routes(req.from_, req.to, req.profile, when=req.when)
    except FileNotFoundError as exc:
        raise HTTPException(503, f"timetable data is missing: {exc}")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
