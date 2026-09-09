from pydantic import BaseModel, Field


class RagChapterInput(BaseModel):
    id: int = Field(..., ge=1)
    numeral: str | None = None
    title: str | None = None
    content: str = Field(..., min_length=1)


class RagIndexRequest(BaseModel):
    bookId: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    chapters: list[RagChapterInput] = Field(..., min_length=1, max_length=500)


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
