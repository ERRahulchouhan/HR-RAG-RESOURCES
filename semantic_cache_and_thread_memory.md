# Semantic cache and thread memory

This document explains why the project uses semantic caching and thread memory, where they are called from, and how they fit into the request flow.

---

## 1) Why semantic cache is used

The semantic cache is used to avoid repeating expensive work for near-duplicate questions.

In this project, a request goes through a full RAG pipeline:

- input guardrail
- semantic cache lookup
- retrieval from vector store
- reranking
- LLM answer generation
- output guardrail
- cache storage

This work is expensive in both time and cost. If the user asks a question that is semantically similar to a previous one, the app can return the old answer immediately instead of running the whole pipeline again.

Example:

- “How many annual leave days do I get?”
- “What is my paid annual leave entitlement?”
- “How much leave am I allowed each year?”

These are not identical strings, but they are near-duplicates. A semantic cache detects that similarity and reuses the prior answer.

### Where it is created
File: `hr_assistant/pipeline.py`

Function:
- `_build_guarded_assistant(...)`

Code:
- `return agent, SemanticCache()`

This happens when the app builds the guarded assistant.

### Where it is used
File: `hr_assistant/pipeline.py`

Function:
- `ask(agent, cache, question, thread_id="default-session")`

Relevant lines:
- `cached_answer = cache.lookup(question)`
- `cache.store(question, answer)`

This means the cache sits in front of the agent flow: it is checked before the model call, and populated after a valid answer is generated.

---

## 2) Semantic cache implementation

File: `hr_assistant/semantic_cache.py`

Main class:
- `SemanticCache`

Main methods:
- `lookup(self, question: str) -> str | None`
- `store(self, question: str, answer: str) -> None`

### `lookup()`
This method:

- gets fresh cache entries only (ignores expired ones)
- embeds the new question
- compares it against stored embeddings using cosine similarity
- returns the cached answer if the similarity exceeds `SEMANTIC_CACHE_THRESHOLD`
- otherwise returns `None`

### `store()`
This method:

- embeds the question
- stores the question, answer, embedding, and timestamp in memory
- keeps only a bounded number of entries using a deque

It is intentionally bounded and time-limited so the cache does not grow forever and does not serve stale answers after policy updates.

---

## 3) Why thread memory is used

Thread memory is used so the assistant can keep context across turns in the same conversation.

Without memory, each question would be treated as a completely fresh prompt. The agent would not know that the user earlier asked about leave, then followed up with a related question like:

- “What is the notice period during probation?”
- “And what about my notice period after maternity leave?”

The model needs relevant recent chat history to maintain conversation continuity.

This memory is not the same as the semantic cache:

- semantic cache = reuse prior answers for similar questions
- thread memory = remember earlier conversation turns for context

### Where it is used
File: `hr_assistant/pipeline.py`

Function:
- `ask(agent, cache, question, thread_id="default-session")`

It calls:
- `thread_memory.input_text_for_screening(agent, question, thread_id)`
- `thread_memory.record_turn(...)`
- `thread_memory.overwrite_answer(...)`
- `thread_memory.invoke_agent(...)`

This means memory is used both for the input guardrail and for preserving conversation context in the LangGraph agent.

---

## 4) Thread memory implementation

File: `hr_assistant/thread_memory.py`

Main responsibilities:

- preserve conversation state per thread
- provide the text used for input safety screening
- keep the conversation transcript for the agent
- record or overwrite the last answer in memory

Important helper:
- `input_text_for_screening(agent, question, thread_id)`

This function combines:

- current user question
- recent user-turn history
- metadata necessary for the guardrail check

This is used because the input guardrail should screen the current question together with recent conversational history, not just the latest message in isolation.

---

## 5) How they fit together in the app flow

The full flow is:

1. User sends a question from `app.py`
2. `ask()` in `hr_assistant/pipeline.py` starts
3. Input guardrail runs
4. Semantic cache lookup runs
5. If no cache hit, agent runs with thread memory
6. Output guardrail runs
7. If safe, answer is stored in semantic cache
8. Conversation turns are recorded in thread memory

The main call chain is:

- `app.py` -> `ask(...)`
- `hr_assistant/pipeline.py` -> `cache.lookup(...)`
- `hr_assistant/pipeline.py` -> `thread_memory.invoke_agent(...)`
- `hr_assistant/pipeline.py` -> `check_output(...)`
- `hr_assistant/pipeline.py` -> `cache.store(...)`

---

## 6) When to start reading

If you want to understand the runtime behavior quickly, start with:

1. `app.py`
   - this shows the entry point from the UI

2. `hr_assistant/pipeline.py`
   - this shows the core secure flow and where cache + memory are used

3. `hr_assistant/semantic_cache.py`
   - this explains how lookup and store work

4. `hr_assistant/thread_memory.py`
   - this explains how conversation context is maintained

5. `hr_assistant/guardrails.py`
   - this explains the safety gate around the request

---

## 7) In one sentence

The semantic cache reduces repeated work for similar questions, while thread memory preserves continuity across turns in the same conversation.
