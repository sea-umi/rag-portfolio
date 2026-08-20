from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import Settings
from app.config import get_settings
from app.schemas import SearchHit


class SupabaseServiceError(RuntimeError):
    """Raised when Supabase cannot execute the vector search."""


class SupabaseVectorStore:
    def __init__(self, settings: Settings) -> None:
        if (
            not settings.supabase_url
            or not settings.supabase_service_role_key
            or not settings.supabase_service_role_key.get_secret_value()
        ):
            raise SupabaseServiceError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are not configured"
            )
        self._client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key.get_secret_value(),
        )

    def search(
        self,
        query_embedding: list[float],
        *,
        match_threshold: float,
        match_count: int,
    ) -> list[SearchHit]:
        try:
            result = self._client.rpc(
                "match_document_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": match_threshold,
                    "match_count": match_count,
                },
            ).execute()
            return [SearchHit.model_validate(row) for row in (result.data or [])]
        except Exception as exc:
            raise SupabaseServiceError("Supabase vector search failed") from exc


@lru_cache
def get_vector_store() -> SupabaseVectorStore:
    return SupabaseVectorStore(get_settings())
