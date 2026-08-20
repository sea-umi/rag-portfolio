from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path

from pypdf import PdfReader
from supabase import create_client

from app.config import get_settings
from app.services.gemini import GeminiService

LOGGER = logging.getLogger(__name__)
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def split_text(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + CHUNK_SIZE, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def iter_pdf_chunks(directory: Path):
    for pdf_path in sorted(directory.glob("*.pdf")):
        reader = PdfReader(str(pdf_path))
        for page_number, page in enumerate(reader.pages, start=1):
            for chunk_index, content in enumerate(split_text(page.extract_text() or "")):
                yield pdf_path.name, page_number, chunk_index, content


def ingest(directory: Path) -> int:
    settings = get_settings()
    if (
        not settings.supabase_url
        or not settings.supabase_service_role_key
        or not settings.supabase_service_role_key.get_secret_value()
    ):
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
        )

    gemini = GeminiService(settings)
    supabase = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
    )
    count = 0
    for file_name, page_number, chunk_index, content in iter_pdf_chunks(directory):
        content_hash = hashlib.sha256(
            f"{file_name}:{page_number}:{chunk_index}:{content}".encode("utf-8")
        ).hexdigest()
        embedding = gemini.embed_document(content, title=file_name)
        supabase.table("document_chunks").upsert(
            {
                "file_name": file_name,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "content": content,
                "content_hash": content_hash,
                "embedding": embedding,
            },
            on_conflict="content_hash",
        ).execute()
        count += 1
        LOGGER.info("登録: %s p.%s chunk=%s", file_name, page_number, chunk_index)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="PDFをGemini EmbeddingでSupabaseへ登録")
    parser.add_argument("--directory", type=Path, default=Path("文書"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    count = ingest(args.directory)
    LOGGER.info("登録完了: %sチャンク", count)


if __name__ == "__main__":
    main()
