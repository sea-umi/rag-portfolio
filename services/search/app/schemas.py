from pydantic import BaseModel, Field, field_validator


NO_INFORMATION_MESSAGE = "該当する情報が見つかりません"


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="質問文")
    match_count: int = Field(default=5, ge=1, le=20)
    match_threshold: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("質問を入力してください")
        return value


class Source(BaseModel):
    file_name: str
    page_number: int = Field(..., ge=1)


class SearchHit(Source):
    chunk_index: int = Field(..., ge=0)
    content: str
    similarity: float = Field(..., ge=-1.0, le=1.0)


class SearchResponse(BaseModel):
    results: list[SearchHit]


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    found: bool
