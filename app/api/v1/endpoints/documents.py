from __future__ import annotations

import os
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.core.config import Settings
from app.core.dependencies import get_settings, get_vectorstore
from app.db.database import get_db
from app.db.document_repository import DocumentRepository
from app.models.schemas import DocumentListResponse, DocumentMetadata

router = APIRouter(prefix="/documents", tags=["documents"])

_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


def _extract_pdf_pages(file_path: str) -> tuple[list[Document], str | None]:
    """Extract report text without losing the upload if parsing fails."""
    try:
        pages = PyPDFLoader(file_path).load()
        if pages and any(page.page_content.strip() for page in pages):
            return pages, None
    except Exception as exc:
        primary_error = str(exc)
    else:
        primary_error = "PDF contains no readable text"

    try:
        reader = PdfReader(file_path)
        pages = [
            Document(
                page_content=text,
                metadata={"page": index},
            )
            for index, page in enumerate(reader.pages)
            if (text := (page.extract_text() or "").strip())
        ]
        if pages:
            return pages, None
    except Exception as exc:
        return [], f"{primary_error}; fallback parser failed: {exc}"

    return [], primary_error


@router.post("/upload", response_model=DocumentMetadata)
async def upload_document(
    parent_id: str = Form(...),
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    vectorstore: Chroma = Depends(get_vectorstore),
) -> DocumentMetadata:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    # Persist raw PDF to disk
    upload_dir = os.path.join("data", "uploads", parent_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    upload_date = date.today().isoformat()
    document_id = str(uuid.uuid4())
    pages, extraction_error = _extract_pdf_pages(file_path)
    chunks = _splitter.split_documents(pages) if pages else []

    # Attach metadata to every chunk
    for chunk in chunks:
        chunk.metadata.update({
            "parent_id": parent_id,
            "filename": file.filename,
            "upload_date": upload_date,
            "document_id": document_id,
        })

    processing_status = "queued"
    if chunks:
        try:
            vectorstore.add_documents(chunks)
            processing_status = "indexed"
        except Exception as exc:
            extraction_error = f"Text extracted, but indexing failed: {exc}"
            chunks = []

    metadata = DocumentMetadata(
        document_id=document_id,
        parent_id=parent_id,
        filename=file.filename,
        upload_date=upload_date,
        chunk_count=len(chunks),
        processing_status=processing_status,
        extraction_error=extraction_error,
        summary=(
            f"{file.filename} is uploaded and searchable by AI."
            if processing_status == "indexed"
            else f"{file.filename} is uploaded but needs OCR before AI can read it."
        ),
    )

    async with get_db(settings) as db:
        repo = DocumentRepository(db)
        await repo.insert_document(metadata, file_path)

    return metadata


@router.get("/{parent_id}", response_model=DocumentListResponse)
async def list_documents(
    parent_id: str,
    settings: Settings = Depends(get_settings),
) -> DocumentListResponse:
    async with get_db(settings) as db:
        repo = DocumentRepository(db)
        documents = await repo.get_documents_by_parent(parent_id)

    return DocumentListResponse(documents=documents)
