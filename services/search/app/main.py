from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, status

from app.config import Settings, get_settings
from app.schemas import (
    NO_INFORMATION_MESSAGE,
    AskRequest,
    AskResponse,
    SearchHit,
    SearchResponse,
    Source,
)
from app.services.gemini import GeminiService, GeminiServiceError
from app.services.supabase import (
    SupabaseServiceError,
    SupabaseVectorStore,
    get_vector_store,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="社内文書検索AI RAG API",
    version="0.1.0",
    description="Gemini Embedding + Supabase pgvector + Gemini回答生成のAPI",
)


@lru_cache
def get_gemini_service() -> GeminiService:
    return GeminiService(get_settings())


def _retrieve(
    request: AskRequest,
    settings: Settings,
    gemini: GeminiService,
    vector_store: SupabaseVectorStore,
) -> list[SearchHit]:
    embedding = gemini.embed_query(request.question)
    threshold = (
        request.match_threshold
        if request.match_threshold is not None
        else settings.rag_match_threshold
    )
    return vector_store.search(
        embedding,
        match_threshold=threshold,
        match_count=request.match_count,
    )


def _source_list(results: list[SearchHit]) -> list[Source]:
    unique_sources: list[Source] = []
    seen: set[tuple[str, int]] = set()
    for result in results:
        key = (result.file_name, result.page_number)
        if key not in seen:
            seen.add(key)
            unique_sources.append(
                Source(file_name=result.file_name, page_number=result.page_number)
            )
    return unique_sources


def _context(results: list[SearchHit], max_chars: int) -> str:
    sections: list[str] = []
    current_length = 0
    for index, result in enumerate(results, start=1):
        section = (
            f"[根拠{index}] ファイル名: {result.file_name} "
            f"ページ: {result.page_number}\n{result.content.strip()}"
        )
        if current_length + len(section) > max_chars:
            break
        sections.append(section)
        current_length += len(section)
    return "\n\n".join(sections)


def _service_unavailable(exc: Exception, detail: str) -> HTTPException:
    logger.error("RAG dependency failed: %s", type(exc).__name__)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/search", response_model=SearchResponse)
def search(
    request: AskRequest,
    settings: Settings = Depends(get_settings),
    gemini: GeminiService = Depends(get_gemini_service),
    vector_store: SupabaseVectorStore = Depends(get_vector_store),
) -> SearchResponse:
    try:
        return SearchResponse(
            results=_retrieve(request, settings, gemini, vector_store)
        )
    except (GeminiServiceError, SupabaseServiceError) as exc:
        raise _service_unavailable(exc, "検索サービスを利用できません") from exc


@app.post("/api/v1/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    settings: Settings = Depends(get_settings),
    gemini: GeminiService = Depends(get_gemini_service),
    vector_store: SupabaseVectorStore = Depends(get_vector_store),
) -> AskResponse:
    try:
        results = _retrieve(request, settings, gemini, vector_store)
        sources = _source_list(results)
        if not results:
            return AskResponse(
                answer=NO_INFORMATION_MESSAGE,
                sources=[],
                found=False,
            )

        answer = gemini.generate_answer(
            request.question,
            _context(results, settings.rag_max_context_chars),
        )
        return AskResponse(answer=answer, sources=sources, found=True)
    except (GeminiServiceError, SupabaseServiceError) as exc:
        raise _service_unavailable(exc, "回答サービスを利用できません") from exc
