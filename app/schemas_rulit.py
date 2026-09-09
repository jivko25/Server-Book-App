from pydantic import BaseModel, Field


class RulitFormatInfo(BaseModel):
    type: str
    sizeKb: int | None = None


class RulitDownloadInfo(BaseModel):
    url: str
    fileName: str


class RulitBookListItem(BaseModel):
    id: str
    title: str
    author: str
    language: str | None = None
    year: str | None = None
    genre: str | None = None
    rating: float | None = None
    coverUrl: str | None = None
    pageUrl: str
    formats: list[str] = Field(default_factory=list)
    epubSizeKb: int | None = None


class RulitCatalogResponse(BaseModel):
    page: int
    hasNext: bool
    items: list[RulitBookListItem]


class RulitBookDetail(RulitBookListItem):
    authors: list[str] = Field(default_factory=list)
    series: str | None = None
    synopsis: str | None = None
    formats: list[RulitFormatInfo] = Field(default_factory=list)
    download: dict[str, RulitDownloadInfo] = Field(default_factory=dict)


class RulitDownloadUrlResponse(BaseModel):
    bookId: str
    format: str
    url: str
    fileName: str
    resolvedUrl: str | None = None
