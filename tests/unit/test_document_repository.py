"""Unit tests for DocumentRepository — mocked aiosqlite connection."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.db.document_repository import DocumentRepository
from app.models.schemas import DocumentMetadata


def _make_metadata(**kwargs) -> DocumentMetadata:
    defaults = dict(
        document_id="doc-uuid-1",
        parent_id="parent_1",
        filename="report.pdf",
        upload_date="2025-01-15",
        chunk_count=5,
    )
    defaults.update(kwargs)
    return DocumentMetadata(**defaults)


@pytest.mark.asyncio
async def test_should_insert_document_with_correct_values():
    meta = _make_metadata()
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    repo = DocumentRepository(db)
    await repo.insert_document(meta, "/data/uploads/parent_1/report.pdf")

    db.execute.assert_called_once()
    sql, params = db.execute.call_args[0]
    assert "INSERT INTO documents" in sql
    assert params[0] == "doc-uuid-1"
    assert params[1] == "parent_1"
    assert params[2] == "report.pdf"
    assert params[4] == 5
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_should_return_documents_for_parent():
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "id": "doc-1", "parent_id": "parent_1",
        "filename": "labs.pdf", "upload_date": "2025-01-10", "chunk_count": 3,
    }[k]

    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    db = AsyncMock()
    db.execute = MagicMock(return_value=mock_cursor)

    repo = DocumentRepository(db)
    results = await repo.get_documents_by_parent("parent_1")

    assert len(results) == 1
    assert results[0].document_id == "doc-1"
    assert results[0].filename == "labs.pdf"
    assert results[0].chunk_count == 3


@pytest.mark.asyncio
async def test_should_return_empty_list_for_unknown_parent():
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    db = AsyncMock()
    db.execute = MagicMock(return_value=mock_cursor)

    repo = DocumentRepository(db)
    results = await repo.get_documents_by_parent("ghost")

    assert results == []


@pytest.mark.asyncio
async def test_should_filter_by_parent_id_in_query():
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    db = AsyncMock()
    db.execute = MagicMock(return_value=mock_cursor)

    repo = DocumentRepository(db)
    await repo.get_documents_by_parent("target_parent")

    call_args = db.execute.call_args[0]
    assert call_args[1] == ("target_parent",)
