from __future__ import annotations

import json
from typing import List
from uuid import uuid4

import aiosqlite

from app.models.schemas import DocumentMetadata, InsightRecord


class DocumentRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert_document(self, metadata: DocumentMetadata, file_path: str) -> None:
        await self._db.execute(
            """
            INSERT INTO documents (
                id, parent_id, filename, upload_date, chunk_count, file_path,
                processing_status, extraction_error, summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.document_id,
                metadata.parent_id,
                metadata.filename,
                metadata.upload_date,
                metadata.chunk_count,
                file_path,
                metadata.processing_status,
                metadata.extraction_error,
                metadata.summary,
            ),
        )
        await self._db.commit()

    async def get_documents_by_parent(self, parent_id: str) -> List[DocumentMetadata]:
        async with self._db.execute(
            """
            SELECT id, parent_id, filename, upload_date, chunk_count,
                   processing_status, extraction_error, summary
            FROM   documents
            WHERE  parent_id = ?
            ORDER  BY upload_date DESC
            """,
            (parent_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            DocumentMetadata(
                document_id=row["id"],
                parent_id=row["parent_id"],
                filename=row["filename"],
                upload_date=row["upload_date"],
                chunk_count=row["chunk_count"],
                processing_status=row["processing_status"],
                extraction_error=row["extraction_error"],
                summary=row["summary"],
            )
            for row in rows
        ]

    async def insert_insight(
        self,
        parent_id: str,
        query: str,
        insight: str,
        source_document_ids: list[str],
        model: str = "groq:llama-3.3-70b-versatile",
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO health_insights (id, parent_id, query, insight, source_document_ids, model)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                parent_id,
                query,
                insight,
                json.dumps(source_document_ids),
                model,
            ),
        )
        await self._db.commit()

    async def get_insights_by_parent(self, parent_id: str, limit: int = 20) -> list[InsightRecord]:
        async with self._db.execute(
            """
            SELECT id, parent_id, query, insight, source_document_ids, model, created_at
            FROM   health_insights
            WHERE  parent_id = ?
            ORDER  BY created_at DESC
            LIMIT  ?
            """,
            (parent_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            InsightRecord(
                insight_id=row["id"],
                parent_id=row["parent_id"],
                query=row["query"],
                insight=row["insight"],
                source_document_ids=json.loads(row["source_document_ids"] or "[]"),
                model=row["model"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
