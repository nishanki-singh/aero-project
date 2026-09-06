"""SRE Copilot interactive chat routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.service import AeroService
from src.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["SRE Copilot"])


@router.post("", response_model=ChatResponse, summary="Send question to Grounded SRE Copilot")
def chat_with_copilot(request: ChatRequest) -> ChatResponse:
    """Answers an SRE question grounded strictly in the active incident telemetry."""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        return AeroService.chat(
            scenario_key=request.scenario_key,
            message=request.message.strip(),
            provider=request.provider,
            seed=request.seed,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Copilot inference failed: {e!s}")
