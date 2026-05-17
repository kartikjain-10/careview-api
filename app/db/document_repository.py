from __future__ import annotations

from typing import List

import aiosqlite

from app.models.schemas import DocumentMetadata


class DocumentRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert_document(self, metadata: DocumentMetadata, file_path: str) -> None:
        await self._db.execute(
            """
            INSERT INTO documents (id, parent_id, filename, upload_date, chunk_count, file_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.document_id,
                metadata.parent_id,
                metadata.filename,
                metadata.upload_date,
                metadata.chunk_count,
                file_path,
            ),
        )
        await self._db.commit()

    async def get_documents_by_parent(self, parent_id: str) -> List[DocumentMetadata]:
        async with self._db.execute(
            """
            SELECT id, parent_id, filename, upload_date, chunk_count
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
            )
            for row in rows
        ]
