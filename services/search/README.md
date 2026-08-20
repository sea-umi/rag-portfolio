# 社内文書検索AI（RAG）API

Python / FastAPIで作る、社内PDF向けの検索・回答APIです。

- Embedding：Gemini API（`gemini-embedding-001`）
- 回答生成：Gemini API
- ベクトル検索：Supabase PostgreSQL + pgvector
- 出典：検索結果のファイル名・ページ番号をAPIレスポンスに含める
- 根拠がない場合：`該当する情報が見つかりません`

OpenAI APIとClaude APIは使用していません。

## 1. セットアップ

PowerShellの例です。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` に次の値を設定します。実際の値はチャットやGitへ貼り付けないでください。

```text
GEMINI_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

## 2. Supabaseの準備

Supabase SQL Editorで [`supabase/migrations/001_create_document_chunks.sql`](supabase/migrations/001_create_document_chunks.sql) を実行します。

Embeddingは768次元で登録するため、GeminiのEmbedding設定とSQLの `vector(768)` は変更しないでください。変更する場合は両方を同じ値にします。

## 3. PDF登録

PDFの本文をページ単位で抽出し、チャンク化してGemini Embeddingを作成し、Supabaseへ登録します。

```powershell
python scripts\ingest_pdfs.py --directory 文書
```

画像だけのPDF、パスワード付きPDF、複雑な表は今回のMVP対象外です。

## 4. API起動

```powershell
uvicorn app.main:app --reload
```

Swagger UIは <http://127.0.0.1:8000/docs> です。

### 検索

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/search `
  -Method Post -ContentType 'application/json' `
  -Body '{"question":"有給休暇は何日付与されますか？"}'
```

### 回答

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ask `
  -Method Post -ContentType 'application/json' `
  -Body '{"question":"有給休暇は何日付与されますか？"}'
```

回答レスポンスの例：

```json
{
  "answer": "入社6ヶ月経過後に10日付与されます。",
  "sources": [
    {
      "file_name": "case3-doc1-employment-rules.pdf",
      "page_number": 2
    }
  ],
  "found": true
}
```

検索結果が0件の場合、回答生成APIを呼ばずに `該当する情報が見つかりません` を返します。

## 5. テスト

```powershell
pytest
```

テストは外部APIを呼ばず、検索結果がない場合の固定文言と、回答にファイル名・ページ番号が含まれることを確認します。
