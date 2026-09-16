from pydantic import BaseModel, Field


class RagChapterInput(BaseModel):
    id: int = Field(..., ge=1)
    numeral: str | None = None
    title: str | None = None
    content: str = Field(..., min_length=1)
    contentOffset: int = Field(
        0,
        ge=0,
        description="Character offset in the full chapter when content is a segment.",
    )


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


class RagRegisterBookRequest(BaseModel):
    bookId: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)


class RagRegisterBookResponse(BaseModel):
    bookId: str
    title: str
    status: str
    passageCount: int


class RagChapterIndexStatusResponse(BaseModel):
    bookId: str
    chapterId: int
    passageCount: int
    status: str


class RagAskCitation(BaseModel):
    chunkIndex: int
    text: str
    similarity: float


class RagAskRequest(BaseModel):
    bookId: str = Field(..., min_length=1, max_length=128)
    chapterId: int = Field(..., ge=1)
    question: str = Field(..., min_length=2, max_length=2000)
    bookTitle: str | None = Field(default=None, max_length=300)
    chapterTitle: str | None = Field(default=None, max_length=300)
    chapterNumeral: str | None = Field(default=None, max_length=32)


class RagAskResponse(BaseModel):
    bookId: str
    chapterId: int
    question: str
    answer: str
    citations: list[RagAskCitation]


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
