"""Persistent policy indexing and semantic retrieval with ChromaDB."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

CHROMA_DIR = Path(os.getenv("CHROMA_DIR", "data/chroma"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "mediguard_policy_clauses")
EMBEDDING_MODEL = os.getenv("CHROMA_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")


def _client_and_collection():
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("ChromaDB is required. Run pip install -r requirements.txt.") from exc
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        embedding = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        collection = client.get_or_create_collection(COLLECTION_NAME, embedding_function=embedding)
    except Exception:
        # Chroma's default embedding function remains usable when the optional
        # sentence-transformers model cannot be loaded locally.
        collection = client.get_or_create_collection(COLLECTION_NAME)
    return collection


def chunk_policy_text(text: str, page: int = 1, chunk_size: int = 700, overlap: int = 100) -> list[dict[str, Any]]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}|(?<=[.!?])\s+", text or "") if part.strip()]
    chunks: list[dict[str, Any]] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current} {paragraph}".strip()
        if current and len(candidate) > chunk_size:
            chunks.append({"text": current, "page": page, "section": "policy"})
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {paragraph}".strip()
        else:
            current = candidate
    if current:
        chunks.append({"text": current, "page": page, "section": "policy"})
    return chunks


def index_policy_documents(policy_documents: list[dict[str, Any]], policy_id: str) -> dict[str, Any]:
    collection = _client_and_collection()
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for document in policy_documents:
        evidence = document.get("evidence", [])
        if evidence:
            page_groups: dict[int, list[str]] = {}
            for item in evidence:
                page_groups.setdefault(int(item.get("page", 1)), []).append(item.get("text", ""))
        else:
            page_groups = {1: [document.get("text", "")]}
        for page, page_text in page_groups.items():
            for index, chunk in enumerate(chunk_policy_text("\n".join(page_text), page=page), start=1):
                identity = f"{policy_id}|{document.get('document_id')}|{page}|{index}|{chunk['text']}"
                ids.append(hashlib.sha256(identity.encode()).hexdigest())
                texts.append(chunk["text"])
                metadatas.append({"policy_id": policy_id, "document_id": document.get("document_id", ""), "source_name": document.get("source_name", ""), "page": page, "section": chunk["section"]})
    if ids:
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
    return {"collection": COLLECTION_NAME, "policy_id": policy_id, "chunks_indexed": len(ids), "storage_path": str(CHROMA_DIR)}


def retrieve_policy_evidence(query: str, policy_id: str, limit: int = 8) -> list[dict[str, Any]]:
    collection = _client_and_collection()
    result = collection.query(query_texts=[query], n_results=limit, where={"policy_id": policy_id} if policy_id else None)
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    output = []
    for index, text in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else None
        output.append({"clause_id": f"{metadata.get('document_id', 'policy')}-{metadata.get('page', 1)}-{index + 1}", "text": text, "page": metadata.get("page", 1), "section": metadata.get("section", "policy"), "source_name": metadata.get("source_name", ""), "policy_id": metadata.get("policy_id", policy_id), "distance": distance})
    return output
