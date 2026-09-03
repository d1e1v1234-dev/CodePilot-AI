# CodePilot AI — Backend

An AI-powered Python code review and bug-fixing agent. Users submit
Python code (pasted text or a code screenshot), and the backend
returns a structured review — bugs, security issues, performance
problems, and code-quality/best-practice violations — grounded in a
small retrieval-augmented knowledge base, with an optional automatic
fix that is statically validated before being returned.

## Features

- **Code review**: Gemini reviews submitted Python code and returns a
  structured list of issues, strengths, and an overall score.
- **RAG-grounded review**: Relevant excerpts from a local knowledge
  base (PEP 8, common Python errors, OWASP basics, FastAPI best
  practices) are retrieved via ChromaDB and given to Gemini as
  supporting context — not blindly appended, and not treated as
  ground truth to copy from.
- **Agentic workflow (LangGraph)**: Review, fix generation, and
  validation are orchestrated as a graph with a bounded retry loop
  (up to 2 retries) when a generated fix fails validation.
- **Automatic fix generation**: When issues are found, Gemini
  generates a corrected version of the code with an explanation of
  what changed.
- **Static validation of fixes**: Generated fixes are validated using
  Python's `ast` module (syntax check) and `ruff` (static analysis) —
  **not** by executing the code. See "What validation means" below
  for what this does and does not guarantee.
- **Screenshot → code extraction**: Upload a PNG/JPG/WEBP image of
  code and Gemini's multimodal capability transcribes it into text,
  with a confidence score and notes on any unreadable portions.

## Tech Stack

- **FastAPI** + **Uvicorn** — HTTP API
- **Pydantic** — request/response validation and structured LLM output
- **Gemini** (via `langchain-google-genai`) — code understanding,
  structured review/fix generation, and image-to-code extraction
- **ChromaDB** — local vector store for RAG
- **LangGraph** — orchestrates the review → fix → validate workflow
- **Ruff** — static Python analysis for fix validation
- **pytest** — test suite (all Gemini calls mocked, no live API calls
  needed to run tests)

## Folder Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app and routes
│   ├── config.py                  # env-based settings
│   ├── knowledge/                 # RAG source documents (Markdown)
│   │   ├── python_best_practices.md
│   │   ├── python_common_errors.md
│   │   ├── owasp_security_basics.md
│   │   └── fastapi_best_practices.md
│   ├── models/
│   │   ├── review.py              # review/fix/validation schemas
│   │   └── extract.py             # image-extraction schema
│   ├── services/
│   │   ├── gemini.py              # Gemini wrapper (text, structured, image)
│   │   ├── rag.py                 # ChromaDB indexing + retrieval
│   │   ├── review.py              # public entry point, invokes the graph
│   │   ├── validation.py          # AST + Ruff static validation
│   │   └── extract.py             # image -> code extraction service
│   └── agents/
│       ├── state.py               # typed LangGraph state
│       ├── graph.py               # compiled workflow
│       └── nodes/
│           ├── retrieve.py        # RAG retrieval node
│           ├── review.py          # Gemini review node
│           ├── generate_fix.py    # Gemini fix-generation node
│           ├── validate_fix.py    # static validation node
│           └── decision.py        # finalize + retry routing
├── scripts/
│   └── build_index.py             # one-time/on-demand RAG indexing
├── tests/                         # pytest suite
├── chroma_db/                     # generated vector store (gitignored)
├── requirements.txt
├── .gitignore
└── .env                           # not committed; see below
```

## Setup

```bash
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Environment configuration

Create a `.env` file in `backend/` with:

```
GEMINI_API_KEY=your_actual_api_key
```

Optional overrides (defaults shown are the confirmed-working values):

```
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
```

## Build the RAG knowledge index

Run once, and again any time you edit files in `app/knowledge/`:

```bash
python scripts/build_index.py
```

This embeds the knowledge documents and persists them to `chroma_db/`
(gitignored). The index is loaded from disk on every request — it is
**not** rebuilt per request.

## Run the backend

```bash
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`, interactive docs at
`http://localhost:8000/docs`.

## API Endpoints

### `GET /api/health`

Basic health check.

**Response:**
```json
{ "status": "ok", "service": "CodePilot AI Backend" }
```

---

### `POST /api/test-gemini`

Sends a raw text prompt to Gemini. Useful for verifying the API key
and model are configured correctly.

