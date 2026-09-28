# Guardrail architecture and execution flow

This project has two different guardrails:

1. Safety guardrail (input/output content screening)
   - File: `hr_assistant/guardrails.py`
   - Purpose: block prompt injection, jailbreak attempts, unsafe content, leaked sensitive personal data, and identity override attempts.

2. Scope guardrail (retrieval filtering)
   - File: `hr_assistant/tools.py`
   - Purpose: prevent the agent from retrieving non-HR documents and keep irrelevant results from leaking into the answer.

Both are important, but the app’s main safety gate is the input/output guardrail pipeline defined in `hr_assistant/pipeline.py`.

---

## 1) Where the app calls the guardrail

### Entry point: Streamlit UI
File: `app.py`

The UI builds the assistant and sends user questions through the secure pipeline:

- `get_agent()`
- `build_hr_assistant()`
- `ask(agent, cache, question, thread_id=...)`

Relevant code path:

- `app.py` -> `ask(...)`
- `ask.py` is not a separate file; the request goes through the function in `hr_assistant/pipeline.py`

### CLI entry point
File: `main.py`

The command-line version does the same thing:

- `build_hr_assistant()`
- `ask(agent, cache, question)`

---

## 2) The actual request flow

File: `hr_assistant/pipeline.py`

### Function: `ask(agent, cache, question, thread_id="default-session")`
This is the main secure flow.

Execution steps:

1. `screen_text = thread_memory.input_text_for_screening(agent, question, thread_id)`
   - File: `hr_assistant/thread_memory.py`
   - Purpose: gather the current user question plus recent user messages for screening.

2. `input_ok, input_reason = check_input(screen_text)`
   - File: `hr_assistant/guardrails.py`
   - Function: `check_input(text: str)`
   - Purpose: block malicious or unsafe prompt text before any retrieval or model call.

3. If input is blocked:
   - `return INPUT_BLOCKED_MESSAGE`
   - constant defined in `hr_assistant/pipeline.py`
   - message: `I can't process that request — it was flagged by the input safety guardrail.`

4. If input passes:
   - check semantic cache
   - if a cached answer exists, return it immediately

5. Otherwise call the agent:
   - `message = thread_memory.invoke_agent(agent, question, thread_id)`
   - `answer = message.text`

6. `output_ok, output_reason = check_output(answer)`
   - File: `hr_assistant/guardrails.py`
   - Function: `check_output(text: str)`
   - Purpose: inspect the model’s final answer before it reaches the user.

7. If output is blocked:
   - `thread_memory.overwrite_answer(agent, thread_id, message, OUTPUT_BLOCKED_MESSAGE)`
   - `return OUTPUT_BLOCKED_MESSAGE`

8. If output passes:
   - `cache.store(question, answer)`
   - return the answer

This is the complete secure execution path for the app.

---

## 3) Safety guardrail implementation

File: `hr_assistant/guardrails.py`

### Function: `check_input(text: str)`
- Decorated with `@traceable(name="guardrail_check_input")`
- Delegates to `_check(text, "input")`

### Function: `check_output(text: str)`
- Decorated with `@traceable(name="guardrail_check_output")`
- Delegates to `_check(text, "output")`

### Helper function: `_check(text: str, direction: str)`
This is the shared guardrail gate.

Behavior:

- If `config.GUARDRAIL_PROVIDER == "none"`:
  - returns `(True, "guardrail disabled")`

- Otherwise it tries a LLM-based classification:
  - `_check_with_openai(text, direction)`

- If the provider raises an exception:
  - calls `_on_provider_error(direction, exc)`

### Helper function: `_check_with_openai(text: str, direction: str)`
This is the real content filter.

It does the following:

- gets a reusable safety model via `_safety_client()`
- builds a classification prompt
- asks the model to decide if the text is safe or unsafe
- expects structured output from a Pydantic model:
  - `_SafetyVerdict`
  - fields: `safe`, `reason`

