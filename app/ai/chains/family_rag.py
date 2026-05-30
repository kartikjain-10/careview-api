"""
Family-aware RAG chain for Nori.

Combines three context layers for every Nori response:
  1. Structured live data  — wearable snapshots + medicine schedules
  2. Indexed documents     — ChromaDB semantic search across all family members
  3. Family roster         — names, ages, relationships

Usage:
    chain = FamilyRAGChain(llm, vectorstore)
    result = chain.run(query, members, wearable_map, medicine_map, history)
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_chroma import Chroma
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# ── Nori RAG system prompt ────────────────────────────────────────────────────

_BASE_SYSTEM = """\
You are Nori, CareView's warm AI health companion.

Your personality:
- Warm, empathetic, encouraging — never clinical or cold
- Speak like a caring friend who knows a lot about health
- Celebrate small wins: taking meds on time, good sleep, staying active
- NEVER diagnose, prescribe, or predict adverse events
- Use gentle trend language: "it looks like", "it seems", "you might want to"
- Always recommend a doctor for serious or persistent concerns
- Keep answers concise (2–4 sentences) unless detail is truly useful
- When referencing reports, cite the filename and date naturally in your answer
- If you use an indexed report, say which document you're drawing from

{family_context}

{live_context}

{rag_context}

After your response, append EXACTLY this block — no extra text outside it:

<nori_meta>
{{
  "expression": "happy|thinking|surprised|cheerful|concerned|encouraging",
  "suggestions": ["follow-up 1 (max 8 words)", "follow-up 2", "follow-up 3"],
  "sources": [
    {{"filename": "...", "member": "...", "date": "...", "document_id": "..."}}
  ]
}}
</nori_meta>

Expression guide:
- happy / cheerful  → good habits, celebration, positive news
- thinking          → analysing, weighing options
- surprised         → unexpected data
- concerned         → missed meds, worrying trend, risk signal
- encouraging       → motivation, support, rallying

