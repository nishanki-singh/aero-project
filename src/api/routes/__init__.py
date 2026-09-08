"""FastAPI route modules for AERO."""

from src.api.routes.chat import router as chat_router
from src.api.routes.diagnostic import router as diagnostic_router
from src.api.routes.evaluation import router as evaluation_router
from src.api.routes.health import router as health_router
from src.api.routes.postmortem import router as postmortem_router
from src.api.routes.risk import router as risk_router
from src.api.routes.scenarios import router as scenarios_router
from src.api.routes.timeline import router as timeline_router

__all__ = [
    "chat_router",
    "diagnostic_router",
    "evaluation_router",
    "health_router",
    "postmortem_router",
    "risk_router",
    "scenarios_router",
    "timeline_router",
]
