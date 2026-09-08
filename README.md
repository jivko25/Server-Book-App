# FOLIO Summary API

Thin Python backend proxy for the [FOLIO](https://github.com/) React Native audiobook app. Accepts chapter text from the mobile client and returns a short AI-generated literary summary via Gemini — keeping the API key server-side only.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- `google-genai` SDK
- Deployable on **Vercel** (Hobby / free tier)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check + configured model |
| `POST` | `/api/summary` | Generate chapter summary |
| `GET` | `/docs` | Swagger UI |

### `POST /api/summary`

**Request**

```json
{
  "chapter_text": "Full chapter text here…",
  "book_title": "Hamlet",
  "chapter_title": "The Ghost Appears",
  "chapter_numeral": "Act I"
}
```

**Response**

```json
{
  "summary": "Upon Elsinore's frost-bitten battlements…"
}
```

**Errors**

| Status | Meaning |
|--------|---------|
| `429` | Gemini free-tier quota exceeded |
| `401` / `403` | Invalid or unauthorized API key |
| `502` | Upstream Gemini failure |
| `503` | `GEMINI_API_KEY` not configured |

## Local development

```bash
cd Server-Book-App
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Test:

```bash
curl -X POST http://localhost:8000/api/summary \
  -H "Content-Type: application/json" \
  -d '{"chapter_text": "The ghost of the late king appeared on the battlements. Horatio and the guards were terrified. They resolved to tell young Hamlet."}'
```

## Deploy on Vercel (zero budget)

1. Push this repo to GitHub
2. Import project in [Vercel](https://vercel.com) (Hobby plan is free)
3. Add environment variable: `GEMINI_API_KEY`
4. Deploy — Vercel auto-detects FastAPI via `app/main.py`

Optional env vars in Vercel dashboard: `GEMINI_MODEL`, `ALLOWED_ORIGINS`.

## Gemini configuration

| Setting | Default |
|---------|---------|
| Model | `gemini-3.1-flash-lite` |
| Temperature | `0` |
| Thinking | disabled (`thinking_budget=0` / `thinking_level=minimal`) |
| Max output tokens | `512` |
| SDK retries | `1` attempt (no hidden retry storms on quota) |

## Mobile app integration (phase 3)

Point the React Native client at your deployed URL:

```typescript
const response = await fetch(`${API_BASE_URL}/api/summary`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    chapter_text: chapter.content,
    book_title: book.title,
    chapter_title: chapter.title,
    chapter_numeral: chapter.numeral,
  }),
});
```

Cache summaries locally in AsyncStorage to minimize API calls on the free tier.
