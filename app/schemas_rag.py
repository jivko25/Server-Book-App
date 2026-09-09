from pydantic import BaseModel, Field


class RagChapterInput(BaseModel):
    id: int = Field(..., ge=1)
    numeral: str | None = None
    title: str | None = None
    content: str = Field(..., min_length=1)


class RagIndexStartRequest(BaseModel):
    bookId: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)


class RagIndexBatchRequest(BaseModel):
    chapters: list[RagChapterInput] = Field(..., min_length=1, max_length=50)


class RagIndexRequest(BaseModel):
    """Legacy single-shot index — still supported for small books."""

    bookId: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    chapters: list[RagChapterInput] = Field(..., min_length=1, max_length=500)


class RagIndexStartResponse(BaseModel):
    bookId: str
    title: str
    status: str


class RagIndexBatchResponse(BaseModel):
    bookId: str
    batchPassageCount: int
    totalPassageCount: int
    status: str


class RagIndexResponse(BaseModel):
    bookId: str
    title: str
    passageCount: int
    status: str


class RagIndexStatusResponse(BaseModel):
    bookId: str
    title: str
    passageCount: int
    status: str
    errorMessage: str | None = None
