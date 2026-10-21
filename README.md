# Reliable AI Sales Copilot

Decision-support copilot for FMCG field sales (SalesEasy-style take-home). A representative sends a plain-text field update. The app checks a small **verified** inventory table, returns a structured recommendation, and **escalates uncertain or high-impact cases for a human**. It does not authorize price changes, replenishment, or medical diagnoses.

This is **not** an autonomous commercial decision-maker.

**LLM disclosure:** the default (and only implemented) provider is a **mock**. There is no API key in this submission. Mock results **do not** validate real LLM behavior.

**Demo video (3–5 min):** [AI-Sales-Copilot-Demo.mov](https://drive.google.com/file/d/1UF2dB33_x-7vPL_p7NvWvJHrQBCnhrFO/view?usp=drive_link) — set Google Drive sharing to **Anyone with the link**.

## Prerequisites

- Python 3.13.5 (3.12+ compatible)
- FastAPI 0.128.2, Pydantic 2.13.5, pytest 9.0.2, HTTPX 0.28.1, Uvicorn 0.48.0
- Docker (optional, for the container)

## Install and run

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: `GET http://127.0.0.1:8000/health`
- Analyze: `POST http://127.0.0.1:8000/analyze`

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `INVENTORY_PATH` | `data/inventory.json` | Verified inventory file |
| `LLM_PROVIDER` | `mock` | Only `mock` is implemented |
| `FIELD_UPDATE_MAX_LENGTH` | `4000` | Max characters after strip |
| `RATE_LIMIT_PER_MINUTE` | `10` | Per-IP analyze limit |

Do not commit `.env`. Uvicorn bind address/port are CLI flags (`--host`, `--port`), not app settings.

## Architecture and request flow

One process (modular monolith): HTTP → schemas → inventory → LLM adapter → parse → evidence check → safety policy → JSON.

```
POST /analyze
  1. Validate AnalyzeRequest (extra fields forbidden, length cap)
  2. Rate-limit (10/min/IP, in memory)
  3. Load trusted inventory JSON
  4. Call LLM adapter (mock) with the field update delimited as untrusted data
  5. Parse JSON into AnalyzeResponse (exactly seven fields)
  6. Independently verify every verified_table claim against the file
  7. Apply deterministic review rules (can only escalate, never suppress)
  8. Return JSON, or a controlled 4xx/5xx
```

| Package | Role |
|---------|------|
| `app/main.py` | FastAPI app, 429 handler |
| `app/api/routes.py` | `GET /health`, `POST /analyze` |
| `app/api/rate_limit.py` | In-memory limiter |
| `app/schemas.py` | Request/response contract |
| `app/inventory/` | Strict records + JSON repository |
| `app/llm/` | Interface, prompt, **mock** adapter |
| `app/services/analysis.py` | Orchestration |
| `app/services/evidence.py` | Grounding (fail closed) |
| `app/services/safety.py` | Human-review policy |
| `app/services/signals.py` | Shared phrase detectors |
| `data/inventory.json` | Three fictional outlets |

## API

### `GET /health`

Liveness only. No secrets, no provider name.

```json
{"status": "ok"}
```

### `POST /analyze`

Request (only this field; extras → 422):

```json
{ "field_update": "Metro Fresh reports Cola 500ml is out of stock." }
```

Success response — **exactly** these seven keys:

```json
{
  "issue_category": "stockout",
  "urgency": "high",
  "evidence": [
    {
      "source": "field_update",
      "claim": "Metro Fresh reports Cola 500ml is out of stock.",
      "status": "reported",
      "record_id": null
    },
    {
      "source": "verified_table",
      "claim": "System inventory records 48 units of Cola 500ml at Metro Fresh.",
      "status": "conflicting",
      "record_id": "inv_metro_fresh_cola_500ml"
    }
  ],
  "recommended_next_action": "Verify the physical shelf and the inventory record before any replenishment decision.",
  "missing_information": ["When the shelf was last physically checked"],
  "needs_human_review": true,
  "review_reason": "Reported stockout conflicts with the 48-unit system inventory record."
}
```

Schema decisions:

- JSON field is `claim` (not `factual_claim`) to match the brief example.
- Inventory IDs stay stable (`inv_metro_fresh_cola_500ml`), not `INV-002`.
- `missing_information` is `[]` when nothing is missing; `review_reason` is `null` when review is false.
- Extra JSON keys are rejected (`extra="forbid"`).
- A stock quantity is **recorded inventory**, not proof of the physical shelf.

## Enums

| `issue_category` | Meaning |
|------------------|---------|
| `stockout` | Product reported or recorded unavailable |
| `damaged_product` | Damaged goods |
| `pricing` | Price / competitor claim |
| `delivery` | Delivery issue |
| `customer_safety` | Possible harm to a customer |
| `other` | Does not fit the above |
| `none` | No issue (ordinary update) |

| `urgency` | Meaning |
|-----------|---------|
| `low` | Can wait |
| `medium` | Needs attention this cycle |
| `high` | Time-sensitive if the issue is real |
| `critical` | Immediate (e.g. possible illness) |

| Evidence `source` | Meaning |
|-------------------|---------|
| `field_update` | What the representative reported (`record_id` must be null) |
| `verified_table` | A row from `data/inventory.json` (`record_id` required) |

| Evidence `status` | Meaning |
|-------------------|---------|
| `reported` | Claimed in the note, not independently proven |
| `verified` | Matches the trusted table |
| `conflicting` | Note and table disagree |
| `unverified` | Not backed by the table (e.g. competitor price) |

## Urgency vs human review

| | High urgency | Low/medium urgency |
|--|--------------|-------------------|
| **Review required** | Illness + damaged pack | Unsupported price-match demand |
| **Review not required** | Corroborated 0-unit stockout (Indiranagar) | Ordinary “shelf looks fine” visit |

- **Urgency** = how time-sensitive it is *if the issue is real*.
- **needs_human_review** = uncertainty or need for authorization.
- The model may raise concern. Application rules **never** turn a mandatory review off.

## Human-review rules (application code)

1. Damaged product **and** customer feeling unwell → review, urgency at least critical, no diagnosis.
2. Reported stockout **and** recorded units > 0 → review, mark table evidence `conflicting`.
3. Competitor discount / price-match demand → review, **do not authorize** a price change.
4. Prompt-injection text cannot mark a case resolved or skip review when a rule above applies.
5. “Major lost sales” without a number → ask for proof; do not invent a figure.

## Failure handling

| Situation | HTTP |
|-----------|------|
| Extra fields, empty text, over-long input | 422 |
| Over rate limit | 429 |
| Malformed / ungrounded model output | 502 |
| Provider not available | 503 |
| LLM timeout | 504 |

Messages are generic. Invalid model output is **not** repaired into a fake success. Logs record request id, outcome, and length — **not** the raw field update and **not** secrets.

## Rate limiting

Default **10 requests / minute / IP** (`RATE_LIMIT_PER_MINUTE`). Implementation is **in-memory**. It does **not** work across multiple processes or instances.

`GET /health` is not rate-limited.

## Tests and evaluation

```bash
source .venv/bin/activate
pytest -q
python evaluation/run_eval.py
```

- Pytest: **48 passed** (API, inventory, schemas, analysis, safety, including the five required scenarios). Scope is **mock + application rules**, not a live LLM.
- `evaluation/run_eval.py` writes `evaluation/results.md` from `evaluation/cases.json`: **8/8** on the **mock** provider. That does **not** establish real-provider reliability.
- Live LLM smoke tests: **not run** (no key).
- Public deploy: **verified** against [https://ai-sales-copilot-zkpu.onrender.com](https://ai-sales-copilot-zkpu.onrender.com) (`GET /health` and `POST /analyze`). See **Deployment status** below.

## Deployment status

**Public demo (no login, no API keys):** [https://ai-sales-copilot-zkpu.onrender.com](https://ai-sales-copilot-zkpu.onrender.com)

Verified on this host (not localhost):

- `GET https://ai-sales-copilot-zkpu.onrender.com/health` → `{"status":"ok"}`
- `POST https://ai-sales-copilot-zkpu.onrender.com/analyze` with Metro Fresh Cola 500ml stockout → 200, seven fields, `needs_human_review: true`

```bash
curl -s https://ai-sales-copilot-zkpu.onrender.com/health
curl -s https://ai-sales-copilot-zkpu.onrender.com/analyze \
  -H 'Content-Type: application/json' \
  -d '{"field_update":"Metro Fresh reports Cola 500ml is out of stock."}'
```

Provider is **mock**. Render free instances may sleep; the first request after idle can take ~30–60s.

Local Uvicorn is still valid for development. It does not replace this URL. Docker image build remains unverified (daemon not running).

## Demo video

[3–5 minute screen recording](https://drive.google.com/file/d/1UF2dB33_x-7vPL_p7NvWvJHrQBCnhrFO/view?usp=drive_link) (Google Drive). No evaluator login should be required; use **Anyone with the link**.

## Docker

```bash
docker build -t sales-copilot .
docker run --rm -p 8000:8000 sales-copilot
```

Then `GET /health` and `POST /analyze` as above.

The image was not run in this environment: the Docker **CLI** is installed, but the **daemon was not running** (`docker.sock` missing). Do not treat this README as proof of a live container until `docker build` and `docker run` succeed on your machine.

## Known limitations

- Mock LLM is scenario-based; it is not a production model.
- Stockout / injection detection uses shared phrase lists, not full NLU.
- In-memory rate limit is single-instance only.
- Inventory is three fictional rows; a quantity is not shelf truth.
- No real LLM adapter (no API key).

## Time spent

See `TIME_LOG.md`. The 120-minute phase table is a **plan**, not measured duration.

Planned timebox: **120 minutes**. Total actual elapsed time: *(record from a clock before final submission)*.

## AI-tool usage

The brief allows a coding assistant. **Cursor** was used in that role (lookup, boilerplate, and drafting). Architecture, schemas, safety/review rules, tests, evaluation, and the mock-vs-live limitation were specified and checked by me. Mock results were not treated as proof of a live LLM.
