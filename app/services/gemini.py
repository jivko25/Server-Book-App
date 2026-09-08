from __future__ import annotations

from google import genai
from google.genai import errors, types

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_CHAPTER_CHARS,
    MAX_OUTPUT_TOKENS,
    TEMPERATURE,
)

SUMMARY_SYSTEM_INSTRUCTION = (
    "You are a literary assistant for FOLIO, a premium audiobook app. "
    "Write concise chapter summaries in elegant literary prose. "
    "Always write the summary in the same language as the chapter text."
)

SUMMARY_USER_TEMPLATE = """Summarize this audiobook chapter in 2–4 sentences of literary prose.
Write the summary in the same language as the chapter text below
(e.g. Bulgarian text → Bulgarian summary, English text → English summary).
Use third person past tense. No bullet points, headings, or meta commentary.
Output only the summary text.

{context_block}
Chapter text:
\"\"\"
{chapter_text}
\"\"\"
"""


class GeminiConfigurationError(Exception):
    """Raised when the Gemini client is not configured."""


class GeminiQuotaError(Exception):
    """Raised when Gemini returns 429 RESOURCE_EXHAUSTED."""


class GeminiAuthError(Exception):
    """Raised when Gemini rejects the API key."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiUpstreamError(Exception):
    """Raised when Gemini returns a server-side failure."""


def _build_thinking_config(model: str) -> types.ThinkingConfig:
    """Gemini 3 uses thinking_level; 2.5 uses thinking_budget."""
    if "3." in model or model.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level="minimal")
    return types.ThinkingConfig(thinking_budget=0)


def _build_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured")

    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def _build_context_block(
    book_title: str | None,
    chapter_title: str | None,
    chapter_numeral: str | None,
) -> str:
    lines: list[str] = []
    if book_title:
        lines.append(f"Book: {book_title}")
    if chapter_numeral:
        lines.append(f"Chapter: {chapter_numeral}")
    if chapter_title:
        lines.append(f"Title: {chapter_title}")
    if not lines:
        return ""
    return "Context:\n" + "\n".join(lines) + "\n"


def _map_client_error(exc: errors.ClientError) -> Exception:
    code = exc.code
    if code == 429:
        return GeminiQuotaError(str(exc))
    if code in (401, 403):
        return GeminiAuthError(str(exc), status_code=code)
    if code >= 500 or code in (408, 502, 503, 504):
        return GeminiUpstreamError(str(exc))
    return GeminiUpstreamError(str(exc))


def generate_chapter_summary(
    chapter_text: str,
    *,
    book_title: str | None = None,
    chapter_title: str | None = None,
    chapter_numeral: str | None = None,
) -> str:
    trimmed_text = chapter_text.strip()
    if len(trimmed_text) > MAX_CHAPTER_CHARS:
        trimmed_text = trimmed_text[:MAX_CHAPTER_CHARS]

    context_block = _build_context_block(book_title, chapter_title, chapter_numeral)
    prompt = SUMMARY_USER_TEMPLATE.format(
        context_block=context_block,
        chapter_text=trimmed_text,
    )

    client = _build_client()
    config = types.GenerateContentConfig(
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=_build_thinking_config(GEMINI_MODEL),
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
    except errors.ClientError as exc:
        raise _map_client_error(exc) from exc
    except Exception as exc:
        raise GeminiUpstreamError(str(exc)) from exc

    summary = (response.text or "").strip()
    if not summary:
        raise GeminiUpstreamError("Gemini returned an empty summary")

    return summary