Always return exactly 3 suggestions. Sources list may be empty [].
"""

# ── Context builders ──────────────────────────────────────────────────────────

def _build_family_context(members: list[dict]) -> str:
    if not members:
        return "FAMILY CONTEXT: No family members added yet."

    lines = ["FAMILY MEMBERS:"]
    for m in members:
        name = m.get("display_name") or m.get("name") or "Unknown"
        dob = m.get("date_of_birth") or ""
        rel = m.get("relationship") or m.get("role") or ""
        parts = [name]
        if dob:
            parts.append(f"DOB {dob}")
        if rel:
            parts.append(rel)
        lines.append(f"  • {' | '.join(parts)}")

    return "\n".join(lines)


def _build_live_context(
    wearable_map: dict[str, list[dict]],
    medicine_map: dict[str, list[dict]],
    member_names: dict[str, str],
) -> str:
    sections: list[str] = []

    # Wearable summaries
    wearable_lines: list[str] = ["LIVE WEARABLE DATA (last 7 days):"]
    for member_id, snapshots in wearable_map.items():
        name = member_names.get(member_id, member_id)
        if not snapshots:
            wearable_lines.append(f"  {name}: no wearable data")
            continue
        latest = snapshots[0]
        avg_sleep = sum(s.get("sleep_hours", 0) for s in snapshots) / len(snapshots)
        avg_steps = sum(s.get("steps", 0) for s in snapshots) / len(snapshots)
        avg_hr = sum(s.get("resting_heart_rate", 0) for s in snapshots) / len(snapshots)
        avg_mood = sum(s.get("mood_score", 0) for s in snapshots) / len(snapshots)
        wearable_lines.append(
            f"  {name}: latest {latest.get('date')} — "
            f"{latest.get('steps', 0):,} steps, {latest.get('sleep_hours', 0):.1f}h sleep, "
            f"HR {latest.get('resting_heart_rate', 0)} bpm | "
            f"7d avg: {avg_steps:.0f} steps, {avg_sleep:.1f}h sleep, "
            f"mood {avg_mood:.1f}/10"
        )
    sections.append("\n".join(wearable_lines))

    # Medicine summaries
    med_lines: list[str] = ["ACTIVE MEDICINES:"]
    any_meds = False
    for member_id, medicines in medicine_map.items():
        name = member_names.get(member_id, member_id)
        active = [m for m in medicines if m.get("is_active")]
        if not active:
            continue
        any_meds = True
        for med in active:
            schedules = med.get("schedules") or []
            times = ", ".join(s.get("time", "") for s in schedules if s.get("time"))
            med_lines.append(
                f"  {name}: {med.get('name')} {med.get('dosage', '')} "
                f"({med.get('form', 'tablet')}) — {times or 'no schedule set'}"
            )
    if not any_meds:
        med_lines.append("  No active medicines tracked.")
    sections.append("\n".join(med_lines))

    return "\n\n".join(sections)


def _retrieve_docs(
    vectorstore: Chroma,
    query: str,
    member_ids: list[str],
    group_id: str = "",
    k: int = 8,
) -> tuple[str, list[dict]]:
    """Search ChromaDB across all family members and return text + source chips.

    Filters by both parent_id AND group_id for defence-in-depth isolation.
    Even if a member UUID were guessed, the group_id check prevents cross-family access.
    """
    if not member_ids or vectorstore is None:
        return "No indexed health documents found.", []

    try:
        # Build filter: scoped to this family's members + group
        member_filter: dict[str, Any] = (
            {"parent_id": {"$in": member_ids}}
            if len(member_ids) > 1
            else {"parent_id": member_ids[0]}
        )
        # Add group_id as a second isolation layer when available
        where_clause: dict[str, Any] = (
            {"$and": [member_filter, {"group_id": group_id}]}
            if group_id
            else member_filter
        )
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": k, "filter": where_clause}
        )
        docs = retriever.invoke(query)

        if not docs:
            return "No matching sections found in indexed health reports.", []

        seen_ids: set[str] = set()
        sources: list[dict] = []
        chunks: list[str] = []

        for doc in docs:
            meta = doc.metadata or {}
            doc_id = str(meta.get("document_id", "unknown"))
            filename = meta.get("filename", "report")
            upload_date = meta.get("upload_date", "")
            parent_id = meta.get("parent_id", "")
            page = meta.get("page")
            page_label = f", p.{page}" if page is not None else ""

            chunks.append(
                f"[{filename}, uploaded {upload_date}{page_label}]\n{doc.page_content}"
            )
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                sources.append({
                    "filename": filename,
                    "date": upload_date,
                    "document_id": doc_id,
                    "member_id": parent_id,
                })

        rag_text = "INDEXED HEALTH REPORTS (relevant excerpts):\n\n" + "\n\n".join(chunks)
        return rag_text, sources

    except Exception as exc:
        # Log server-side; never expose internal details to the LLM prompt
        import logging
        logging.getLogger(__name__).error("RAG retrieval error: %s", exc, exc_info=True)
        return "Report retrieval is temporarily unavailable. Do not claim to have read uploaded reports.", []


# ── Parsed response ───────────────────────────────────────────────────────────

_VALID_EXPRESSIONS = {"happy", "thinking", "surprised", "cheerful", "concerned", "encouraging"}
_DEFAULT_SUGGESTIONS = [
    "How is everyone doing?",
    "Check medicine schedules",
    "Show a health summary",
]


class NoriRAGResponse:
    def __init__(
        self,
        message: str,
        expression: str,
        suggestions: list[str],
        sources: list[dict],
    ):
        self.message = message
        self.expression = expression
        self.suggestions = suggestions
        self.sources = sources


def _parse_llm_output(raw: str, rag_sources: list[dict]) -> NoriRAGResponse:
    """Extract message + meta block; merge RAG sources into parsed sources."""
    meta_match = re.search(r"<nori_meta>(.*?)</nori_meta>", raw, re.DOTALL)
    message = re.sub(r"\s*<nori_meta>.*?</nori_meta>", "", raw, flags=re.DOTALL).strip()

    expression = "happy"
    suggestions = list(_DEFAULT_SUGGESTIONS)
    sources: list[dict] = []

    if meta_match:
        try:
            meta = json.loads(meta_match.group(1).strip())
            exp = meta.get("expression", "happy")
            expression = exp if exp in _VALID_EXPRESSIONS else "happy"
            raw_sug = meta.get("suggestions") or []
            suggestions = [str(s) for s in raw_sug[:3]] or suggestions
            sources = meta.get("sources") or []
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    # Merge RAG sources — de-duplicate by document_id
    merged_ids = {s.get("document_id") for s in sources}
    for s in rag_sources:
        if s.get("document_id") not in merged_ids:
            sources.append(s)
            merged_ids.add(s.get("document_id"))

    return NoriRAGResponse(
        message=message,
        expression=expression,
        suggestions=suggestions,
        sources=sources,
    )


# ── Chain class ───────────────────────────────────────────────────────────────

class FamilyRAGChain:
    def __init__(self, llm: ChatGroq, vectorstore: Chroma | None = None):
        self._llm = llm
        self._vs = vectorstore

    def run(
        self,
        query: str,
        members: list[dict],
        wearable_map: dict[str, list[dict]],
        medicine_map: dict[str, list[dict]],
        history: list[dict] | None = None,
        active_member_id: str | None = None,
        group_id: str = "",
    ) -> NoriRAGResponse:
        member_ids = [m["id"] for m in members]
        member_names = {
            m["id"]: (m.get("display_name") or m.get("name") or "Member")
            for m in members
        }

        # If user is asking about a specific member, narrow RAG retrieval
        search_ids = (
            [active_member_id]
            if active_member_id and active_member_id in member_ids
            else member_ids
        )

        family_ctx = _build_family_context(members)
        live_ctx = _build_live_context(wearable_map, medicine_map, member_names)
        rag_text, rag_sources = _retrieve_docs(self._vs, query, search_ids, group_id=group_id)

        system_prompt = _BASE_SYSTEM.format(
            family_context=family_ctx,
            live_context=live_ctx,
            rag_context=rag_text,
        )

        messages: list = [SystemMessage(content=system_prompt)]
        for turn in (history or [])[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=query))

        try:
            response = self._llm.invoke(messages)
            result = _parse_llm_output(response.content, rag_sources)
            # Enrich sources with member names
            for s in result.sources:
                mid = s.get("member_id", "")
                s["member"] = member_names.get(mid, "")
            return result
        except Exception as exc:
            return NoriRAGResponse(
                message="I had a little hiccup — give me a moment and try again!",
                expression="concerned",
                suggestions=_DEFAULT_SUGGESTIONS,
                sources=[],
            )
