# app/azure_native_utils.py
"""
Azure-native utilities using 100% Azure services:
- Azure OpenAI (instead of OpenAI API)
- Azure AI Search (instead of ChromaDB)
- Azure Blob Storage (instead of AWS S3)
- Azure Key Vault (for secrets)
"""

import os
import json
from typing import List, Dict, Any
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
)
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

# --- Auto-load .env ---
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# --- Azure OpenAI Configuration ---
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT_CHAT = os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT", "gpt-4o-mini")
AZURE_OPENAI_DEPLOYMENT_EMBED = os.getenv("AZURE_OPENAI_DEPLOYMENT_EMBED", "text-embedding-3-small")

# --- Azure AI Search Configuration ---
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "hr-policy-chunks")

# --- Azure Storage Configuration ---
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "documents")

# --- Initialize Clients ---

# Azure OpenAI Client
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY:
    azure_openai_client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    print(f"✓ Azure OpenAI initialized: {AZURE_OPENAI_ENDPOINT}")
else:
    azure_openai_client = None
    print("⚠ Azure OpenAI not configured")

# Azure Blob Storage Client
if AZURE_STORAGE_CONNECTION_STRING:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    print(f"✓ Azure Blob Storage initialized")
else:
    blob_service_client = None
    print("⚠ Azure Storage not configured")

# Azure AI Search Clients
if AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY:
    search_credential = AzureKeyCredential(AZURE_SEARCH_KEY)
    search_index_client = SearchIndexClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=search_credential
    )
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=search_credential
    )
    print(f"✓ Azure AI Search initialized: {AZURE_SEARCH_INDEX}")
else:
    search_index_client = None
    search_client = None
    print("⚠ Azure AI Search not configured")


# ========================================
# Azure OpenAI Functions
# ========================================

def azure_embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using Azure OpenAI.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (1536-dimensional)
    """
    if not azure_openai_client:
        raise RuntimeError("Azure OpenAI client not initialized")

    response = azure_openai_client.embeddings.create(
        model=AZURE_OPENAI_DEPLOYMENT_EMBED,
        input=texts
    )

    return [item.embedding for item in response.data]


def azure_embed_one(text: str) -> List[float]:
    """Generate embedding for a single text."""
    return azure_embed_texts([text])[0]


def azure_chat_completion(messages: List[Dict[str, str]], temperature: float = 0.1, max_tokens: int = 1000) -> tuple:
    """
    Generate chat completion using Azure OpenAI.

    Args:
        messages: List of message dicts with 'role' and 'content'
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Tuple of (response_text, latency_ms, prompt_tokens, completion_tokens, cost_in, cost_out)
    """
    if not azure_openai_client:
        raise RuntimeError("Azure OpenAI client not initialized")

    import time
    start = time.time()

    response = azure_openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_CHAT,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

    latency_ms = int((time.time() - start) * 1000)

    message = response.choices[0].message.content
    usage = response.usage

    # Azure OpenAI pricing (approximate - check current pricing)
    # GPT-4o-mini: $0.60 per 1M input tokens, $2.40 per 1M output tokens
    cost_in = (usage.prompt_tokens / 1_000_000) * 0.60
    cost_out = (usage.completion_tokens / 1_000_000) * 2.40

    return message, latency_ms, usage.prompt_tokens, usage.completion_tokens, cost_in, cost_out


# ========================================
# Azure Blob Storage Functions
# ========================================

def azure_blob_get(blob_name: str, container_name: str = None) -> bytes:
    """Download blob and return contents as bytes."""
    if not blob_service_client:
        raise RuntimeError("Azure Blob Storage client not initialized")

    container = container_name or AZURE_CONTAINER_NAME
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)

    return blob_client.download_blob().readall()


def azure_blob_get_json(blob_name: str, container_name: str = None) -> dict:
    """Download JSON blob and return parsed dictionary."""
    blob_bytes = azure_blob_get(blob_name, container_name)
    return json.loads(blob_bytes.decode("utf-8"))


def azure_blob_upload(blob_name: str, data: bytes, container_name: str = None) -> str:
    """Upload data to blob."""
    if not blob_service_client:
        raise RuntimeError("Azure Blob Storage client not initialized")

    container = container_name or AZURE_CONTAINER_NAME
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
    blob_client.upload_blob(data, overwrite=True)

    return blob_client.url


# ========================================
# Azure AI Search Functions (Vector Store)
# ========================================

def create_search_index():
    """
    Create Azure AI Search index with vector search capabilities.
    Call this once during initial setup.
    """
    if not search_index_client:
        raise RuntimeError("Azure AI Search client not initialized")

    # Define index schema
    fields = [
        SearchField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            sortable=True,
            filterable=True
        ),
        SearchField(
            name="content",
            type=SearchFieldDataType.String,
            searchable=True,
            retrievable=True
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,  # text-embedding-3-small dimensions
            vector_search_profile_name="hnsw-config"
        ),
        SearchField(
            name="doc_id",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True
        ),
        SearchField(
            name="page_start",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True
        ),
        SearchField(
            name="page_end",
            type=SearchFieldDataType.Int32,
            filterable=True
        ),
        SearchField(
            name="chunk_idx",
            type=SearchFieldDataType.Int32,
            filterable=True
        ),
    ]

    # Configure vector search
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-algorithm",
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="hnsw-config",
                algorithm_configuration_name="hnsw-algorithm"
            )
        ]
    )

    # Create index
    index = SearchIndex(
        name=AZURE_SEARCH_INDEX,
        fields=fields,
        vector_search=vector_search
    )

    result = search_index_client.create_or_update_index(index)
    print(f"✓ Created/updated search index: {result.name}")
    return result


def azure_search_upsert(chunks: List[Dict[str, Any]]):
    """
    Upload/update document chunks to Azure AI Search.

    Args:
        chunks: List of dicts with keys: id, content, content_vector, doc_id, page_start, page_end, chunk_idx
    """
    if not search_client:
        raise RuntimeError("Azure AI Search client not initialized")

    # Transform chunks to match index schema
    documents = []
    for chunk in chunks:
        documents.append({
            "id": chunk["id"],
            "content": chunk["text"],
            "content_vector": chunk["embedding"],
            "doc_id": chunk["metadata"]["doc_id"],
            "page_start": chunk["metadata"]["page_start"],
            "page_end": chunk["metadata"]["page_end"],
            "chunk_idx": chunk["metadata"]["chunk_idx"]
        })

    # Upload in batches of 1000 (Azure AI Search limit)
    batch_size = 1000
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        result = search_client.upload_documents(documents=batch)
        print(f"✓ Uploaded {len(batch)} documents to search index")

    return len(documents)


def azure_search_query(query_vector: List[float], top_k: int = 6, filter_by: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Query Azure AI Search using vector similarity.

    Args:
        query_vector: Embedding vector for the query
        top_k: Number of results to return
        filter_by: Optional filters (e.g., {"doc_id": "doc-001"})

    Returns:
        List of matching documents with scores
    """
    if not search_client:
        raise RuntimeError("Azure AI Search client not initialized")

    # Build filter string
    filter_str = None
    if filter_by:
        filter_parts = [f"{k} eq '{v}'" for k, v in filter_by.items()]
        filter_str = " and ".join(filter_parts)

    # Create vectorized query
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top_k,
        fields="content_vector"
    )

    # Execute search
    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        filter=filter_str,
        select=["id", "content", "doc_id", "page_start", "page_end", "chunk_idx"],
        top=top_k
    )

    # Transform results to match ChromaDB format
    hits = []
    for result in results:
        hits.append({
            "id": result["id"],
            "text": result["content"],
            "score": result["@search.score"],
            "metadata": {
                "doc_id": result["doc_id"],
                "page_start": result["page_start"],
                "page_end": result["page_end"],
                "chunk_idx": result["chunk_idx"]
            }
        })

    return hits


