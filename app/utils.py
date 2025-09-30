# app/utils.py
import os, io, time, json
from typing import List
from pypdf import PdfReader
import tiktoken
from openai import OpenAI
import boto3

# --- Auto-load .env ---
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    # If python-dotenv isn't installed, the app will still work with env vars set in the shell
    pass

# --- Config from env ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it to your .env as OPENAI_API_KEY=sk-... "
        "or set $Env:OPENAI_API_KEY in PowerShell before running."
    )

CHAT_MODEL   = os.getenv("CHAT_MODEL", "gpt-4o-mini")
EMBED_MODEL  = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
AWS_REGION   = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET    = os.getenv("S3_BUCKET")  # validated lazily in s3_* fns

# --- SDK clients ---
client = OpenAI(api_key=OPENAI_API_KEY)
s3 = boto3.client("s3", region_name=AWS_REGION)

# --- Tokenizer (for chunking) ---
ENC = tiktoken.get_encoding("cl100k_base")


# -----------------------------
# PDF -> pages (text extraction)
# -----------------------------
def pdf_to_pages(pdf_bytes: bytes) -> List[str]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages: List[str] = []
    for i in range(len(reader.pages)):
        try:
            pages.append(reader.pages[i].extract_text() or "")
        except Exception:
            pages.append("")
    return pages


# -----------------------------
# Page-wise semantic chunking
# -----------------------------
def chunk_pages(pages: List[str], target_tokens: int = 800, overlap: int = 150, 
                min_chunk_tokens: int = 50, stitch_pages: bool = False):
    """
    Advanced paragraph-aware chunking with token budgeting and boundary safety.
    
    Features:
    - Preserves paragraph boundaries (no mid-paragraph splits)
    - Respects bullet points, numbered lists, and structured content
    - Optional cross-page stitching for context continuity
    - Token budget management with safety margins
    - Graceful handling of oversized paragraphs
    
    Args:
        pages: List of page text strings
        target_tokens: Target chunk size in tokens
        overlap: Token overlap between chunks
        min_chunk_tokens: Minimum viable chunk size
        stitch_pages: Create cross-page transition chunks
    """
    chunks = []
    global_chunk_idx = 0
    
    # Process individual pages first
    for pnum, page_text in enumerate(pages, start=1):
        if not page_text or not page_text.strip():
            continue  # Skip empty pages entirely
            
        try:
            page_chunks = _chunk_single_page_safe(
                page_text, pnum, target_tokens, overlap, min_chunk_tokens, global_chunk_idx
            )
            chunks.extend(page_chunks)
            global_chunk_idx += len(page_chunks)
        except Exception as e:
            # Fallback to simple chunking if advanced method fails
            print(f"Warning: Advanced chunking failed for page {pnum}, using fallback: {e}")
            fallback_chunks = _simple_chunk_page(
                page_text, pnum, target_tokens, overlap, global_chunk_idx
            )
            chunks.extend(fallback_chunks)
            global_chunk_idx += len(fallback_chunks)
    
    # Add cross-page stitch chunks if enabled
    if stitch_pages and len(pages) > 1:
        try:
            stitch_chunks = _create_cross_page_stitches(
                pages, chunks, target_tokens, global_chunk_idx
            )
            chunks.extend(stitch_chunks)
        except Exception as e:
            print(f"Warning: Cross-page stitching failed: {e}")
    
    return chunks


def _simple_chunk_page(page_text: str, page_num: int, target_tokens: int, 
                      overlap: int, start_chunk_idx: int) -> List[dict]:
    """
    Simple fallback chunking method (similar to original).
    """
    chunks = []
    toks = ENC.encode(page_text)
    
    if not toks:
        return []
    
    step = max(1, target_tokens - overlap)
    i = 0
    chunk_idx = start_chunk_idx
    
    while i < len(toks):
        window = toks[i : i + target_tokens]
        chunk_text = ENC.decode(window)
        
        chunks.append({
            "page_start": page_num,
            "page_end": page_num,
            "chunk_idx": chunk_idx,
            "text": chunk_text
        })
        
        i += step
        chunk_idx += 1
    
    return chunks