The prompt explicitly checks for:

- prompt injection / jailbreak attempts
- unsafe or harmful content
- leaked sensitive personal data
- identity override attempts like:
  - “you are now X”
  - “pretend to be Y”
  - “from now on you are Z”

### Helper function: `_safety_client()`
This lazily creates the model used by the safety checks.

Execution:

- `from hr_assistant.llm import get_llm`
- `_safety_llm = get_llm().with_structured_output(_SafetyVerdict)`

This means both input and output checks reuse the same model and structured output schema.

### Helper function: `_on_provider_error(direction: str, exc: Exception)`
This handles provider failure without crashing the request.

Important behavior:

- input error -> fail closed
- output error -> fail open

Configured in `hr_assistant/config.py`:

- `GUARDRAIL_FAIL_OPEN_INPUT`
- `GUARDRAIL_FAIL_OPEN_OUTPUT`

So if the guardrail model is unavailable, the system either blocks the request or allows it depending on direction and config.

---

## 4) Config controls the guardrail behavior

File: `hr_assistant/config.py`

Relevant settings:

- `GUARDRAIL_PROVIDER = os.getenv("GUARDRAIL_PROVIDER", "openai")`
- `GUARDRAIL_FAIL_OPEN_INPUT`
- `GUARDRAIL_FAIL_OPEN_OUTPUT`
- `GUARDRAIL_HISTORY_TURNS`

These values decide whether the guardrail is active and how errors are handled.

### `GUARDRAIL_HISTORY_TURNS`
This is used in `thread_memory.input_text_for_screening(...)` so the input guardrail sees both:

- the current question
- recent prior user turns in the same thread

This helps catch multi-turn prompt injection attempts that look harmless one message at a time.

---

## 5) History/context used in input screening

File: `hr_assistant/thread_memory.py`

### Function: `input_text_for_screening(agent, question, thread_id)`
This packages the data used for the input guardrail.

It includes:

- current question
- recent user turns from the same conversation
- not assistant replies

This is intentional: the input guardrail screens user-origin content only.

---

## 6) Scope guardrail is different but also important

File: `hr_assistant/tools.py`

The project also has a retrieval security layer in the search tool.

### Function: `create_guarded_search_tool(...)`
This is the main search tool used in the secure agent path.

It ensures that:

- only HR policy categories can be retrieved
- results below a relevance threshold are rejected
- the agent cannot freely search unrelated business or noise documents

This is not the same as the `check_input` / `check_output` safety guardrail.

It is a retrieval-scope layer, separate from content safety.

---

## 7) Builder functions that create the guarded agent

File: `hr_assistant/pipeline.py`

### Function: `_build_guarded_assistant(collection_name, ingest_fn, checkpointer=None)`
This creates the real secure assistant stack.

It does:

- `config.check_api_keys()`
- bootstraps collection if needed
- loads vector store
- calls `create_reliability_agent(...)`
- attaches `create_guarded_search_tool(vector_store)`

### Function: `build_hr_assistant(checkpointer=None)`
Builds the secure HR-only assistant for the main app.

### Function: `build_reliability_assistant(checkpointer=None)`
Builds the mixed HR + noise corpus assistant for reliability demos and tests.

---

## 8) Minimal mental model

The app’s runtime flow is roughly:

`app.py` -> `build_hr_assistant()` -> `ask()` -> `check_input()` -> agent -> `check_output()`

The core guardrail functions are:

- `hr_assistant.pipeline.ask`
- `hr_assistant.guardrails.check_input`
- `hr_assistant.guardrails.check_output`
- `thread_memory.input_text_for_screening`
- `tools.create_guarded_search_tool`

The safety filter is model-based and content-based.
The scope filter is retrieval-based and policy-based.

Together they protect the user-facing flow from both:

- malicious prompt content
- unsafe or irrelevant retrieved information
