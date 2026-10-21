# Engineering Time Log

**Project:** Reliable AI Sales Copilot  
**Timebox:** 120 minutes  
**Purpose:** Track implementation effort, verification, regression fixes, and submission readiness.

**Reporting convention:** The phase table below is a **120-minute plan**. Targets are planning estimates. They are **not** evidence that each phase took that long. Do not copy a target into an actual-time field.

| Phase | Target | Cumulative target | Scope and exit criteria |
|---|---:|---:|---|
| 1. Inspection and planning | 8 min | 8 min | Inspect the workspace, Python runtime, dependencies, and existing conventions. Establish the MVP architecture, constraints, and implementation priorities. |
| 2. Project foundation | 12 min | 20 min | Establish configuration, strict Pydantic schemas, enums, stable inventory records, and foundational import/schema tests. |
| 3. API and inventory | 12 min | 32 min | Implement `POST /analyze`, `GET /health`, request validation, inventory retrieval, configurable input limits, rate limiting, and API smoke tests. |
| 4. LLM integration and grounding | 18 min | 50 min | Implement the mock adapter, untrusted-input prompt boundaries, structured-output parsing, evidence validation, and controlled provider/output errors. Add a real provider only if API access is available and authorized. |
| 5. Safety and escalation | 15 min | 65 min | Implement deterministic, escalation-only review rules. Test the five required scenarios, evidence conflicts, commercial authorization boundaries, and prompt-injection resistance. |
| 6. Evaluation and regression improvement | 15 min | 80 min | Add missing-information, provider-failure, and normal-update tests. Run the reproducible evaluation suite. Identify a genuine weakness, preserve failing evidence, fix it, and rerun the affected tests. |
| 7. Documentation and packaging | 10 min | 90 min | Complete setup instructions, environment template, secret exclusions, API examples, safety policy, known limitations, AI-tool disclosure, and Dockerfile. Verify available local/container startup paths. |
| 8. Final technical verification | 5 min | 95 min | Run the full test suite and evaluation, verify the exact API response contract, scan for exposed secrets and unfinished critical paths, and record unresolved failures. |
| 9. Deployment and remote verification | 15 min | 110 min | Attempt deployment if access and infrastructure permit. Verify the actual public endpoint and basic safety controls, or document the specific blocker and mark the service `NOT DEPLOYED`. |
| 10. Demonstration and submission | 10 min | 120 min | Record a 3–5 minute demo if feasible. Verify video playback and access, publish the repository, confirm permissions, and assemble submission links and actual results. |
| **Total planned time** | **120 min** | **120 min** | **Hard deadline. Prioritize safety, test evidence, and truthful reporting over optional features.** |

## Actual execution record

Observed results only. Do not copy planned estimates into this table.

| Metric | Actual result |
|---|---|
| Total actual elapsed time | Pending — record the measured time before final submission. |
| Automated tests | **48 passed** (`pytest -q`, 2026-10-21). Scope: mock adapter + application rules (schemas, inventory, HTTP, evidence, safety). **Does not** establish that a live LLM integration works. |
| Evaluation scenarios | **8/8 passed**, mock provider (`evaluation/results.md`). Same scope as above. **Does not** validate OpenAI/Anthropic/Gemini. |
| Regression fix (REG-1) | Observed fail, then fix, then passing rerun. See **REG-1 evidence** below. |
| Live LLM smoke test | **Not run.** No API key. Mock only. |
| Docker build/run | **Blocked.** Docker CLI present; daemon not running (`docker.sock` missing). A Dockerfile is not a successful `docker build`. |
| Public deployment | **NOT DEPLOYED.** Open item. |
| GitHub repository and access | **Not published.** Open item. Folder is not a git repository yet. |
| Demo recording and access | **Not recorded.** Open item. |

## Open submission items

These are unfinished. Local run does not close them.

| Item | Status | Blocker / next step |
|---|---|---|
| GitHub repository | Open | `git init`, commit, push, confirm evaluator access if private. |
| Public demo URL | Open | Deploy after the repo exists. Verify the **deployed** `/health` and `/analyze`. |
| 3–5 min demo video | Open | Record after local or public run works; confirm playback and sharing. |
| Measured elapsed time | Open | Fill “Total actual elapsed time” from a clock, not from the plan table. |

## REG-1 evidence

**Input:** `Metro Fresh Cola 500ml is all gone, nothing left on the shelf.`

**Observed failure (before the fix):** `issue_category=other` because stockout detection only matched `out of stock` / `unavailable`. Confirmed in-session with `pytest tests/test_safety.py::test_paraphrased_metro_stockout_still_conflicts` (asserted `stockout`, got `other`).

**What is not preserved:** there is **no git history** and **no saved failing pytest log**. This note is the written record of that observation. Do not claim a red commit exists.

**Fix:** `app/services/signals.py` — phrases `all gone` and `nothing left`, used by the mock and the safety policy.

**Passing rerun (after the fix):** the same pytest name and eval case REG-1 in `evaluation/results.md` (8/8, mock).

## Delivery notes

- **Plan vs actual:** Phase targets are a schedule. They are not measured durations.
- **Test scope:** 48 pytest and 8/8 eval prove mock + app behavior. They do not prove a real provider.
- **Local Uvicorn:** `uvicorn app.main:app --host 127.0.0.1 --port 8000` shows the API **runs on this machine**. It is **not** a complete delivery fallback. Evaluators still need a cloneable repository and README setup. It does not replace a public URL or a demo video.
- **Deployment:** A local `/health` check does not establish public availability.
- **Containerization:** Dockerfile only; Docker daemon was not running.

**Final accounting:** Record measured elapsed time before final submission. Keep README and this file aligned: completed vs blocked vs unverified.
