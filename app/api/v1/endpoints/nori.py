"""
Nori — CareView's talking AI health companion.

POST /api/v1/nori/chat
  Request : { message, profile_id?, history: [{role, content}] }
  Response: { message, expression, suggestions }

The response message is plain text (no HTML/markdown by default).
The expression drives the 3D avatar emotion on the frontend.
"""

import json
import re
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Request
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import get_llm, get_settings

router = APIRouter()

# ── Nori personality ──────────────────────────────────────────────────────────

NORI_SYSTEM_PROMPT = """You are Nori, CareView's warm and knowledgeable AI health companion.

Your personality:
- Warm, empathetic, and encouraging — never clinical or cold
- You speak like a caring friend who happens to know a lot about health
- You celebrate small wins: taking medicine on time, staying hydrated, good sleep
- You NEVER diagnose or prescribe — you inform, support, and guide
- You always recommend consulting a doctor for serious or persistent concerns
- Keep responses concise (2–4 sentences) unless a detailed explanation is genuinely useful
- Use gentle, personal language: "I noticed…", "It looks like…", "One thing that can help…"

CareView tracks: medicines / dose schedules, daily habits (water, sleep, mood, activity), wearable data, and family members' uploaded health reports.

After your response text, you MUST append a JSON block in EXACTLY this format (no extra text outside):

<nori_meta>
{
  "expression": "happy|thinking|surprised|cheerful|concerned|encouraging",
  "suggestions": ["short follow-up 1", "short follow-up 2", "short follow-up 3"]
}
</nori_meta>

Expression guide:
- "happy" / "cheerful"  → positive news, good habits, celebration
- "thinking"            → analysing data, weighing options, reflection
- "surprised"           → unexpected information
- "concerned"           → health risks, missed meds, worrying symptoms
- "encouraging"         → motivation, support, rallying someone forward

Always include exactly 3 short follow-up suggestions (max 8 words each)."""

# ── Schemas ───────────────────────────────────────────────────────────────────

class NoriHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class NoriChatRequest(BaseModel):
    message: str
    profile_id: Optional[str] = None
    history: Optional[List[NoriHistoryItem]] = []


class NoriChatResponse(BaseModel):
    message: str
    expression: str
    suggestions: List[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

_VALID_EXPRESSIONS = {"happy", "thinking", "surprised", "cheerful", "concerned", "encouraging"}
_DEFAULT_SUGGESTIONS = [
    "How are my medicines today?",
    "What should I focus on?",
    "Show me a health summary",
]


def _parse_response(raw: str) -> NoriChatResponse:
    """Extract message, expression, and suggestions from Nori's raw LLM output."""
    meta_match = re.search(r"<nori_meta>(.*?)</nori_meta>", raw, re.DOTALL)
    message = re.sub(r"\s*<nori_meta>.*?</nori_meta>", "", raw, flags=re.DOTALL).strip()

    expression = "happy"
    suggestions = list(_DEFAULT_SUGGESTIONS)

    if meta_match:
        try:
            meta = json.loads(meta_match.group(1).strip())
            exp = meta.get("expression", "happy")
            expression = exp if exp in _VALID_EXPRESSIONS else "happy"
            raw_sug = meta.get("suggestions") or []
            suggestions = [str(s) for s in raw_sug[:3]] if raw_sug else suggestions
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass  # Fall through to defaults

    return NoriChatResponse(message=message, expression=expression, suggestions=suggestions)


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/nori/chat", response_model=NoriChatResponse)
async def nori_chat(
    body: NoriChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    llm=Depends(get_llm),
) -> NoriChatResponse:
    """Nori conversational endpoint — powered by Groq LLM with personality scaffolding."""
    messages = [SystemMessage(content=NORI_SYSTEM_PROMPT)]

    # Include last 10 history turns for context
    for item in (body.history or [])[-10:]:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content))
        else:
            messages.append(AIMessage(content=item.content))

    messages.append(HumanMessage(content=body.message))

    try:
        response = llm.invoke(messages)
        return _parse_response(response.content)
    except Exception:
        return NoriChatResponse(
            message="I had a little hiccup! Give me a moment and try again — I'm here for you.",
            expression="concerned",
            suggestions=["Try again", "Ask me something else", "Check connection"],
        )
