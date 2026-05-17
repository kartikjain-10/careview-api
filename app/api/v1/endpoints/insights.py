from fastapi import APIRouter, Depends, HTTPException
from langchain_groq import ChatGroq
from langchain_chroma import Chroma

from app.core.config import Settings
from app.core.dependencies import get_llm, get_settings, get_vectorstore
from app.ai.chains.insight_chain import build_insight_chain
from app.ai.utils import format_wearable_summary
from app.db.database import get_db
from app.db.repository import WearableRepository
from app.models.schemas import InsightRequest, InsightResponse

router = APIRouter()


@router.post("/insights", response_model=InsightResponse)
async def generate_insight(
    body: InsightRequest,
    settings: Settings = Depends(get_settings),
    llm: ChatGroq = Depends(get_llm),
    vectorstore: Chroma = Depends(get_vectorstore),
) -> InsightResponse:
    async with get_db(settings) as db:
        repo = WearableRepository(db)
        snapshots = await repo.get_snapshots_by_parent(body.parent_id, days=7)

    wearable_summary = format_wearable_summary(snapshots)

    try:
        chain = build_insight_chain(llm, vectorstore)
        insight = chain(
            parent_id=body.parent_id,
            query=body.query,
            wearable_summary=wearable_summary,
        )
        return InsightResponse(insight=insight, parent_id=body.parent_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {exc}") from exc