def _chunk_single_page_safe(page_text: str, page_num: int, target_tokens: int, 
                           overlap: int, min_chunk_tokens: int, start_chunk_idx: int):
    """
    Safe wrapper around the advanced chunking method.
    """
    return _chunk_single_page(page_text, page_num, target_tokens, overlap, min_chunk_tokens, start_chunk_idx)


def _chunk_single_page(page_text: str, page_num: int, target_tokens: int, 
                      overlap: int, min_chunk_tokens: int, start_chunk_idx: int):
    """
    Chunk a single page with paragraph awareness and token budgeting.
    """
    paragraphs = _extract_paragraphs(page_text)
    if not paragraphs:
        return []
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    chunk_idx = start_chunk_idx
    
    i = 0
    while i < len(paragraphs):
        para = paragraphs[i]
        para_tokens = len(ENC.encode(para))
        
        # Handle oversized paragraphs that exceed target
        if para_tokens > target_tokens:
            # Finish current chunk if it has content
            if current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    "page_start": page_num,
                    "page_end": page_num,
                    "chunk_idx": chunk_idx,
                    "text": chunk_text,
                    "type": "normal"
                })
                chunk_idx += 1
                current_chunk = []
                current_tokens = 0
            
            # Split oversized paragraph carefully
            oversized_chunks = _split_oversized_paragraph(
                para, page_num, target_tokens, chunk_idx
            )
            chunks.extend(oversized_chunks)
            chunk_idx += len(oversized_chunks)
            i += 1
            continue
        
        # Check if adding this paragraph would exceed target
        if current_tokens + para_tokens > target_tokens and current_chunk:
            # Create chunk from current content
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append({
                "page_start": page_num,
                "page_end": page_num,
                "chunk_idx": chunk_idx,
                "text": chunk_text,
                "type": "normal"
            })
            chunk_idx += 1
            
            # Prepare overlap for next chunk
            overlap_content = _create_overlap(current_chunk, overlap)
            current_chunk = overlap_content
            current_tokens = sum(len(ENC.encode(p)) for p in current_chunk)
        
        # Add current paragraph
        current_chunk.append(para)
        current_tokens += para_tokens
        i += 1
    
    # Handle remaining content
    if current_chunk:
        chunk_text = '\n\n'.join(current_chunk)
        # Always include remaining content if it's the only content for the page
        # or if it meets the minimum threshold
        token_count = len(ENC.encode(chunk_text))
        if token_count >= min_chunk_tokens or len(chunks) == 0:
            chunks.append({
                "page_start": page_num,
                "page_end": page_num,
                "chunk_idx": chunk_idx,
                "text": chunk_text,
                "type": "normal"
            })
    
    return chunks


def _extract_paragraphs(text: str) -> List[str]:
    """
    Extract paragraphs while preserving structure and formatting.

    Handles:
    - Regular paragraphs separated by double newlines
    - Bullet points and numbered lists
    - Headers and structured content
    - Code blocks and formatted sections
    """
    import re

    # Normalize line endings and clean up
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Filter out repetitive headers/footers that appear on every page
    text = _filter_headers_footers(text)

    # Split on double newlines first
    rough_paragraphs = re.split(r'\n\s*\n', text)

    paragraphs = []
    for para in rough_paragraphs:
        para = para.strip()
        if not para:
            continue

        # Skip if this looks like a header/footer
        if _is_header_footer(para):
            continue

        # Check for structured content that should stay together
        if _is_structured_content(para):
            paragraphs.append(para)
        else:
            # Further split on other natural boundaries
            sub_paras = _split_on_natural_boundaries(para)
            paragraphs.extend(sub_paras)

    return [p for p in paragraphs if p.strip()]


def _filter_headers_footers(text: str) -> str:
    """
    Remove repetitive headers and footers from page text.
    """
    import re

    lines = text.split('\n')
    filtered_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            filtered_lines.append('')
            continue

        # Skip only pure page numbers and repetitive contact lines
        if (
            re.match(r'^\s*Page\s+\d+\s*/\s*\d+\s*$', line, re.IGNORECASE) or
            re.match(r'^\s*\d+\s*$', line) or  # Just standalone page numbers
            (line.count('Phone:') and line.count('Email:') and len(line) > 100)  # Only long repetitive contact blocks
        ):
            continue

        filtered_lines.append(line)

    return '\n'.join(filtered_lines)


