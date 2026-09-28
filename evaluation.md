# Evaluation flow for the HR policy assistant

This document explains why the project has an evaluation script, how it works, and which functions are used in the end-to-end evaluation flow.

---

## 1) Why evaluation is used

The project is a RAG system with guardrails, retrieval, reranking, memory, and semantic caching. A basic app run proves the system can answer a few questions, but it does not prove the answers are correct or grounded in the actual policy documents.

The evaluation script checks the quality of the responses using a judge model.

It measures two things:

1. Correctness
   - Is the answer aligned with the verified HR policy reference?

2. Groundedness
   - Are the claims supported by the retrieved evidence/context?

This is important because a model can sound fluent while still making up facts or citing the wrong evidence.

---

## 2) Entry point

File: `hr_assistant/evaluation.py`

Main function:
- `run_evaluation()`

This is the main evaluator entry point.

It does the following:

- initializes LangSmith tracing
- creates or reuses the LangSmith dataset
- loads the vector store
- builds the guarded agent used by the app
- creates a semantic cache
- builds a retriever for evidence context
- runs each question through the production-like flow
- scores each answer with an LLM judge
- uploads the results to LangSmith

---

## 3) The evaluation call flow

### Function: `run_evaluation()`
File: `hr_assistant/evaluation.py`

This function is the top-level orchestrator.

Execution order:

1. `check_langsmith_tracing()`
   - from `hr_assistant/tracing.py`
   - logs whether LangSmith tracing is enabled for this run

2. `client = Client()`
   - LangSmith client for dataset and experiment upload

3. `dataset = _ensure_dataset(client)`
   - creates or reuses the dataset in LangSmith

4. `vector_store = load_vector_store(config.QDRANT_NOISY_COLLECTION_NAME)`
   - loads the mixed HR + noise corpus used in the app reliability flow

5. `agent = create_reliability_agent(get_llm(), [create_guarded_search_tool(vector_store)])`
   - builds the same secure agent structure used by the app and reliability demos

6. `cache = SemanticCache()`
   - sets up the semantic cache used in the live request flow

7. `retriever = get_retriever(...)`
   - builds a retriever with category filtering and candidate retrieval

8. `target(inputs)`
   - this is the per-example evaluation function that runs one question through the real flow

9. `judge = _judge_llm()`
   - builds the Groq judge model used to score answers

10. `correctness_evaluator` and `groundedness_evaluator`
   - create LLM-as-a-judge checks

11. `client.evaluate(...)`
   - runs the evaluation and uploads results to LangSmith

---

## 4) Dataset creation and reuse

File: `hr_assistant/evaluation.py`

Function:
- `_ensure_dataset(client: Client)`

This function checks whether the dataset already exists:

- if it exists, it reuses it
- if not, it creates one based on `TEST_CASES` from `hr_assistant/evaluation_dataset.py`

The dataset stores:

- question
- expected answer reference

This reference is used as the gold answer for correctness scoring.

---

## 5) Judge model

File: `hr_assistant/evaluation.py`

Function:
- `_judge_llm() -> ChatOpenAI`

This function builds the LLM judge using the Groq-compatible endpoint.

It reads:

- `config.GROQ_API_KEY`
- `config.JUDGE_MODEL_NAME`
- `config.GROQ_BASE_URL`

It then creates a `ChatOpenAI` client pointed at the Groq model.

This judge is used for both:

- correctness evaluation
- groundedness evaluation

---

## 6) Real example execution path

The per-question evaluator is the nested function inside `run_evaluation()`:

### Function: `target(inputs: dict) -> dict`
This runs a single question through the real secure app pipeline.

The logic is:

```python
question = inputs["question"]
answer = ask(agent, cache, question, thread_id=f"eval-{uuid.uuid4()}")
candidates = retriever.invoke(question)
top_chunks = rerank(question, candidates, top_n=config.TOP_K_RESULTS)
context = "\n\n".join(chunk.page_content for chunk in top_chunks)
return {"answer": answer, "context": context}
```

This means the evaluation does not call a simplified mock path. It runs the same secure request logic the app uses in production:

- `ask(...)` from `hr_assistant/pipeline.py`
- with the guarded agent and semantic cache
- plus rebuilt retrieval context for judging groundedness

This is the critical part: the evaluation measures the app behavior as it actually runs.

---

## 7) Where the secure flow is used

The evaluation uses:

- `ask(agent, cache, question, thread_id=...)`
- from `hr_assistant/pipeline.py`

That function internally runs:

- input guardrail: `check_input(...)`
- semantic cache lookup: `cache.lookup(question)`
- the agent invocation: `thread_memory.invoke_agent(...)`
- output guardrail: `check_output(...)`
- semantic cache store: `cache.store(question, answer)`

So the evaluator is not bypassing protection. It is testing the same guardrails and cache structure the app uses.

---

## 8) Groundedness evaluation

File: `hr_assistant/evaluation.py`

Function:
- `groundedness_evaluator(outputs: dict, **kwargs) -> dict`

This is used to check that the answer is supported by the retrieved evidence.

It calls:

```python
groundedness_judge(outputs={"answer": outputs["answer"]}, context=outputs["context"])
```

This means the judge inspects:

- the produced answer
- the retrieved context chunk set

and decides whether the answer is grounded in that evidence.

---

## 9) Correctness evaluation

File: `hr_assistant/evaluation.py`

This is created with:

- `create_llm_as_judge(prompt=CORRECTNESS_PROMPT, feedback_key="correctness", judge=judge)`

This evaluates whether the answer matches the human-verified reference answer in the dataset.

The dataset is defined in:

- `hr_assistant/evaluation_dataset.py`

---

## 10) LangSmith upload

The final step is:

```python
client.evaluate(
    target,
    data=dataset.name,
    evaluators=[correctness_evaluator, groundedness_evaluator],
    experiment_prefix="hr-policy-eval",
    description="HR policy assistant — correctness + groundedness (Groq gpt-oss-120b judge)",
)
```

This pushes the results into LangSmith so you can inspect:

- each example
- evaluator scores
- output text
- contexts used for groundedness
- experiment trends across runs

---

## 11) Which files are most important to read

Start here:

1. `hr_assistant/evaluation.py`
2. `hr_assistant/pipeline.py`
3. `hr_assistant/guardrails.py`
4. `hr_assistant/semantic_cache.py`
5. `hr_assistant/evaluation_dataset.py`
6. `hr_assistant/vector_store.py`
7. `hr_assistant/reranker.py`

---

## 12) Command to run

From the project root:

```bash
python evaluate.py
```

Or in the current environment:

```bash
& ".venv\Scripts\python.exe" evaluate.py
```

This runs the evaluation against the dataset and uploads the experiment to LangSmith.

---

## 13) In one sentence

The evaluation script is the quality gate: it sends real questions through the same guarded app flow, rebuilds the evidence used for retrieval, and scores the final answers for correctness and grounding using an LLM judge in LangSmith.
