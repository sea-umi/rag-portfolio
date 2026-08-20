"""APIなしで取り込みJSONLの最低限の構造を検証する。"""
import json
import sys
import os
from pathlib import Path

REQUIRED = {"source", "chunk_index", "page_number", "metadata", "content", "content_hash"}

def main() -> int:
    if len(sys.argv) != 2:
        print("使い方: python validate_jsonl.py chunks.jsonl")
        return 2
    path = Path(sys.argv[1])
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError("レコードがありません")
    for number, record in enumerate(records, 1):
        missing = REQUIRED - record.keys()
        if missing:
            raise ValueError(f"{number}行目: 必須キー不足 {sorted(missing)}")
        if not record["content"].strip():
            raise ValueError(f"{number}行目: 空のcontent")
        if record["page_number"] < 1:
            raise ValueError(f"{number}行目: page_numberが不正")
        if "embedding" in record:
            dimension = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", "768"))
            if not isinstance(record["embedding"], list) or len(record["embedding"]) != dimension:
                raise ValueError(f"{number}行目: embedding次元数が不正です（想定: {dimension}）。")
    print(f"検証OK: {len(records)}件（必須キー・空チャンク・ページ番号・embedding次元数）")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
