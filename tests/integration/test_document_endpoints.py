"""Integration tests for document endpoints — real SQLite, mocked vectorstore."""
import io
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_settings, get_vectorstore
from app.db.database import init_db
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        groq_api_key="test_key",
        chroma_persist_dir=str(tmp_path / "chroma"),
        sqlite_db_path=str(tmp_path / "test.db"),
    )


@pytest.fixture
def mock_vectorstore():
    vs = MagicMock()
    vs.add_documents = MagicMock(return_value=None)
    return vs


@pytest.fixture
def client(test_settings, mock_vectorstore, tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_vectorstore] = lambda: mock_vectorstore

    asyncio.get_event_loop().run_until_complete(init_db(test_settings))

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _minimal_pdf_bytes() -> bytes:
    """Return a minimal valid single-page PDF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\n"
        b"BT /F1 12 Tf 100 700 Td (Hello CareView) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000266 00000 n \n"
        b"0000000360 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n441\n%%EOF\n"
    )


def test_should_return_422_for_non_pdf_file(client):
    resp = client.post(
        "/api/v1/documents/upload",
        data={"parent_id": "parent_1"},
        files={"file": ("report.txt", b"not a pdf", "text/plain")},
    )
    assert resp.status_code == 422


def test_should_return_empty_list_when_no_documents_uploaded(client):
    resp = client.get("/api/v1/documents/parent_no_docs")
    assert resp.status_code == 200
    assert resp.json() == {"documents": []}


def test_should_return_document_metadata_after_upload(client, mock_vectorstore, tmp_path):
    pdf_bytes = _minimal_pdf_bytes()
    with patch("app.api.v1.endpoints.documents.PyPDFLoader") as mock_loader_cls:
        from langchain_core.documents import Document
        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Document(page_content="Lab results: Cholesterol 180.", metadata={})
        ]
        mock_loader_cls.return_value = mock_loader

        resp = client.post(
            "/api/v1/documents/upload",
            data={"parent_id": "parent_1"},
            files={"file": ("labs.pdf", pdf_bytes, "application/pdf")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["parent_id"] == "parent_1"
    assert body["filename"] == "labs.pdf"
    assert "document_id" in body
    assert body["chunk_count"] >= 1


def test_should_call_vectorstore_add_documents_on_upload(client, mock_vectorstore):
    with patch("app.api.v1.endpoints.documents.PyPDFLoader") as mock_loader_cls:
        from langchain_core.documents import Document
        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Document(page_content="Blood pressure reading normal.", metadata={})
        ]
        mock_loader_cls.return_value = mock_loader

        client.post(
            "/api/v1/documents/upload",
            data={"parent_id": "parent_1"},
            files={"file": ("bp.pdf", b"%PDF-1.4", "application/pdf")},
        )

    mock_vectorstore.add_documents.assert_called_once()


def test_should_attach_parent_id_to_chunk_metadata(client, mock_vectorstore):
    captured_chunks = []

    def capture(chunks):
        captured_chunks.extend(chunks)

    mock_vectorstore.add_documents = capture

    with patch("app.api.v1.endpoints.documents.PyPDFLoader") as mock_loader_cls:
        from langchain_core.documents import Document
        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Document(page_content="A" * 600, metadata={})
        ]
        mock_loader_cls.return_value = mock_loader

        client.post(
            "/api/v1/documents/upload",
            data={"parent_id": "parent_99"},
            files={"file": ("scan.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert len(captured_chunks) >= 1
    for chunk in captured_chunks:
        assert chunk.metadata["parent_id"] == "parent_99"
        assert chunk.metadata["filename"] == "scan.pdf"


def test_should_list_documents_after_upload(client):
    with patch("app.api.v1.endpoints.documents.PyPDFLoader") as mock_loader_cls:
        from langchain_core.documents import Document
        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Document(page_content="Thyroid report normal.", metadata={})
        ]
        mock_loader_cls.return_value = mock_loader

        client.post(
            "/api/v1/documents/upload",
            data={"parent_id": "parent_list"},
            files={"file": ("thyroid.pdf", b"%PDF-1.4", "application/pdf")},
        )

    resp = client.get("/api/v1/documents/parent_list")
    assert resp.status_code == 200
    docs = resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "thyroid.pdf"


def test_should_not_show_other_parents_documents(client):
    with patch("app.api.v1.endpoints.documents.PyPDFLoader") as mock_loader_cls:
        from langchain_core.documents import Document
        mock_loader = MagicMock()
        mock_loader.load.return_value = [Document(page_content="content", metadata={})]
        mock_loader_cls.return_value = mock_loader

        client.post(
            "/api/v1/documents/upload",
            data={"parent_id": "alice"},
            files={"file": ("alice.pdf", b"%PDF-1.4", "application/pdf")},
        )

    resp = client.get("/api/v1/documents/bob")
    assert resp.json() == {"documents": []}