def _is_header_footer(text: str) -> bool:
    """
    Identify text that looks like a header or footer.
    """
    import re

    # Short texts that are likely headers/footers
    if len(text) < 20:
        return True

    # Only filter out long repetitive contact blocks, preserve company names
    if (
        'Phone:' in text and 'Email:' in text and len(text) > 100
    ):
        return True

    # Page numbers
    if re.match(r'^\s*Page\s+\d+', text, re.IGNORECASE):
        return True

    # Very short lines that are just numbers or basic info
    if len(text.split()) < 3:
        return True

    return False


def _is_structured_content(text: str) -> bool:
    """
    Identify content that should remain as single paragraphs.
    """
    import re
    
    # Bullet points or numbered lists
    if re.match(r'^\s*[•·\-\*]\s+', text) or re.match(r'^\s*\d+[\.\)]\s+', text):
        return True
    
    # Headers (short lines, often capitalized)
    if len(text) < 100 and ('\n' not in text or text.count('\n') <= 2):
        if text.isupper() or re.match(r'^[A-Z][^.]*$', text.strip()):
            return True
    
    # Tables or formatted data (contains multiple tabs or aligned content)
    if '\t' in text or re.search(r'\s{3,}', text):
        return True
    
    # Policy numbers, dates, or structured identifiers
    if re.search(r'\d+\.\d+|\d{1,2}/\d{1,2}/\d{4}|[A-Z]{2,}-\d+', text):
        return True
    
    return False


def _split_on_natural_boundaries(text: str) -> List[str]:
    """
    Split text on natural boundaries while avoiding bad breaks.
    """
    import re
    
    # Don't split short text
    if len(text) < 200:
        return [text]
    
    # Split on sentence boundaries, but be careful
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    
    paragraphs = []
    current_para = []
    
    for i, sentence in enumerate(sentences):
        current_para.append(sentence)
        
        # Check if we should break here
        para_text = ' '.join(current_para)
        next_sentences = sentences[i + 1:i + 2] if i + 1 < len(sentences) else []
        
        if (len(para_text) > 300 and 
            not _would_create_bad_break(sentence, next_sentences)):
            paragraphs.append(para_text)
            current_para = []
    
    # Add remaining content
    if current_para:
        paragraphs.append(' '.join(current_para))
    
    return paragraphs


def _would_create_bad_break(current_sentence: str, next_sentences: List[str]) -> bool:
    """
    Check if splitting after current sentence would create a bad break.
    """
    import re
    
    # Don't break in the middle of lists or numbered items
    if re.search(r'\b(including|such as|for example|e\.g\.|i\.e\.)\s*:?\s*$', current_sentence, re.IGNORECASE):
        return True
    
    # Don't break before continuing phrases
    if next_sentences and re.match(r'^\s*(however|therefore|furthermore|additionally|moreover)', 
                                   next_sentences[0], re.IGNORECASE):
        return True
    
    # Don't break numbers from their units
    if re.search(r'\d+\s*$', current_sentence) and next_sentences:
        if re.match(r'^\s*(days?|months?|years?|hours?|minutes?|%|percent)', 
                    next_sentences[0], re.IGNORECASE):
            return True
    
    return False


def _split_oversized_paragraph(paragraph: str, page_num: int, target_tokens: int, 
                              start_chunk_idx: int) -> List[dict]:
    """
    Safely split paragraphs that exceed token limits.
    """
    import re
    
    chunks = []
    chunk_idx = start_chunk_idx
    
    # Try splitting on sentences first
    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
    
    current_chunk = []
    current_tokens = 0
    
    for sentence in sentences:
        sentence_tokens = len(ENC.encode(sentence))
        
        # If single sentence is too large, split on other boundaries
        if sentence_tokens > target_tokens:
            # Finish current chunk
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append({
                    "page_start": page_num,
                    "page_end": page_num,
                    "chunk_idx": chunk_idx,
                    "text": chunk_text,
                    "type": "oversized_split"
                })
                chunk_idx += 1
                current_chunk = []
                current_tokens = 0
            
            # Force split the oversized sentence
            force_chunks = _force_split_text(sentence, page_num, target_tokens, chunk_idx)
            chunks.extend(force_chunks)
            chunk_idx += len(force_chunks)
            continue
        
        # Check if adding sentence would exceed limit
        if current_tokens + sentence_tokens > target_tokens and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                "page_start": page_num,
                "page_end": page_num,
                "chunk_idx": chunk_idx,
                "text": chunk_text,
                "type": "oversized_split"
            })
            chunk_idx += 1
            current_chunk = []
            current_tokens = 0
        
        current_chunk.append(sentence)
        current_tokens += sentence_tokens
    
    # Add remaining content
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunks.append({
            "page_start": page_num,
            "page_end": page_num,
            "chunk_idx": chunk_idx,
            "text": chunk_text,
            "type": "oversized_split"
        })
    
    return chunks


