from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    chapter_text: str = Field(
        ...,
        min_length=50,
        max_length=12000,
        description="Full or partial chapter text to summarize.",
    )
    book_title: str | None = Field(
        default=None,
        max_length=200,
        description="Optional book title for context.",
    )
    chapter_title: str | None = Field(
        default=None,
        max_length=200,
        description="Optional chapter title for context.",
    )
    chapter_numeral: str | None = Field(
        default=None,
        max_length=20,
        description='Optional chapter label, e.g. "Act I" or "Chapter 3".',
    )


class SummaryResponse(BaseModel):
    summary: str = Field(..., min_length=1)


class HealthResponse(BaseModel):
    status: str
    model: str


class ErrorResponse(BaseModel):
    detail: str
