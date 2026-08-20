from __future__ import annotations

from google import genai
from google.genai import types

from app.config import Settings


class GeminiServiceError(RuntimeError):
    """Raised when Gemini cannot create an embedding or answer."""


class GeminiService:
    """Small adapter that uses Gemini for both embeddings and generation."""

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value():
            raise GeminiServiceError("GEMINI_API_KEY is not configured")

        self._settings = settings
        self._client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value()
        )

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, task_type="RETRIEVAL_QUERY")

    def embed_document(self, text: str, title: str | None = None) -> list[float]:
        return self._embed(text, task_type="RETRIEVAL_DOCUMENT", title=title)

    def _embed(
        self,
        text: str,
        *,
        task_type: str,
        title: str | None = None,
    ) -> list[float]:
        try:
            response = self._client.models.embed_content(
                model=self._settings.gemini_embedding_model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    title=title,
                    output_dimensionality=self._settings.embedding_dimensions,
                ),
            )
            embedding = response.embeddings[0]
            values = getattr(embedding, "values", None)
            if values is None and isinstance(embedding, dict):
                values = embedding.get("values")
            if not values:
                raise GeminiServiceError("Gemini returned an empty embedding")
            return [float(value) for value in values]
        except GeminiServiceError:
            raise
        except Exception as exc:
            raise GeminiServiceError("Gemini embedding request failed") from exc

    def generate_answer(self, question: str, context: str) -> str:
        system_instruction = (
            "あなたは社内文書検索システムの回答担当です。"
            "与えられた根拠だけを使って日本語で回答してください。"
            "根拠に答えがない、または判断できない場合は、"
            "必ず「該当する情報が見つかりません」とだけ回答してください。"
            "一般知識や推測で補わないでください。"
        )
        prompt = (
            f"質問:\n{question}\n\n"
            "検索で取得した根拠:\n"
            f"{context}\n\n"
            "根拠に沿った簡潔な回答だけを出力してください。"
        )
        try:
            response = self._client.models.generate_content(
                model=self._settings.gemini_generation_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.0,
                    max_output_tokens=800,
                ),
            )
            answer = (response.text or "").strip()
            return answer or "該当する情報が見つかりません"
        except Exception as exc:
            raise GeminiServiceError("Gemini answer generation failed") from exc
