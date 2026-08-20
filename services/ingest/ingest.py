"""Gemini Embedding + Supabase document ingestion CLI.

APIを呼ばないデフォルトでは、抽出・分割結果をJSONLへ出力します。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # APIなしの最小テストでも抽出・分割を実行できるようにする
    def load_dotenv() -> bool:
        return False

load_dotenv()


def extract_pages(path: Path) -> list[tuple[int, str]]:
    if path.suffix.lower() in {".md", ".markdown", ".txt"}:
        return [(1, path.read_text(encoding="utf-8"))]
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF抽出には pypdf が必要です。requirements.txtをインストールしてください。") from exc
        pages = [(number, page.extract_text() or "") for number, page in enumerate(PdfReader(str(path)).pages, 1)]
        if not any(text.strip() for _, text in pages):
            raise RuntimeError(f"PDFから文字を抽出できませんでした: {path.name}。Markdown/txt版を用意してください。")
        return pages
    raise ValueError(f"未対応の拡張子です: {path.name}（PDF/Markdown/txtのみ対応）")


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk_sizeは正数、overlapは0以上かつchunk_size未満にしてください")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind("。", start, end))
            if boundary > start + size // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def iter_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
    else:
        yield from sorted(p for p in input_path.rglob("*") if p.suffix.lower() in {".pdf", ".md", ".markdown", ".txt"})


def make_records(input_path: Path, size: int, overlap: int) -> list[dict]:
    records = []
    for path in iter_files(input_path):
        index = 0
        for page_number, text in extract_pages(path):
            for chunk in chunk_text(text, size, overlap):
                records.append({
                    "source": path.name,
                    "chunk_index": index,
                    "page_number": page_number,
                    "metadata": {"page_number": page_number},
                    "content": chunk,
                    "content_hash": hashlib.sha256(f"{path.name}:{page_number}:{chunk}".encode("utf-8")).hexdigest(),
                })
                index += 1
    return records


def embed(records: list[dict], model: str) -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEYが設定されていません。.env.exampleを参照してください。")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Gemini利用には google-genai が必要です。requirements.txtをインストールしてください。") from exc
    expected_dimension = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", "768"))
    if expected_dimension <= 0:
        raise RuntimeError("GEMINI_EMBEDDING_DIMENSIONは正の整数で指定してください。")
    client = genai.Client(api_key=api_key)
    for record in records:
        result = client.models.embed_content(
            model=model,
            contents=record["content"],
            config={"output_dimensionality": expected_dimension},
        )
        embedding = list(result.embeddings[0].values)
        if len(embedding) != expected_dimension:
            raise RuntimeError(
                f"Embedding次元数が想定外です: {len(embedding)}（想定: {expected_dimension}）。"
                "文書と質問で同じモデル・次元数を設定してください。"
            )
        record["embedding"] = embedding


def upload_worker(records: list[dict]) -> None:
    url = os.getenv("RAG_WORKER_URL")
    token = os.getenv("RAG_WORKER_INGEST_TOKEN")
    if not url or not token:
        raise RuntimeError("RAG_WORKER_URLとRAG_WORKER_INGEST_TOKENが必要です。.env.exampleを参照してください。")
    endpoint = url.rstrip("/") + "/api/v1/ingest"
    for number, record in enumerate(records, 1):
        payload = {key: record[key] for key in (
            "source", "page_number", "chunk_index", "content", "content_hash", "embedding"
        )}
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Ingest-Token": token, "User-Agent": "rag-ingest/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Worker ingest APIがHTTP {response.status}を返しました（{number}件目）。")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Worker ingest APIがHTTP {exc.code}を返しました（{number}件目）。") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Worker ingest APIへ接続できませんでした（{number}件目）: {exc.reason}") from exc


def save_supabase(records: list[dict]) -> None:
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URLとSUPABASE_SERVICE_ROLE_KEYが必要です。.env.exampleを参照してください。")
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("Supabase保存には supabase が必要です。requirements.txtをインストールしてください。") from exc
    create_client(url, key).table("rag_documents").upsert(records, on_conflict="content_hash").execute()


def main() -> int:
    parser = argparse.ArgumentParser(description="文書を分割し、Gemini EmbeddingをSupabaseへ保存します")
    parser.add_argument("input", type=Path, help="PDF/Markdown/txtファイルまたはフォルダ")
    parser.add_argument("-o", "--output", type=Path, default=Path("chunks.jsonl"), help="JSONL出力先")
    parser.add_argument("--chunk-size", type=int, default=int(os.getenv("CHUNK_SIZE", "800")))
    parser.add_argument("--overlap", type=int, default=int(os.getenv("CHUNK_OVERLAP", "120")))
    parser.add_argument("--upload", action="store_true", help="Gemini Embeddingを作成してSupabaseへ保存")
    parser.add_argument("--upload-worker", action="store_true", help="Gemini Embeddingを作成してWorkerへ1件ずつ送信")
    parser.add_argument("--model", default=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"))
    args = parser.parse_args()
    try:
        records = make_records(args.input, args.chunk_size, args.overlap)
        if args.upload or args.upload_worker:
            embed(records, args.model)
        if args.upload_worker:
            upload_worker(records)
        if args.upload:
            save_supabase(records)
        args.output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        destinations = (" Supabaseへ保存しました。" if args.upload else "") + (" Workerへ送信しました。" if args.upload_worker else "")
        print(f"{len(records)}チャンクを {args.output} に出力しました。" + destinations)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
