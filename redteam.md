# Red team testing for the HR policy assistant

This document explains why the project uses a red-team test, how it works, and how to run it.

---

## 1) Why red-team testing is used

The app is a security-sensitive RAG system. It answers questions about HR policies, but it must also block:

- prompt injection / jailbreak attempts
- identity override attempts
- out-of-scope requests
- attempts to access confidential or non-HR documents
- social-engineering scope escapes

A normal happy-path test only checks whether the app answers legitimate HR questions. That is not enough.

The red-team test intentionally tries adversarial prompts to verify that the app behaves safely under attack.

This project includes a dedicated script:

- `redteam_test.py`

It tests both:

1. the plain baseline pipeline (no guardrail, no scope filter)
2. the guarded pipeline (the actual secure flow used by the app)

This gives a before/after comparison across the same prompt set.

---

## 2) What the script does

The script in `redteam_test.py` defines a list of attacks:

- `persona_override`
- `instruction_override`
- `roleplay_scope_escape`
- `social_engineering_scope_escape`
- `data_enumeration`
- `dan_jailbreak`
- `completely_off_topic`

For each attack, it runs:

- the plain pipeline (`ask_plain`)
- the guarded pipeline (`ask`)

The guarded pipeline also runs an explicit input guardrail check with:

- `check_input(prompt)`

This makes the saved output clearer: the script records whether the input guardrail passed or blocked the message.

After running, it saves the results to:

- `results/redteam_results.json`

This gives a structured machine-readable output for later analysis.

---

## 3) Files involved

### Main script
File: `redteam_test.py`

Main function:
- `main()`

This function does all the work:

- builds plain and guarded agents
- runs each adversarial prompt through both
- records the result in memory
- writes JSON to `results/redteam_results.json`

### Guardrail checks used by the test
File: `hr_assistant/guardrails.py`

Functions:
- `check_input(text: str)`
- `check_output(text: str)`

The test uses `check_input()` to record the reason for pass/block on the guarded path.

### Secure request flow
File: `hr_assistant/pipeline.py`

Functions:
- `build_plain_assistant()`
- `build_reliability_assistant()`
- `ask(agent, cache, question, thread_id=...)`
- `ask_plain(agent, question, thread_id=...)`

The red-team script calls the plain pipeline on the baseline, and the guarded pipeline on the secure flow.

---

## 4) Why the plain pipeline is included

The plain pipeline is intentionally stripped down. It does not include:

- input safety guardrail
- output safety guardrail
- scope guardrail
- semantic cache patterns used in the secure app

It exists as a control case: a baseline before/after comparison.

This lets you answer questions like:

- Did the guardrail really help?
- Did the model refuse the attack on its own?
- Does the app still fail when the protection layer is removed?

---

## 5) How to run it

First, ensure the data has been ingested at least once:

```bash
python ingest.py
```

Then run the red-team test:

```bash
python redteam_test.py
```

Or with the configured Python interpreter in this workspace:

```bash
& "C:/Users/rahul/AppData/Local/Python/pythoncore-3.14-64/python.exe" redteam_test.py
```

---

## 6) What output to expect

The script prints progress such as:

- `>>> Building plain pipeline agent (baseline — no guardrails)...`
- `>>> Building guarded pipeline agent (the deployed flow)...`
- `[GUARDED][data_enumeration] input_guardrail=BLOCK DONE`
- `Saved structured results to results\redteam_results.json`

It also logs the relevant guardrail decisions:

- `INPUT GUARDRAIL: block ...`
- `INPUT GUARDRAIL: pass ...`
- `OUTPUT GUARDRAIL: pass ...`

These lines tell you which prompts were rejected and which ones were allowed.

---

## 7) Results file

The structured results are written to:

- `results/redteam_results.json`

This file contains separate lists for:

- `plain`
- `guarded`

Each item includes:

- attack name
- prompt
- input_guardrail status
- input reason
- answer

This is useful for review, reporting, or regression testing.

---

## 8) Important note about runtime behavior

When running the script, you may see provider rate-limit errors from Groq/LiteLLM, such as:

- `RateLimitError`
- `code="rate_limit_exceeded"`

This is not necessarily a code bug. It means the model provider throttled the requests. The red-team script still runs and records the results, but repeated test runs can hit external API limits.

---

## 9) Why it matters in this project

This project is not just a chatbot. It is a structured, multi-layer security system:

- guardrails for prompt safety
- scope filtering for retrieval
- identity lock instructions
- semantic cache for repeated questions
- thread memory for conversation continuity

The red-team script checks whether these layers actually hold under adversarial prompts. It is the fastest way to verify the system is behaving as expected under attack.

---

## 10) Best way to use it

Use it:

- after changing prompts or guardrail logic
- after changing the retrieval/tool layer
- after changing model or provider settings
- before claiming the app is secure

A good pattern is:

1. run `python redteam_test.py`
2. inspect `results/redteam_results.json`
3. compare blocked vs allowed prompts
4. check whether the mutable layers are behaving as expected

---

## Summary

The red-team test is used to stress-test the assistant against adversarial prompts, not just normal usage. It helps verify whether the app still blocks jailbreaks, scope escapes, identity hijacks, and other risky inputs. The main command is:

```bash
python redteam_test.py
```

and the output is saved to:

- `results/redteam_results.json`
