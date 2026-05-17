import chromadb
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import Settings


def build_vectorstore(settings: Settings) -> Chroma:
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    return Chroma(
        client=client,
        collection_name="careview_docs",
        embedding_function=embeddings,
    )
