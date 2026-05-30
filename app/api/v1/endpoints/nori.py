"""
Nori — CareView's AI health companion with full family RAG.

POST /api/v1/nori/chat
  Request : { message, profile_id?, history: [{role, content}] }
  Response: { message, expression, suggestions, sources }

Context layers injected automatically:
  1. Family roster (all members in the authenticated group)
  2. Live wearable data (last 7 days per member)
  3. Active medicines per member
  4. Indexed PDF chunks from ChromaDB (semantic search, scoped to family)
"""

from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Request
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app.ai.chains.family_rag import FamilyRAGChain
from app.core.config import Settings
from app.core.dependencies import get_current_group, get_llm, get_settings, get_vectorstore
from app.db import family_repository, medicine_repository
from app.db.database import get_db
from app.db.repository import WearableRepository

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class NoriHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class NoriChatRequest(BaseModel):
    message: str
    profile_id: Optional[str] = None
    history: Optional[List[NoriHistoryItem]] = []


class NoriSource(BaseModel):
    filename: str
    member: str = ""
    date: str = ""
    document_id: str = ""


class NoriChatResponse(BaseModel):
    message: str
    expression: str
    suggestions: List[str]
    sources: List[NoriSource] = []


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/nori/chat", response_model=NoriChatResponse)
async def nori_chat(
    body: NoriChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    llm: ChatGroq = Depends(get_llm),
    vectorstore: Chroma = Depends(get_vectorstore),
    group: dict = Depends(get_current_group),
) -> NoriChatResponse:
    """Nori conversational endpoint with family-aware RAG."""

    async with get_db(settings) as db:
        # 1. All family members
        members: list[dict] = await family_repository.list_members(db, group["id"])

        # 2. Wearable data for each member (last 7 days)
        wearable_repo = WearableRepository(db)
        wearable_map: dict[str, list[dict]] = {}
        for m in members:
            snaps = await wearable_repo.get_snapshots_by_parent(m["id"], days=7)
            wearable_map[m["id"]] = [
                {
                    "date": str(s.date),
                    "steps": s.steps,
                    "sleep_hours": s.sleep_hours,
                    "resting_heart_rate": s.resting_heart_rate,
                    "active_minutes": s.active_minutes,
                    "mood_score": s.mood_score,
                }
                for s in snaps
            ]

        # 3. Medicines for the whole group
        medicines: list[dict] = await medicine_repository.list_medicines(db, group["id"])
        medicine_map: dict[str, list[dict]] = {}
        for med in medicines:
            pid = med.get("profile_id", "")
            medicine_map.setdefault(pid, []).append(med)

    # Build and run the family RAG chain
    chain = FamilyRAGChain(llm, vectorstore)
    history = [{"role": h.role, "content": h.content} for h in (body.history or [])]

    result = chain.run(
        query=body.message,
        members=members,
        wearable_map=wearable_map,
        medicine_map=medicine_map,
        history=history,
        active_member_id=body.profile_id,
        group_id=group["id"],
    )

    return NoriChatResponse(
        message=result.message,
        expression=result.expression,
        suggestions=result.suggestions,
        sources=[
            NoriSource(
                filename=s.get("filename", ""),
                member=s.get("member", ""),
                date=s.get("date", ""),
                document_id=s.get("document_id", ""),
            )
            for s in result.sources
        ],
    )
