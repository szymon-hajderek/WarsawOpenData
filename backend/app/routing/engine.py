"""The routing seam.

`RouteEngine` is the single boundary between the FastAPI backend and whatever
actually computes routes. Today the only implementation is `StubRouteEngine`
(see `stub_engine.py`), which ports the frontend mock so the app feels alive.

## Future: the C++ engine

The plan is a long-running C++ service that keeps the whole graph and live
state (e.g. where each line's next vehicle is) in memory, so re-loading is
cheap. Python stays a thin backend: it periodically fetches external APIs and
pushes updates into C++, then asks it for routes.

A `CppRouteEngine(RouteEngine)` will therefore:
  - hold a connection to that persistent C++ process (local socket / HTTP / a
    native binding — decided together with the C++ team),
  - implement `update_state(...)` to push graph/state updates,
  - implement `query_routes(...)` to delegate the actual routing and map the
    result back into `RouteOption` objects.

The exact wire format (request/response) is owned by the C++ team; only this
interface and the models in `app/models.py` need to stay stable for the
frontend.
"""
from abc import ABC, abstractmethod
from typing import Any

from ..models import Place, Profile, RouteOption


class RouteEngine(ABC):
    @abstractmethod
    def query_routes(self, frm: Place, to: Place, profile: Profile) -> list[RouteOption]:
        """Return ranked connection options from `frm` to `to` for `profile`."""

    @abstractmethod
    def update_state(self, update: dict[str, Any]) -> None:
        """Push a graph/state update to the engine.

        No-op for the stub; the C++ engine will use this to stay current with
        live data (vehicle positions, Veturilo availability, closures, ...).
        """
