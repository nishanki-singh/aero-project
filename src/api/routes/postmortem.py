"""Automated Google SRE postmortem authoring routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import PostmortemRequest, PostmortemResponse
from src.api.service import AeroService

router = APIRouter(prefix="/api/postmortem", tags=["Postmortem & Documentation"])


@router.post("", response_model=PostmortemResponse, summary="Author publication-ready Google SRE postmortem")
def generate_postmortem(req: PostmortemRequest) -> PostmortemResponse:
    """Generates structured postmortem JSON and publication-ready Markdown report."""
    return AeroService.generate_postmortem(
        incident=req.incident,
        diagnostic_report=req.diagnostic_report,
        provider=req.provider,
    )
