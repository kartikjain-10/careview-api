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
                processing_status, extraction_error, summary, report_type,
                report_date, provider, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                metadata.report_type,
                metadata.report_date,
                metadata.provider,
                metadata.status,
            ),
        )
        await self._db.commit()

    async def get_document(self, document_id: str) -> DocumentMetadata | None:
        async with self._db.execute(
            """
            SELECT id, parent_id, filename, upload_date, chunk_count,
                   processing_status, extraction_error, summary,
                   report_type, report_date, provider, status
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_metadata(row) if row else None

    async def get_documents_by_parent(self, parent_id: str) -> List[DocumentMetadata]:
        async with self._db.execute(
            """
            SELECT id, parent_id, filename, upload_date, chunk_count,
                   processing_status, extraction_error, summary,
                   report_type, report_date, provider, status
            FROM   documents
            WHERE  parent_id = ?
            ORDER  BY upload_date DESC
            """,
            (parent_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_metadata(row) for row in rows]

    async def update_summary(self, document_id: str, summary: str) -> DocumentMetadata | None:
        await self._db.execute(
            "UPDATE documents SET summary = ? WHERE id = ?",
            (summary, document_id),
        )
        await self._db.commit()
        return await self.get_document(document_id)

    def _row_to_metadata(self, row: aiosqlite.Row) -> DocumentMetadata:
        def value(key: str, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        return DocumentMetadata(
            document_id=value("id"),
            parent_id=value("parent_id"),
            filename=value("filename"),
            upload_date=value("upload_date"),
            chunk_count=value("chunk_count"),
            processing_status=value("processing_status", "indexed"),
            extraction_error=value("extraction_error"),
            summary=value("summary"),
            report_type=value("report_type"),
            report_date=value("report_date"),
            provider=value("provider"),
            status=value("status", "active") or "active",
        )

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
