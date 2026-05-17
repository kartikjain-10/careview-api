from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from langchain_groq import ChatGroq

from app.ai.chains.whatsapp_chain import build_whatsapp_chain, build_whatsapp_link
from app.ai.utils import format_wearable_summary
from app.core.config import Settings
from app.core.dependencies import get_llm, get_settings
from app.db.database import get_db
from app.db.repository import WearableRepository
from app.models.schemas import WhatsAppGenerateRequest, WhatsAppGenerateResponse

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("/generate-update", response_model=WhatsAppGenerateResponse)
async def generate_whatsapp_update(
    body: WhatsAppGenerateRequest,
    settings: Settings = Depends(get_settings),
    llm: ChatGroq = Depends(get_llm),
) -> WhatsAppGenerateResponse:
    async with get_db(settings) as db:
        repo = WearableRepository(db)
        snapshots = await repo.get_snapshots_by_parent(body.parent_id, days=7)

    wearable_summary = format_wearable_summary(snapshots)

    try:
        chain = build_whatsapp_chain(llm)
        message = chain(language=body.language, wearable_summary=wearable_summary)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Message generation failed: {exc}"
        ) from exc

    whatsapp_link = build_whatsapp_link(body.phone_number, message)

    return WhatsAppGenerateResponse(
        message=message,
        whatsapp_link=whatsapp_link,
        language=body.language,
    )
