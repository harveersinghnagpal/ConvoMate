"""
analyze.py — POST /analyze: fallback / demo endpoint for direct text analysis.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import groq
from backend.services.context import ContextBuffer

logger = logging.getLogger(__name__)
router = APIRouter()

# Isolated buffer for REST calls (doesn't share state with live stream)
_rest_buffer = ContextBuffer(maxlen=6)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Customer message to analyze")
    reset_context: bool = Field(False, description="Clear context buffer before analysis")


class AnalyzeResponse(BaseModel):
    transcript: str
    sentiment: str
    escalation: str
    suggestion: str


@router.post("/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
async def analyze_text(body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze a piece of caller text and return sentiment, escalation, and agent suggestion.
    Useful for testing / demo mode without a live Twilio call.
    """
    if body.reset_context:
        _rest_buffer.clear()

    _rest_buffer.add_final(body.text)
    context = _rest_buffer.get_context()

    result = await groq.analyze(body.text, context)
    if result is None:
        raise HTTPException(status_code=503, detail="LLM service temporarily unavailable")

    return AnalyzeResponse(
        transcript=body.text,
        sentiment=result["sentiment"],
        escalation=result["escalation"],
        suggestion=result["suggestion"],
    )
