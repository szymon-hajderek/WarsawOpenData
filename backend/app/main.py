"""FastAPI application entry point.

Run (from `backend/`):  uvicorn app.main:app --reload
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import journey_stats
from .api import geocode, history, journeys, routes
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(journey_stats.initialize)
    yield


app = FastAPI(title="WarsawOpenData API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(geocode.router)
app.include_router(history.router)
app.include_router(journeys.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