**Request:**
```json
{ "prompt": "Explain Python lists in one sentence." }
```

**Response:**
```json
{ "response": "A Python list is an ordered, mutable collection..." }
```

---

### `POST /api/review`

The core feature. Accepts Python code and returns a full review.

**Request:**
```json
{ "code": "def divide(a, b): return a / b" }
```

**What happens internally:**

1. **RAG retrieval** — relevant knowledge-base excerpts are retrieved
   from ChromaDB based on the submitted code.
2. **Gemini review** — the code + retrieved context are sent to
   Gemini, which returns a structured review (issues, strengths,
   overall score).
3. **Fix generation** — if issues were found, Gemini generates a
   corrected version of the code with an explanation.
4. **Static validation** — the generated fix is checked with `ast`
   (syntax) and `ruff` (lint/correctness rules), **without executing
   any code**.
5. **Retry loop** — if validation fails and a fix was actually
   changed, the workflow retries fix generation (feeding back the
   validation errors) up to 2 times before giving up.

All of the above is orchestrated as a LangGraph workflow
(`retrieve_context → review_code → generate_fix → validate_fix →
decision`, with a conditional retry edge back to `generate_fix`).

**Response:**
```json
{
  "summary": "The function performs division without validating the divisor.",
  "overall_score": 70,
  "issues": [
    {
      "severity": "medium",
      "category": "bug",
      "title": "Unchecked division by zero",
      "line": 1,
      "description": "The function does not validate whether 'b' is zero.",
      "recommendation": "Add a check for b == 0 before dividing."
    }
  ],
  "strengths": ["Concise implementation for valid inputs."],
  "sources": [
    { "name": "Python Common Errors", "relevance": 0.31 }
  ],
  "fixed_code": "def divide(a: float, b: float) -> float:\n    if b == 0:\n        raise ValueError(\"b must not be 0\")\n    return a / b\n",
  "fix_explanation": "Added a zero-division guard and type hints.",
  "validation": {
    "valid": true,
    "tool": "ruff",
    "messages": []
  },
  "retry_count": 0
}
```

`fixed_code`, `fix_explanation`, `validation`, and `retry_count` are
new fields on top of the original review response and are always
present, but `fixed_code`/`fix_explanation`/`validation` may be `null`
if no fix was needed or fix generation itself failed.

---

### `POST /api/extract-code`

Upload an image (PNG, JPG/JPEG, or WEBP; max 8MB) containing a
screenshot of code. Gemini's multimodal capability transcribes the
visible code.

**Request (curl):**
```bash
curl -X POST http://localhost:8000/api/extract-code \
  -F "file=@screenshot.png;type=image/png"
```

**Response:**
```json
{
  "code": "def divide(a, b):\n    return a / b\n",
  "language": "python",
  "confidence": 0.92,
  "notes": "Bottom-right corner of the image was slightly cropped."
}
```

The extracted code is **not** executed — it is returned as text only,
for the user to review and optionally submit to `/api/review`.

You can also test this endpoint interactively via Swagger:
1. Open `http://localhost:8000/docs`
2. Expand **POST /api/extract-code**
3. Click **Try it out**, choose an image file, click **Execute**

## ⚠️ What "validation" means here

`validation.valid: true` means the generated fix **passed static
analysis** — it is syntactically valid Python (via `ast.parse`) and
passed Ruff's lint checks. It does **not** mean the code was executed,
tested, or confirmed to produce correct runtime behavior. No
user-submitted or LLM-generated code is ever executed by this
backend. Runtime correctness (unit tests, execution, output
verification) is out of scope for the current implementation.

## Testing

```bash
pytest tests/ -v
```

All tests mock Gemini calls — no real API key or network access is
required to run the test suite. Tests cover:

- Fix generation output validation
- Static validation of valid and invalid Python code
- Retry-limit enforcement in the LangGraph workflow
- `/api/review` end-to-end shape / backward-compatibility
- `/api/extract-code`: unsupported file types, oversized files,
  successful extraction, and malformed Gemini responses

## Security notes

- API keys are never exposed in responses or logs; only generic error
  messages are returned to clients, with full details logged
  server-side only.
- Uploaded images are processed in memory and never written to disk.
- No user-submitted or AI-generated code is ever executed by the
  server.
- CORS is restricted to `http://localhost:5173` (the frontend dev
  server).