def _force_split_text(text: str, page_num: int, target_tokens: int, 
                     start_chunk_idx: int) -> List[dict]:
    """
    Last resort: force split text that can't be split naturally.
    """
    chunks = []
    chunk_idx = start_chunk_idx
    
    tokens = ENC.encode(text)
    
    i = 0
    while i < len(tokens):
        chunk_tokens = tokens[i:i + target_tokens]
        chunk_text = ENC.decode(chunk_tokens)
        
        chunks.append({
            "page_start": page_num,
            "page_end": page_num,
            "chunk_idx": chunk_idx,
            "text": chunk_text,
            "type": "force_split"
        })
        
        chunk_idx += 1
        i += target_tokens
    
    return chunks


def _create_overlap(paragraphs: List[str], overlap_tokens: int) -> List[str]:
    """
    Create overlap content from the end of current paragraphs.
    """
    if not paragraphs:
        return []
    
    overlap_content = []
    total_tokens = 0
    
    # Work backwards through paragraphs
    for para in reversed(paragraphs):
        para_tokens = len(ENC.encode(para))
        if total_tokens + para_tokens <= overlap_tokens:
            overlap_content.insert(0, para)
            total_tokens += para_tokens
        else:
            # Partial paragraph inclusion if needed
            if total_tokens < overlap_tokens * 0.7:  # 70% fill threshold
                remaining_tokens = overlap_tokens - total_tokens
                para_tokens_list = ENC.encode(para)
                if len(para_tokens_list) > remaining_tokens:
                    # Take the end of the paragraph
                    partial_tokens = para_tokens_list[-remaining_tokens:]
                    partial_text = ENC.decode(partial_tokens)
                    overlap_content.insert(0, "..." + partial_text)
            break
    
    return overlap_content


