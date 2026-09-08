"""FastAPI application factory and middleware configuration for AERO."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import (
    chat_router,
    diagnostic_router,
    evaluation_router,
    health_router,
    postmortem_router,
    risk_router,
    scenarios_router,
    timeline_router,
    topology_router,
)
from src.config import config

logger = logging.getLogger("aero.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events."""
    logger.info(
        f"AERO API initialized (Environment: {config.environment}, "
        f"Project: {config.project_id}, Region: {config.region})"
    )
    yield
    logger.info("AERO API shutting down.")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title="AERO - AI-Enabled Reliability & Operations API",
        description="RESTful SRE Copilot API for incident correlation, AI diagnosis, timeline synthesis, and automated postmortem authoring.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for local development and Phase 4 SRE Copilot UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Route Handlers
    app.include_router(health_router)
    app.include_router(scenarios_router)
    app.include_router(diagnostic_router)
    app.include_router(timeline_router)
    app.include_router(postmortem_router)
    app.include_router(evaluation_router)
    app.include_router(chat_router)
    app.include_router(risk_router)
    app.include_router(topology_router)


    # Mount static assets for SRE Command Center UI (Stage 4A)
    web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
    if os.path.exists(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app


app = create_app()