def azure_search_delete_by_doc(doc_id: str):
    """Delete all documents for a specific doc_id."""
    if not search_client:
        raise RuntimeError("Azure AI Search client not initialized")

    # Search for documents with this doc_id
    results = search_client.search(
        search_text="*",
        filter=f"doc_id eq '{doc_id}'",
        select=["id"],
        top=10000
    )

    # Delete documents
    doc_ids = [{"id": result["id"]} for result in results]
    if doc_ids:
        search_client.delete_documents(documents=doc_ids)
        print(f"✓ Deleted {len(doc_ids)} documents for doc_id: {doc_id}")

    return len(doc_ids)


# ========================================
# High-level functions (drop-in replacements)
# ========================================

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Wrapper for azure_embed_texts"""
    return azure_embed_texts(texts)


def embed_one(text: str) -> List[float]:
    """Wrapper for azure_embed_one"""
    return azure_embed_one(text)


def ask_llm_with_context(snippets: List[str], question: str, conversation_history: List[dict]) -> tuple:
    """
    Generate answer using Azure OpenAI with conversation context.

    Returns: (message, latency_ms, prompt_tokens, completion_tokens, cost_in, cost_out)
    """
    system = (
        "You are a helpful AI assistant that answers questions based on provided document snippets. "
        "IMPORTANT RULES:\n"
        "1. Provide helpful answers using any relevant information from the snippets, even if indirect\n"
        "2. Make reasonable inferences from abbreviations, partial names, or contextual clues\n"
        "3. Always cite page numbers when referencing specific information\n"
        "4. Use conversation history for context on follow-up questions\n"
        "5. Be proactive in connecting related information across snippets\n"
        "6. Only say 'I don't know' if there is truly no relevant information whatsoever\n"
    )

    # Build message array
    messages = [{"role": "system", "content": system}]

    # Add conversation history (last 12 messages)
    recent_history = conversation_history[-12:] if len(conversation_history) > 12 else conversation_history
    for msg in recent_history:
        if msg["role"] in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current question with snippets
    snippets_text = "DOCUMENT SNIPPETS:\n\n" + "\n\n---\n\n".join(snippets)
    current_prompt = f"{snippets_text}\n\nCURRENT QUESTION: {question}\n\nAnswer based only on the snippets above:"
    messages.append({"role": "user", "content": current_prompt})

    # Call Azure OpenAI
    return azure_chat_completion(messages, temperature=0.1, max_tokens=1000)


# ========================================
# Initialization Check
# ========================================

def check_azure_services():
    """Check which Azure services are configured."""
    status = {
        "azure_openai": azure_openai_client is not None,
        "azure_storage": blob_service_client is not None,
        "azure_search": search_client is not None,
    }

    print("\n" + "=" * 50)
    print("Azure Services Status:")
    print("=" * 50)
    for service, is_configured in status.items():
        symbol = "✓" if is_configured else "✗"
        print(f"  {symbol} {service}: {'Configured' if is_configured else 'Not configured'}")
    print("=" * 50 + "\n")

    return status