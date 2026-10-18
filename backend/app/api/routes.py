"""Routing endpoint — the backend side of the frontend's `fetchRouteOptions`."""
from fastapi import APIRouter, HTTPException
from street_router import RouteError, RouterUnavailable

from ..models import RouteOption, RouteRequest
from ..routing.engine import RouteEngine
from ..routing.factory import make_engine
from ..routing.multi import query_multi
from ..routing.onboard import VehicleNotFound, query_onboard
from ..routing.real_engine import _clock

router = APIRouter(prefix="/api", tags=["routes"])

# ROUTE_ENGINE picks it (default: real timetable + street graph).
engine: RouteEngine = make_engine()


@router.post("/routes", response_model=list[RouteOption])
def get_routes(req: RouteRequest) -> list[RouteOption]:
    try:
        if req.onboard is not None:
            if req.via or req.travel != "transit":
                raise HTTPException(422, "onboard works only for a transit trip without via")
            return query_onboard(engine, req.onboard.vehicleId, req.to, req.profile, _clock(req.when), search=req)
        if req.via:
            return query_multi(engine, req.from_, req.to, req.via, req.order, req.profile, when=req.when, search=req)
        return engine.query_routes(req.from_, req.to, req.profile, when=req.when, search=req)
    except VehicleNotFound as exc:
        raise HTTPException(404, "vehicle not found") from exc
    except RouterUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except RouteError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, f"timetable data is missing: {exc}")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
