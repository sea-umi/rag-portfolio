# case3-rag-worker

Gemini + D1 + Vectorize の社内文書RAG APIです。既定モデルは `gemini-embedding-001` / `gemini-3.6-flash` ですが、`GEMINI_EMBEDDING_MODEL` と `GEMINI_GENERATION_MODEL` の環境変数で変更できます。

## 初回設定

`case3-rag-db` の D1 ID（`26781bac-ed83-4181-bade-d5da9a0dff2b`）を設定済みです。Vectorize は `case3-rag-index`、768次元、cosine metricで事前作成してください。

```powershell
npm install
npx wrangler d1 migrations apply case3-rag-db --local
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put INGEST_TOKEN
npm run check
npm run dry-run
npx wrangler dev
```

本番 migration は `--remote`、デプロイは `npx wrangler deploy` です。文書登録は `POST /api/v1/ingest` に `X-Ingest-Token` を付けて行い、ブラウザUIからトークンを送らないでください。検索・質問のbodyは `{question, match_count?, match_threshold?}`、質問結果は `{answer,sources:[{file_name,page_number}],found}`、検索結果は `{results:[{id,file_name,page_number,chunk_index,content,similarity}]}` です。

## セキュリティと再実行性

Gemini APIキーはURLクエリではなく `x-goog-api-key` ヘッダーで送信します。`CORS_ORIGIN` を設定した場合は、そのOriginだけを許可します。本番では必ず `CORS_ORIGIN` を設定し、`INGEST_TOKEN` と併用してください。未設定時の `*` は開発用です。

ingestは `content_hash` をキーにD1をupsertするため、同じ文書チャンクを再送できます。処理順はD1登録（upsert）→Vectorize upsertです。D1成功後にVectorizeが失敗した場合、HTTP 500になっても同じpayloadを再送してください。逆にVectorize成功後の再送も安全です。D1とVectorizeは別サービスのため完全なトランザクションではなく、再送による補償を前提にしています。
