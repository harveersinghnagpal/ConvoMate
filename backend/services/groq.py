import asyncio
import json
import logging
from typing import Optional

from groq import Groq

from backend.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

if GROQ_API_KEY and GROQ_API_KEY.strip() and "your_" not in GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception as exc:
        logger.error("Failed to initialize Groq client: %s", exc)
        client = None
else:
    logger.warning("No valid GROQ_API_KEY found. Running in DEMO / fallback mode.")
    client = None

_SYSTEM_PROMPT = """
You are an expert real-time call-center analyst. You receive a live call transcript or partial conversation and must respond with a strict JSON object, with no markdown and no extra text.

Analyze the latest statement and conversation history, then return:
{
  "sentiment": "<one of: Angry | Frustrated | Neutral | Happy>",
  "escalation": "<one of: Yes | No>",
  "suggestion": "<1-2 line coaching tip for the agent>"
}

Rules:
- sentiment: reflect the caller's emotional tone in the latest segment
- escalation: "Yes" if the caller is Angry or Frustrated and repeating complaints or using strong language
- suggestion: be direct and actionable
- respond only with the JSON object
"""


def _fallback_analysis(latest_text: str) -> dict:
    lower_text = latest_text.lower()

    angry_markers = (
        "angry",
        "unacceptable",
        "ridiculous",
        "terrible",
        "frustrated",
        "fed up",
        "cancel",
        "not okay",
        "three times",
        "nobody",
    )
    happy_markers = (
        "thank",
        "thanks",
        "appreciate",
        "great",
        "perfect",
        "resolved",
        "helpful",
    )

    if any(marker in lower_text for marker in angry_markers):
        sentiment = "Angry" if any(
            marker in lower_text for marker in ("angry", "unacceptable", "ridiculous", "terrible", "fed up")
        ) else "Frustrated"
        return {
            "sentiment": sentiment,
            "escalation": "Yes",
            "suggestion": "Acknowledge the frustration clearly, apologize, and offer the fastest concrete next step.",
        }

    if any(marker in lower_text for marker in happy_markers):
        return {
            "sentiment": "Happy",
            "escalation": "No",
            "suggestion": "Confirm the resolution, thank them for their patience, and close the call warmly.",
        }

    return {
        "sentiment": "Neutral",
        "escalation": "No",
        "suggestion": "Continue listening carefully, confirm the issue, and explain the next action clearly.",
    }


async def analyze(latest_text: str, context: str, retries: int = 3) -> Optional[dict]:
    if not latest_text or not latest_text.strip():
        return None

    if not client:
        await asyncio.sleep(1)
        return _fallback_analysis(latest_text)

    prompt = (
        f"Conversation so far: {context}\n\n"
        f"Latest caller statement: \"{latest_text}\"\n\n"
        "Respond with JSON only."
    )

    for attempt in range(1, retries + 1):
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            raw = (response.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            return {
                "sentiment": data.get("sentiment", "Neutral"),
                "escalation": data.get("escalation", "No"),
                "suggestion": data.get("suggestion", "Continue listening carefully."),
            }
        except json.JSONDecodeError as exc:
            logger.warning("Groq returned non-JSON (attempt %d): %s", attempt, exc)
        except Exception as exc:
            logger.warning("Groq API error with model %s (attempt %d): %s", GROQ_MODEL, attempt, exc)
        if attempt < retries:
            await asyncio.sleep(0.5 * attempt)

    return _fallback_analysis(latest_text)