def _create_cross_page_stitches(pages: List[str], existing_chunks: List[dict], 
                               target_tokens: int, start_chunk_idx: int) -> List[dict]:
    """
    Create cross-page stitch chunks for better context continuity.
    
    These chunks combine the tail of page N with the head of page N+1
    to capture information that might span page boundaries.
    """
    stitch_chunks = []
    chunk_idx = start_chunk_idx
    
    for i in range(len(pages) - 1):
        current_page = pages[i].strip()
        next_page = pages[i + 1].strip()
        
        if not current_page or not next_page:
            continue
        
        # Extract tail from current page (last ~200 tokens)
        tail_tokens = min(200, target_tokens // 4)
        current_tokens = ENC.encode(current_page)
        if len(current_tokens) > tail_tokens:
            tail_start = len(current_tokens) - tail_tokens
            tail_text = ENC.decode(current_tokens[tail_start:])
            # Clean up partial words at the beginning
            tail_text = tail_text[tail_text.find(' ') + 1:] if ' ' in tail_text else tail_text
        else:
            tail_text = current_page
        
        # Extract head from next page (first ~200 tokens)  
        head_tokens = min(200, target_tokens // 4)
        next_tokens = ENC.encode(next_page)
        if len(next_tokens) > head_tokens:
            head_text = ENC.decode(next_tokens[:head_tokens])
            # Clean up partial words at the end
            head_text = head_text[:head_text.rfind(' ')] if ' ' in head_text else head_text
        else:
            head_text = next_page
        
        # Combine with clear page boundary marker
        stitch_text = f"{tail_text}\n\n--- PAGE BOUNDARY ---\n\n{head_text}"
        
        # Only create stitch if it provides meaningful content
        if len(ENC.encode(stitch_text)) >= 100:  # Minimum viable stitch
            stitch_chunks.append({
                "page_start": i + 1,
                "page_end": i + 2,
                "chunk_idx": chunk_idx,
                "text": stitch_text,
                "type": "cross_page_stitch"
            })
            chunk_idx += 1
    
    return stitch_chunks


# -----------------------------
# Embeddings
# -----------------------------
def embed_texts(texts: List[str]) -> List[List[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def embed_one(text: str) -> List[float]:
    return embed_texts([text])[0]


# -----------------------------
# Chat completion (grounded)
# -----------------------------
def ask_llm(snippets: List[str], question: str):
    """
    Returns: (message, latency_ms, prompt_tokens, completion_tokens, usd_in, usd_out)
    """
    system = (
        "Answer ONLY using the provided snippets. "
        "Cite exact page numbers from snippet headers. "
        "If insufficient, reply exactly: I don't know."
    )
    prompt = "Snippets:\n\n" + "\n\n---\n\n".join(snippets) + f"\n\nQuestion: {question}\nAnswer:"
    t0 = time.time()
    chat = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user",   "content": prompt}],
        temperature=0
    )
    latency = int((time.time() - t0) * 1000)
    msg = chat.choices[0].message.content
    usage = chat.usage

    # Cost estimate using list prices (USD per 1M tokens)
    usd_in  = (usage.prompt_tokens     / 1_000_000) * 0.60
    usd_out = (usage.completion_tokens / 1_000_000) * 2.40
    return msg, latency, usage.prompt_tokens, usage.completion_tokens, usd_in, usd_out


def ask_llm_with_context(snippets: List[str], question: str, conversation_history: List[dict]):
    """
    Enhanced version with conversation context for follow-up questions.
    Returns: (message, latency_ms, prompt_tokens, completion_tokens, usd_in, usd_out)
    """
    system = (
        "You are a helpful AI assistant that answers questions based on provided document snippets. "
        "IMPORTANT RULES:\n"
        "1. Provide helpful answers using any relevant information from the snippets, even if indirect\n"
        "2. Make reasonable inferences from abbreviations, partial names, or contextual clues\n"
        "3. If you see company codes like 'VSG' in a corporate handbook, infer what they might represent\n"
        "4. Always cite page numbers when referencing specific information\n"
        "5. Use conversation history for context on follow-up questions\n"
        "6. Be proactive in connecting related information across snippets\n"
        "7. Only say 'I don't know' if there is truly no relevant information whatsoever\n"
        "8. When asked about company names, look for any company references, codes, or headers\n"
    )
    
    # Build conversation context
    messages = [{"role": "system", "content": system}]
    
    # Add recent conversation history (last 6 exchanges to keep context manageable)
    recent_history = conversation_history[-12:] if len(conversation_history) > 12 else conversation_history
    for msg in recent_history:
        if msg["role"] in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current snippets and question
    snippets_text = "DOCUMENT SNIPPETS:\n\n" + "\n\n---\n\n".join(snippets)
    current_prompt = f"{snippets_text}\n\nCURRENT QUESTION: {question}\n\nAnswer based only on the snippets above:"
    
    messages.append({"role": "user", "content": current_prompt})
    
    t0 = time.time()
    chat = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.1,  # Slightly higher for more natural conversation
        max_tokens=1000
    )
    latency = int((time.time() - t0) * 1000)
    msg = chat.choices[0].message.content
    usage = chat.usage

    # Cost estimate using list prices (USD per 1M tokens)
    usd_in  = (usage.prompt_tokens     / 1_000_000) * 0.60
    usd_out = (usage.completion_tokens / 1_000_000) * 2.40
    return msg, latency, usage.prompt_tokens, usage.completion_tokens, usd_in, usd_out


# -----------------------------
# S3 helpers
# -----------------------------
def _require_bucket():
    if not S3_BUCKET:
        raise RuntimeError(
            "S3_BUCKET is not set. Put it in your .env as S3_BUCKET=your-bucket-name "
            "or set $Env:S3_BUCKET before running."
        )

def s3_get(key: str) -> bytes:
    _require_bucket()
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return obj["Body"].read()

def s3_get_json(key: str) -> dict:
    _require_bucket()
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))
