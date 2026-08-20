# RAG UI

## API設定

`.env.example` を `.env.local` にコピーし、`NEXT_PUBLIC_SEARCH_API_URL` に検索APIのベースURLを設定します。ローカル開発ではWorkerの `http://localhost:8787` を使えます。本番公開時は、`NEXT_PUBLIC_SEARCH_API_URL` にWorkerの公開URLを設定してください。

画面は次のAPIを呼び出します。

```text
POST {NEXT_PUBLIC_SEARCH_API_URL}/api/v1/ask
{ "question": "質問文" }
```

レスポンスは `{ "answer": string, "sources": [{ "file_name": string, "page_number": number }], "found": boolean }` です。
