"""Persistent policy indexing and semantic retrieval with ChromaDB."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
# Keep the configured local embedding weights available when the app runs
# without network access. Callers can override this via HF_HOME.
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".venv" / "hf-cache"))
_cached_bge = Path(os.environ["HF_HOME"]) / "hub" / "models--BAAI--bge-small-en-v1.5" / "snapshots"
if "HF_HUB_OFFLINE" not in os.environ and _cached_bge.is_dir() and any(_cached_bge.iterdir()):
    # Reuse verified local weights without waiting on optional Hub metadata
    # checks; a fresh installation can still download weights on first use.
    os.environ["HF_HUB_OFFLINE"] = "1"
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", "data/chroma"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "mediguard_policy_clauses")
EMBEDDING_MODEL = os.getenv("CHROMA_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
ACTIVE_EMBEDDING_BACKEND = "not_initialized"
_CHROMA_CLIENT = None
_CHROMA_COLLECTION = None


def _client_and_collection():
    global ACTIVE_EMBEDDING_BACKEND, _CHROMA_CLIENT, _CHROMA_COLLECTION
    if _CHROMA_CLIENT is not None and _CHROMA_COLLECTION is not None:
        return _CHROMA_COLLECTION
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
        ACTIVE_EMBEDDING_BACKEND = EMBEDDING_MODEL
    except Exception:
        # Chroma's default embedding function remains usable when the optional
        # sentence-transformers model cannot be loaded locally.
        collection = client.get_or_create_collection(COLLECTION_NAME)
        ACTIVE_EMBEDDING_BACKEND = "chromadb_default_fallback"
    _CHROMA_CLIENT = client
    _CHROMA_COLLECTION = collection
    return collection


def close_policy_index() -> None:
    """Release the cached Chroma client (used by isolated evaluation runs)."""
    global _CHROMA_CLIENT, _CHROMA_COLLECTION
    if _CHROMA_CLIENT is not None:
        _CHROMA_CLIENT.close()
    _CHROMA_CLIENT = None
    _CHROMA_COLLECTION = None


def embedding_backend_status() -> dict[str, str]:
    """Report the backend actually selected after Chroma initialization."""
    _client_and_collection()
    return {"configured": EMBEDDING_MODEL, "active": ACTIVE_EMBEDDING_BACKEND}


_SECTION_HEADERS = re.compile(
    r"^\s*(?:\d+[\.\)]\s*)?("
    r"coverage|covered benefits?|what is covered"
    r"|exclusions?|what is not covered|not covered"
    r"|waiting period|pre-?existing"
    r"|co-?pay(?:ment)?|deductible|cost.?shar"
    r"|sub.?limit|room rent|room limit|daily limit"
    r"|claim(?:s)? procedure|how to claim|claim process"
    r"|network|cashless|empanelled"
    r"|general conditions?|definitions?|eligibility"
    r"|premium|renewal|termination"
    r")\s*$",
    re.IGNORECASE,
)


def _detect_section(paragraph: str) -> str | None:
    """Return a normalised section label if the paragraph looks like a header."""
    stripped = paragraph.strip()
    # Headers are typically short (≤ 80 chars) and match a known keyword.
    if len(stripped) > 80:
        return None
    match = _SECTION_HEADERS.match(stripped)
    if match:
        return match.group(1).lower().replace(" ", "_").replace("-", "_")
    return None


def chunk_policy_text(text: str, page: int = 1, chunk_size: int = 700, overlap: int = 100) -> list[dict[str, Any]]:
    """Split policy text into overlapping chunks, tagging each with its parent section.

    Lines are first split on any newline.  Lines that match a known section
    header keyword (e.g. "Exclusions", "Waiting Period") update the active
    section label and trigger a buffer flush; all other lines are accumulated
    into size-bounded, overlapping chunks.  This produces the section-aware,
    clause-level metadata the RAG retrieval step relies on for filtered queries.
    """
    lines = [line.rstrip() for line in (text or "").splitlines()]
    chunks: list[dict[str, Any]] = []
    current = ""
    current_section = "general"

    def _flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append({"text": current.strip(), "page": page, "section": current_section})
        current = ""

    for line in lines:
        detected = _detect_section(line)
        if detected:
            _flush()
            current_section = detected
            continue
        if not line.strip():
            # Blank line: treat as a soft paragraph boundary.
            if current:
                current += " "
            continue
        candidate = (current + " " + line).strip() if current else line
        if current and len(candidate) > chunk_size:
            _flush()
            tail = current[-overlap:] if overlap else ""
            current = (tail + " " + line).strip()
        else:
            current = candidate

    _flush()
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
                chunk_id = hashlib.sha256(identity.encode()).hexdigest()
                ids.append(chunk_id)
                texts.append(chunk["text"])
                metadatas.append({"policy_id": policy_id, "document_id": document.get("document_id", ""), "source_name": document.get("source_name", ""), "page": page, "section": chunk["section"], "clause_id": chunk_id})
    if ids:
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
    return {"collection": COLLECTION_NAME, "policy_id": policy_id, "chunks_indexed": len(ids), "storage_path": str(CHROMA_DIR)}


def retrieve_policy_evidence(query: str, policy_id: str, limit: int = 8) -> list[dict[str, Any]]:
    collection = _client_and_collection()
    result = collection.query(query_texts=[query], n_results=limit, where={"policy_id": policy_id} if policy_id else None, include=["documents", "metadatas", "distances"])
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    output = []
    for index, text in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else None
        stable_id = metadata.get("clause_id") or hashlib.sha256(f"{metadata.get('policy_id', policy_id)}|{metadata.get('document_id', 'policy')}|{metadata.get('page', 1)}|{text}".encode()).hexdigest()
        output.append({"clause_id": stable_id, "text": text, "page": metadata.get("page", 1), "section": metadata.get("section", "policy"), "source_name": metadata.get("source_name", ""), "policy_id": metadata.get("policy_id", policy_id), "distance": distance})
    return output
