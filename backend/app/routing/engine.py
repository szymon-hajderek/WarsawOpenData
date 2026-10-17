"""The routing seam.

`RouteEngine` is the single boundary between the FastAPI backend and whatever
actually computes routes. The running implementation is `RealRouteEngine`.
`StubRouteEngine` is the old mock.

## Future: the C++ engine

The plan is a long-running C++ service. On startup it builds its own graph and
keeps that graph in memory. Python does not send the graph. After startup,
Python only pushes live data and values derived from it (vehicle positions,
Veturilo availability, alerts, delays), then asks C++ for routes.

A `CppRouteEngine(RouteEngine)` will therefore:
  - hold a connection to that persistent C++ process (local socket / HTTP / a
    native binding — decided together with the C++ team),
  - implement `update_state(...)` for live updates only, not for rebuilding the graph,
  - implement `query_routes(...)` to delegate the actual routing and map the
    result back into `RouteOption` objects.

The exact wire format (request/response) is owned by the C++ team; only this
interface and the models in `app/models.py` need to stay stable for the
frontend.

## Testing a new engine

`ROUTE_ENGINE` (`app/routing/factory.py`) picks the engine. A new engine MUST pass
the integration suite (`integration/`, synthetic trips on real data) before it
replaces `real`: `ROUTE_ENGINE=<name> uv run pytest ../integration`, then compare
`integration/RESULTS.md` with a run of the current engine.
"""
from abc import ABC, abstractmethod
from typing import Any

from ..models import Place, Profile, RouteOption


class RouteEngine(ABC):
    @abstractmethod
    def query_routes(self, frm: Place, to: Place, profile: Profile, when: str | None = None, search=None) -> list[RouteOption]:
        """Return ranked connection options from `frm` to `to` for `profile`.

        `when` is a Warsaw-local ``HH:MM`` or ISO datetime. Empty means now.
        """

    @abstractmethod
    def update_state(self, update: dict[str, Any]) -> None:
        """Push a live update to the engine.

        The C++ process builds its own graph at startup. This call carries only
        live data and values derived from it (vehicle positions, Veturilo
        availability, alerts, delays). No-op until that process exists.
        """
