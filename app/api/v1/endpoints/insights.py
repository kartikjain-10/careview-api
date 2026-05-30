from fastapi import APIRouter, Depends, HTTPException
from langchain_groq import ChatGroq
from langchain_chroma import Chroma

from app.core.config import Settings
from app.core.dependencies import get_current_group, get_llm, get_settings, get_vectorstore
from app.ai.chains.insight_chain import build_insight_chain
from app.ai.utils import format_wearable_summary
from app.db.database import get_db
from app.db.document_repository import DocumentRepository
from app.db.repository import WearableRepository
from app.db import family_repository
from app.models.schemas import InsightHistoryResponse, InsightRequest, InsightResponse

router = APIRouter()


@router.get("/insights/{parent_id}/history", response_model=InsightHistoryResponse)
async def insight_history(
    parent_id: str,
    group: dict = Depends(get_current_group),
    settings: Settings = Depends(get_settings),
) -> InsightHistoryResponse:
    async with get_db(settings) as db:
        member = await family_repository.get_member(db, parent_id)
        if not member or member["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Family member not found")
        repo = DocumentRepository(db)
        insights = await repo.get_insights_by_parent(parent_id)
    return InsightHistoryResponse(insights=insights)


@router.post("/insights", response_model=InsightResponse)
async def generate_insight(
    body: InsightRequest,
    group: dict = Depends(get_current_group),
    settings: Settings = Depends(get_settings),
    llm: ChatGroq = Depends(get_llm),
    vectorstore: Chroma = Depends(get_vectorstore),
) -> InsightResponse:
    async with get_db(settings) as db:
        member = await family_repository.get_member(db, body.parent_id)
        if not member or member["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Family member not found")
        wearable_repo = WearableRepository(db)
        document_repo = DocumentRepository(db)
        snapshots = await wearable_repo.get_snapshots_by_parent(body.parent_id, days=7)
        documents = await document_repo.get_documents_by_parent(body.parent_id)

    wearable_summary = format_wearable_summary(snapshots)
    document_inventory = "\n".join(
        (
            f"- {doc.filename} uploaded {doc.upload_date}; "
            f"status={doc.processing_status}; indexed_sections={doc.chunk_count}; "
            f"document_id={doc.document_id}"
        )
        for doc in documents
    ) or "No reports uploaded for this family member yet."

    try:
        chain = build_insight_chain(llm, vectorstore)
        insight, source_document_ids = chain(
            parent_id=body.parent_id,
            query=body.query,
            wearable_summary=wearable_summary,
            document_inventory=document_inventory,
        )
        async with get_db(settings) as db:
            document_repo = DocumentRepository(db)
            await document_repo.insert_insight(
                parent_id=body.parent_id,
                query=body.query,
                insight=insight,
                source_document_ids=source_document_ids,
            )
        return InsightResponse(
            insight=insight,
            parent_id=body.parent_id,
            report_count=len(documents),
            indexed_report_count=sum(1 for doc in documents if doc.processing_status == "indexed"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {exc}") from exc
