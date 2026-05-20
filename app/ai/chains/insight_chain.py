from __future__ import annotations

from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_chroma import Chroma

SYSTEM_PROMPT = """You are CareView, a privacy-first family wellness assistant.

Your role is to provide warm, non-clinical wellness observations for aging parents
based on their wearable data and any uploaded health records.

STRICT RULES — never violate these:
- Do NOT draw medical conclusions or label any health condition
- Do NOT predict adverse health events or classify anything as urgent
- Do NOT suggest specific drugs or clinical interventions
- Do NOT use absolute language ("your condition is...", "you have...")
- Use trend-based, gentle language ("seems like", "appears to", "might want to")
- If relevant health records are provided, reference them gently — never alarmingly
- When using an uploaded report, cite the filename and upload date in plain language
- Distinguish measured facts from AI interpretation
- If no indexed report text is available, say that clearly before giving general guidance
- Always remind the user to consult a doctor for medical concerns
"""

USER_TEMPLATE = """Parent wellness query: {query}

Recent wearable data (last 7 days):
{wearable_summary}
Uploaded report inventory:
{document_inventory}

Indexed report excerpts:
{health_records_section}"""

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", USER_TEMPLATE),
])


def _retrieve_health_records(vectorstore: Chroma, parent_id: str, query: str) -> tuple[str, list[str]]:
    """Return relevant document chunks with source labels and document ids."""
    try:
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": 6, "filter": {"parent_id": parent_id}}
        )
        docs = retriever.invoke(query)
        if not docs:
            return "No indexed report text was found for this family member.", []
        source_ids: list[str] = []
        chunks = []
        for doc in docs:
            metadata = doc.metadata or {}
            document_id = str(metadata.get("document_id", "unknown"))
            if document_id != "unknown" and document_id not in source_ids:
                source_ids.append(document_id)
            filename = metadata.get("filename", "uploaded report")
            upload_date = metadata.get("upload_date", "unknown date")
            page = metadata.get("page")
            page_label = f", page {page}" if page is not None else ""
            chunks.append(
                f"[Source: {filename}, uploaded {upload_date}{page_label}, document_id={document_id}]\n"
                f"{doc.page_content}"
            )
        return "\n\n".join(chunks), source_ids
    except Exception:
        return "Report retrieval failed. Do not claim to have read uploaded reports.", []


def build_insight_chain(llm: ChatGroq, vectorstore: Optional[Chroma] = None):
    chain = _PROMPT | llm | StrOutputParser()

    def run(
        parent_id: str,
        query: str,
        wearable_summary: str = "",
        document_inventory: str = "No reports uploaded yet.",
    ) -> tuple[str, list[str]]:
        health_records_section, source_document_ids = (
            _retrieve_health_records(vectorstore, parent_id, query)
            if vectorstore is not None
            else ("Report retrieval is not configured.", [])
        )
        insight = chain.invoke({
            "query": query,
            "wearable_summary": wearable_summary or "No wearable data provided.",
            "document_inventory": document_inventory,
            "health_records_section": health_records_section,
        })
        return insight, source_document_ids

    return run
