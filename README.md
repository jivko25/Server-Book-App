# FOLIO Backend API

Python backend for the FOLIO React Native audiobook app:

- **AI summaries** — Gemini proxy (`POST /api/summary`)
- **Rulit catalog** — metadata + download URLs (`GET /api/rulit/*`)

Deployable on **Vercel** (Hobby / free tier). Does **not** host or store EPUB files.

Production URL: `https://book-app-bice-phi.vercel.app`

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- `google-genai` SDK (summaries)
- `httpx` + `BeautifulSoup4` (rulit scrape)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/summary` | AI chapter summary |
| `GET` | `/api/rulit/catalog` | Browse rulit catalog |
| `GET` | `/api/rulit/search?q=` | Search rulit books |
| `GET` | `/api/rulit/books/{id}` | Book detail + download metadata |
| `GET` | `/api/rulit/books/{id}/download-url` | EPUB download URL |
| `GET` | `/docs` | Swagger UI |

### Rulit catalog

```
GET /api/rulit/catalog?lang=bg&page=1&sort=date&format=epub&genre=science-fiction
GET /api/rulit/search?q=хамлет&lang=bg&page=1
GET /api/rulit/books/319132
GET /api/rulit/books/319132/download-url?format=epub&resolve=false
```

All errors use FastAPI format: `{ "detail": "human readable message" }`

| Status | Meaning |
|--------|---------|
| `404` | Book not found |
| `422` | Invalid query/path params |
| `429` | Rate limited (rulit routes) |
| `502` | Rulit unreachable or HTML parse failed |

### AI summary

```json
POST /api/summary
{
  "chapter_text": "...",
  "book_title": "Hamlet",
  "chapter_title": "The Ghost Appears",
  "chapter_numeral": "Act I"
}
```

Summary is returned in the **same language** as `chapter_text`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Required for `/api/summary` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model |
| `ALLOWED_ORIGINS` | `*` | CORS origins (comma-separated) |
| `RULIT_BASE_URL` | `https://www.rulit.me` | Rulit base URL |
| `RULIT_CACHE_TTL_SECONDS` | `1800` | In-memory cache TTL (15–60 min) |
| `RULIT_RATE_LIMIT_PER_MINUTE` | `30` | Per-IP limit on `/api/rulit/*` |
| `RULIT_REQUEST_TIMEOUT_SECONDS` | `10` | Upstream scrape timeout |

## Cache behavior

- Catalog, search, book detail, and download URL responses are cached in memory
- TTL defaults to 30 minutes (`RULIT_CACHE_TTL_SECONDS=1800`)
- Book page URLs discovered from list/search are cached for faster detail lookups
- On Vercel serverless, cache is per-instance (still reduces scrape load significantly)

## Local development

```bash
cd Server-Book-App
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Run tests (mocked HTML fixtures — no live scrape in CI):

```bash
pytest
```

## Deploy on Vercel

1. Push to GitHub
2. Import in Vercel (Hobby plan)
3. Set `GEMINI_API_KEY` (+ optional vars above)
4. Deploy — zero-config FastAPI via `app/main.py`

## Mobile integration

```typescript
// Catalog browse
const res = await fetch(`${API_BASE_URL}/api/rulit/catalog?page=1&lang=bg`);
const { items } = await res.json();

// Import flow — mobile downloads EPUB itself
const dl = await fetch(`${API_BASE_URL}/api/rulit/books/${id}/download-url`);
const { url, fileName } = await dl.json();
// PendingImport { uri: url, format: 'epub', fileName }
```

## Legal note

Rulit content may be copyrighted. This API is a **metadata proxy** for personal use in the FOLIO app. The mobile client should display a disclaimer. Production may require a licensed catalog later.
