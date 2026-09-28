"""01 · config — every setting, read from .env. Everything imports this.

config.py holds values only (keys, URLs, model ids, thresholds). The
system-prompt text lives next door in prompts.py (02).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

## ENV VAR / SECRETS

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

## LOCAL DOCUMENT STORAGE

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

## VECTOR STORE

QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "hr_policies")

# Reliability path: a separate collection holding HR docs + non-HR noise
# together, so retrieval is tested against real cross-domain noise instead
# of the clean single-domain collection above.
QDRANT_NOISY_COLLECTION_NAME = os.getenv("QDRANT_NOISY_COLLECTION_NAME", "hr_policies_noisy_demo")

## MODELS

LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "openai/gpt-oss-20b")
FALLBACK_MODEL_NAME = os.getenv("FALLBACK_MODEL_NAME", "gpt-4o-mini")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")

## CHUNK / TEXT SPLITTING CONFIG

CHUNK_SIZE = 500
CHUNK_OVERLAP = 60

## RETRIEVAL RESULTS

# Broad questions ("list all maternity leave provisions") need enough
# chunks in context to answer in full; at CHUNK_SIZE=500 a single
# multi-section policy doc is often 4-5 chunks, so a small top_k can't
# return the whole thing no matter how the prompt is worded.
TOP_K_RESULTS = 5
RERANK_CANDIDATE_K = 12  # wider shortlist retrieved before re-ranking

## RELIABILITY — scope guardrail (see hr_assistant/tools.py)

# Exact values used in each policy file's "Policy Category:" line. The
# search tool hard-filters retrieval to only these categories — non-HR
# chunks (Finance/Sales/Operations/Business) are structurally unreachable,
# regardless of how confused embedding similarity gets.
HR_POLICY_CATEGORIES = {
    "Leave", "Work From Home", "Probation", "Notice Period", "Reimbursement",
    "Code of Conduct", "Holidays", "Maternity Paternity", "Travel Expense", "Exit Process",
}

# Reranker relevance cutoff — below this, the tool reports "not found"
# instead of returning a technically-in-scope but irrelevant chunk.
RELEVANCE_THRESHOLD = 0.35

## RELIABILITY — input/output safety guardrail

GUARDRAIL_PROVIDER = "none" if os.getenv("GUARDRAIL_PROVIDER", "openai").lower() == "none" else "openai"

# What to do when the guardrail PROVIDER itself errors (an API failure, not
# a content block). Input fails closed — an unscreened prompt must never
# reach the model. Output fails open — a transient screening error
# shouldn't discard an answer the model already produced. Both overridable.
# See hr_assistant/guardrails.py.
GUARDRAIL_FAIL_OPEN_INPUT = os.getenv("GUARDRAIL_FAIL_OPEN_INPUT", "false").strip().lower() == "true"
GUARDRAIL_FAIL_OPEN_OUTPUT = os.getenv("GUARDRAIL_FAIL_OPEN_OUTPUT", "true").strip().lower() == "true"

# The input guardrail screens the current question plus up to this many of
# the most recent *user* turns for the thread (0 disables history
# screening) — so a multi-turn attack that looks harmless message-by-message
# is still caught in aggregate. Assistant answers and tool output are never
# included. See hr_assistant/thread_memory.py's input_text_for_screening.
GUARDRAIL_HISTORY_TURNS = int(os.getenv("GUARDRAIL_HISTORY_TURNS", "6"))

## LANGSMITH — tracing and evaluation

LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "hr-policy-assistant")

## GROQ — fallback model and evaluation judge

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
JUDGE_MODEL_NAME = os.getenv("JUDGE_MODEL_NAME", "openai/gpt-oss-120b")

## RELIABILITY — semantic cache

SEMANTIC_CACHE_THRESHOLD = 0.93  # cosine similarity above this = cache hit

# Bound the in-memory cache: a long-lived process shouldn't grow forever,
# and a stale answer (policy changed + re-ingested) shouldn't be served
# indefinitely. Past MAX_ENTRIES the oldest entry is evicted; entries older
# than TTL_SECONDS are ignored on lookup (0 = never expire).
SEMANTIC_CACHE_MAX_ENTRIES = int(os.getenv("SEMANTIC_CACHE_MAX_ENTRIES", "500"))
SEMANTIC_CACHE_TTL_SECONDS = int(os.getenv("SEMANTIC_CACHE_TTL_SECONDS", "3600"))

# System-prompt text: hr_assistant/prompts.py (02).


def check_api_keys() -> None:
    """Stop early with a clear message if a required key/config is missing."""
    missing = [
        name for name, value in [
            ("GROQ_API_KEY", GROQ_API_KEY),
            ("OPENAI_API_KEY", OPENAI_API_KEY),
            ("QDRANT_URL", QDRANT_URL),
            ("QDRANT_API_KEY", QDRANT_API_KEY),
        ]
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required .env values: {', '.join(missing)}")
