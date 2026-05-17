from __future__ import annotations

import os
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import Settings
from app.core.dependencies import get_settings, get_vectorstore
from app.db.database import get_db
from app.db.document_repository import DocumentRepository
from app.models.schemas import DocumentListResponse, DocumentMetadata

router = APIRouter(prefix="/documents", tags=["documents"])

_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


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

    # Extract text and chunk
    try:
        loader = PyPDFLoader(file_path)
        pages = loader.load()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {exc}") from exc

    if not pages:
        raise HTTPException(status_code=422, detail="PDF appears to be empty or unreadable")

    chunks = _splitter.split_documents(pages)
    upload_date = date.today().isoformat()
    document_id = str(uuid.uuid4())

    # Attach metadata to every chunk
    for chunk in chunks:
        chunk.metadata.update({
            "parent_id": parent_id,
            "filename": file.filename,
            "upload_date": upload_date,
            "document_id": document_id,
        })

    vectorstore.add_documents(chunks)

    metadata = DocumentMetadata(
        document_id=document_id,
        parent_id=parent_id,
        filename=file.filename,
        upload_date=upload_date,
        chunk_count=len(chunks),
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
