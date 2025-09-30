# app/main_azure.py
"""
Azure-compatible version of main.py
Uses Azure Blob Storage instead of AWS S3
"""
import os, time, json, pathlib
import logging

# Silence Chroma/telemetry noise in logs
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_ENABLED", "false")

# Configure detailed logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Ensure our logger propagates to uvicorn
logger.setLevel(logging.INFO)
logger.propagate = True

from typing import List, Dict, Any, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid

from .utils import (
    pdf_to_pages,
    chunk_pages,
    embed_texts,
    embed_one,
    ask_llm_with_context,
)

# Import Azure utilities
try:
    from .azure_utils import azure_blob_get, azure_blob_get_json
    USE_AZURE = True
    logger.info("Using Azure Blob Storage")
except ImportError:
    logger.warning("Azure utilities not available, falling back to AWS S3")
    from .utils import s3_get as azure_blob_get, s3_get_json as azure_blob_get_json
    USE_AZURE = False

from .vectordb.chroma_store import ChromaStore

DOC_ID = os.getenv("DOC_ID", "doc-001")
THRESHOLD = float(os.getenv("THRESHOLD", "0.15"))
TOP_K = int(os.getenv("TOP_K", "6"))

store = ChromaStore("./data/chroma")
STATE_DIR = pathlib.Path(".state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = STATE_DIR / "state.json"

app = FastAPI(
    title="HR Policy Chatbot",
    description="AI-powered HR policy question answering system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static UI under /ui
app.mount("/ui", StaticFiles(directory="web", html=True), name="ui")

# Add startup logging
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("HR Policy Chatbot starting up...")
    logger.info(f"Storage Backend: {'Azure Blob Storage' if USE_AZURE else 'AWS S3'}")
    logger.info("Detailed logging enabled for /ask endpoint")
    logger.info("UI available at /ui")
    logger.info("API docs available at /docs")
    logger.info("=" * 60)

METRICS: Dict[str, Any] = {"qcount": 0, "usd_total": 0.0, "latencies": [], "last_ingested_key": None}
CONVERSATIONS: Dict[str, List[Dict[str, str]]] = {}


def read_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def write_state(d: dict):
    STATE_PATH.write_text(json.dumps(d, indent=2), encoding="utf-8")


def ensure_ingested() -> Dict[str, Any]:
    """
    Fetch manifest from Azure Blob Storage and (re)ingest if the latest pdf key changed.
    Requires blob: <DOC_ID>/manifest.json with {"latest_pdf": "<DOC_ID>/<ts>.pdf"}
    """
    manifest_key = f"{DOC_ID}/manifest.json"

    try:
        manifest = azure_blob_get_json(manifest_key)
    except Exception as e:
        return {"ok": False, "error": f"Failed to fetch manifest: {str(e)}"}

    latest_key = manifest.get("latest_pdf")
    if not latest_key:
        return {"ok": False, "error": f"manifest missing latest_pdf at {manifest_key}"}

    state = read_state()
    if state.get("last_ingested_key") == latest_key:
        return {"ok": True, "s3_key": latest_key, "action": "noop"}

    # download, parse, chunk, embed, upsert
    try:
        pdf_bytes = azure_blob_get(latest_key)
    except Exception as e:
        return {"ok": False, "error": f"Failed to download PDF: {str(e)}"}

    pages = pdf_to_pages(pdf_bytes)
    if not any(pages):
        return {"ok": False, "error": "PDF appears to be scanned or textless."}

    chunks = chunk_pages(pages, target_tokens=1200, overlap=300, stitch_pages=True)
    vecs = embed_texts([c["text"] for c in chunks])

    # clear previous vectors for this doc and insert fresh ones
    store.delete_where({"doc_id": DOC_ID})
    points = []
    for c, v in zip(chunks, vecs):
        pid = f"{DOC_ID}:{c['page_start']}:{c['chunk_idx']}"
        points.append({
            "id": pid,
            "text": c["text"],
            "embedding": v,
            "metadata": {
                "doc_id": DOC_ID,
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "chunk_idx": c["chunk_idx"],
            },
        })
    store.upsert(points)

    state["last_ingested_key"] = latest_key
    state["pages"] = len(pages)
    state["chunks"] = len(points)
    write_state(state)
    METRICS["last_ingested_key"] = latest_key

    return {"ok": True, "s3_key": latest_key, "pages": len(pages), "chunks": len(points), "action": "reingested"}


class AskBody(BaseModel):
    question: str
    top_k: int | None = None
    threshold: float | None = None
    session_id: str | None = None

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str | None = None
    sources: List[int] | None = None


@app.get("/")
def root():
    """Root endpoint - redirect to UI"""
    return {
        "message": "HR Policy Chatbot API",
        "ui": "/ui",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health():
    state = read_state()
    return {
        "status": "healthy",
        "storage": "Azure Blob Storage" if USE_AZURE else "AWS S3",
        "doc_id": DOC_ID,
        "last_ingested_key": state.get("last_ingested_key"),
        "pages": state.get("pages"),
        "chunks": state.get("chunks"),
    }


@app.post("/refresh")
def refresh():
    logger.info("[SYNC] Manual refresh requested")
    result = ensure_ingested()
    if result.get("ok"):
        action = result.get("action", "unknown")
        if action == "reingested":
            logger.info(f"[OK] Document reingested: {result.get('pages', 0)} pages, {result.get('chunks', 0)} chunks")
        else:
            logger.info(f"[OK] Document already current: {result.get('s3_key', 'unknown')}")
    else:
        logger.error(f"[ERROR] Refresh failed: {result.get('error', 'unknown error')}")
    return result


@app.post("/ask")
def ask(body: AskBody):
    start_time = time.time()

    session_id = body.session_id or str(uuid.uuid4())
    is_new_session = session_id not in CONVERSATIONS

    logger.info("=" * 80)
    logger.info(f"[QUESTION] NEW QUESTION RECEIVED")
    logger.info(f"Question: '{body.question}'")
    logger.info(f"Session: {session_id[:8]}... {'(NEW)' if is_new_session else '(EXISTING)'}")

    if is_new_session:
        CONVERSATIONS[session_id] = []
        logger.info("[NEW] Created new conversation session")
    else:
        logger.info(f"[SESSION] Continuing with {len(CONVERSATIONS[session_id])} previous messages")

    logger.info("[SYNC] Checking document synchronization...")
    sync = ensure_ingested()
    if not sync.get("ok"):
        logger.error(f"[ERROR] Document sync failed: {sync.get('error')}")
        return {"answer": "I don't know.", "sources": [], "error": sync.get("error", "sync_failed")}
    logger.info(f"[OK] Document sync: {sync.get('action')}")

    t_k = body.top_k or TOP_K
    thr = body.threshold or THRESHOLD

    logger.info("[EMBED] Generating question embedding...")
    qvec = embed_one(body.question)
    logger.info(f"[OK] Embedding generated (vector size: {len(qvec)})")

    logger.info(f"[SEARCH] Searching vector database (top_k={t_k}, threshold={thr})...")
    hits = store.query(qvec, top_k=t_k, filter_by={"doc_id": DOC_ID})

    if not hits:
        logger.warning("[WARNING] No search results found")
        CONVERSATIONS[session_id].append({"role": "user", "content": body.question})
        CONVERSATIONS[session_id].append({"role": "assistant", "content": "I don't know.", "sources": []})
        return {"answer": "I don't know.", "sources": [], "session_id": session_id}

    max_score = max(h["score"] for h in hits)
    logger.info(f"[STATS] Found {len(hits)} results (max score: {max_score:.3f})")

    if max_score < thr:
        logger.warning(f"[WARNING] All results below threshold (max: {max_score:.3f} < {thr:.3f})")
        return {"answer": "I don't know.", "sources": [], "session_id": session_id}

    snippets, pages = [], []
    for h in hits:
        if h["score"] >= thr:
            pg = h["metadata"]["page_start"]
            pages.append(pg)
            snippets.append(f"(page {pg}) {h['text'][:1200]}")

    logger.info(f"[CONTEXT] Prepared {len(snippets)} snippets from pages {sorted(set(pages))}")

    conversation_history = CONVERSATIONS[session_id]
    logger.info(f"[HISTORY] Using {len(conversation_history)} previous messages")

    logger.info("[LLM] Calling LLM for response...")
    msg, latency, ptok, ctok, usd_in, usd_out = ask_llm_with_context(snippets, body.question, conversation_history)

    logger.info(f"[OK] LLM response received (latency: {latency}ms)")
    logger.info(f"[COST] Tokens: {ptok} + {ctok} = ${(usd_in + usd_out):.6f}")

    CONVERSATIONS[session_id].append({"role": "user", "content": body.question})
    CONVERSATIONS[session_id].append({"role": "assistant", "content": msg, "sources": sorted(list(set(pages)))})

    if len(CONVERSATIONS[session_id]) > 20:
        CONVERSATIONS[session_id] = CONVERSATIONS[session_id][-20:]

    METRICS["qcount"] += 1
    METRICS["usd_total"] += (usd_in + usd_out)
    METRICS["latencies"].append(latency)

    logger.info(f"[SUCCESS] Question answered with {len(set(pages))} source pages")
    logger.info("=" * 80)

    return {
        "answer": msg,
        "sources": sorted(list(set(pages))),
        "session_id": session_id,
        "usage": {
            "prompt_tokens": ptok,
            "completion_tokens": ctok,
            "usd_total": round(usd_in + usd_out, 6),
        },
        "synced": sync,
    }


@app.get("/metrics")
def metrics():
    lats = sorted(METRICS["latencies"]) or [0]
    p50 = lats[len(lats) // 2]
    p95 = lats[int(len(lats) * 0.95) - 1] if len(lats) >= 20 else lats[-1]
    return {
        "queries": METRICS["qcount"],
        "usd_total": round(METRICS["usd_total"], 6),
        "p50_ms": p50,
        "p95_ms": p95,
        "last_ingested_key": METRICS.get("last_ingested_key"),
        "active_sessions": len(CONVERSATIONS),
    }


@app.get("/conversation/{session_id}")
def get_conversation(session_id: str):
    return {
        "session_id": session_id,
        "messages": CONVERSATIONS.get(session_id, []),
        "message_count": len(CONVERSATIONS.get(session_id, [])),
    }


@app.delete("/conversation/{session_id}")
def clear_conversation(session_id: str):
    if session_id in CONVERSATIONS:
        del CONVERSATIONS[session_id]
        return {"success": True, "message": "Conversation cleared"}
    return {"success": False, "message": "Session not found"}


@app.post("/conversation/new")
def new_conversation():
    session_id = str(uuid.uuid4())
    CONVERSATIONS[session_id] = []
    return {"session_id": session_id}


@app.post("/debug_search")
def debug_search(body: AskBody):
    """Debug endpoint to see similarity scores and retrieved chunks"""
    sync = ensure_ingested()
    if not sync.get("ok"):
        return {"error": sync.get("error", "sync_failed")}

    t_k = body.top_k or TOP_K
    thr = body.threshold or THRESHOLD

    qvec = embed_one(body.question)
    hits = store.query(qvec, top_k=t_k, filter_by={"doc_id": DOC_ID})

    debug_info = {
        "question": body.question,
        "threshold": thr,
        "top_k": t_k,
        "total_hits": len(hits) if hits else 0,
        "hits": []
    }

    if hits:
        for i, h in enumerate(hits):
            debug_info["hits"].append({
                "rank": i + 1,
                "score": h["score"],
                "page": h["metadata"]["page_start"],
                "chunk_id": h["id"],
                "text_preview": h["text"][:200] + "..." if len(h["text"]) > 200 else h["text"],
                "above_threshold": h["score"] >= thr
            })

    return debug_info