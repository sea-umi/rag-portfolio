# Gemini RAG文書取り込みCLI

PDF・Markdown・txtを抽出して設定可能なサイズで分割し、APIを呼ばない場合はJSONLへ出力します。`--upload`を付けた場合だけGemini Embeddingを作成し、Supabaseの`rag_documents`へ保存します。OpenAI/Claude APIは使用しません。

## セットアップ

```powershell
& .venv/Scripts/Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`に実際のGemini APIキー、Supabase接続情報、必要ならWorker接続情報を設定してください。`python-dotenv`により実行時に`.env`が読み込まれます。キーはGitへコミットしないでください。特に`SUPABASE_SERVICE_ROLE_KEY`と`RAG_WORKER_INGEST_TOKEN`は公開しないでください。

文書Embeddingと質問Embeddingは、必ず同じ`GEMINI_EMBEDDING_MODEL`と`GEMINI_EMBEDDING_DIMENSION`を使います。既定値は`gemini-embedding-001`・768次元で、Gemini APIへ`output_dimensionality=768`（環境変数の値）を明示します。

`rag_documents.sql`は既存環境との後方互換のため`vector(3072)`を維持しています。既存SQLを使う場合は`.env`の`GEMINI_EMBEDDING_DIMENSION=3072`へ戻してください。新規に既定値768でSupabaseへ保存する場合は、SQLの`vector(3072)`を`vector(768)`へ変更してから適用してください（既存3072テーブルへ768ベクトルは保存できません）。

## APIなしのテスト

```powershell
python ingest.py sample.md -o test-output.jsonl
```

実行結果はJSONLです。`sample.jsonl`は実際の生成結果ではなく、必須項目と形式を示す確認用サンプルです。`content_hash`も説明用の値です。

```powershell
python ingest.py 文書 -o chunks.jsonl --chunk-size 800 --overlap 120
python ingest.py 文書 -o chunks.jsonl --upload

# Workerへ1件ずつ送信（URL/tokenは.envのRAG_WORKER_*から取得）
python ingest.py 文書 -o chunks.jsonl --upload-worker

# APIなしの構造検証（空チャンク、必須キー、ページ番号を確認）
python validate_jsonl.py test-output.jsonl
# Embedding済みJSONLなら、embeddingの次元数（既定768）も検証します
python validate_jsonl.py chunks.jsonl
```

PDFが画像だけで文字抽出結果が空の場合はエラーにして、Markdown/txt版の用意を案内します。Supabaseへ保存する前に`rag_documents.sql`をSQL Editorで実行してください。

チャンクサイズは現在、トークン数ではなくPythonの文字数ベースです。講座の「500〜1,000トークン」とは異なるため、実運用ではトークン計測方式へ見直します。PDFはページ単位で抽出し、各チャンクに`page_number`を保持します。
