"""FastAPI application entrypoint (PRD component #13/backend). Run locally with:
    uvicorn backend.app.main:app --reload
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import experiments, failures, health, metrics, workers
from backend.app.database.session import get_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(get_engine())
    yield


app = FastAPI(title="PulseX Backend", version="0.1.0", lifespan=lifespan)

# Local research tool: dashboard runs on a different dev-server port than the API, so
# CORS must be opened for it. Restrict to explicit origins (never "*") since credentials
# aren't used here but this keeps the door closed to arbitrary sites either way.
_allowed_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(experiments.router)
app.include_router(workers.router)
app.include_router(metrics.router)
app.include_router(failures.router)
