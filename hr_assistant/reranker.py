"""10 · reranker — re-rank candidates with OpenAI embedding similarity."""

import numpy as np

from hr_assistant import config


def rerank_with_scores(query: str, candidates: list, top_n: int = config.TOP_K_RESULTS) -> list[tuple]:
    """Rank candidates by OpenAI embedding cosine similarity.

    The guarded search tool uses each score to gate relevance, not just
    reorder the wider candidate shortlist (see RERANK_CANDIDATE_K).
    """
    if not candidates:
        return []

    from hr_assistant.embeddings import get_embeddings_model

    embeddings = get_embeddings_model()
    query_vector = np.asarray(embeddings.embed_query(query), dtype=float)
    document_vectors = np.asarray(
        embeddings.embed_documents([candidate.page_content for candidate in candidates]),
        dtype=float,
    )
    query_norm = np.linalg.norm(query_vector) or 1.0
    document_norms = np.linalg.norm(document_vectors, axis=1)
    document_norms[document_norms == 0] = 1.0
    scores = (document_vectors @ query_vector) / (document_norms * query_norm)
    ranked = sorted(zip(candidates, scores.tolist()), key=lambda item: item[1], reverse=True)
    return [(document, float(score)) for document, score in ranked[:top_n]]


def rerank(query: str,
    candidates: list,
    top_n: int = config.TOP_K_RESULTS) -> list:
    """Just the re-ordered Documents, no scores. Thin wrapper around
    rerank_with_scores()."""
    return [doc for doc, _score in rerank_with_scores(query, candidates, top_n)]
