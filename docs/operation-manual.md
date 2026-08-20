# 公開ポートフォリオ運用手順書

最終更新: 2026-08-20

## 1. 目的・対象読者・構成

この手順書は、Cloudflare上で公開している小規模RAGポートフォリオを、初めて運用する人向けです。5件の教材PDFと12問のテストを使い、回答・出典・エラーを確認します。実文書、APIキー、INGEST_TOKENは公開しません。

| 役割 | 構成 |
|---|---|
| UI | 静的Next.js / Cloudflare Pages: https://104aec58.rag-portfolio.pages.dev |
| API | Cloudflare Worker: https://case3-rag-worker.yujianhuanggu636.workers.dev |
| DB | Cloudflare D1（本文・ページ番号・メタデータ） |
| ベクトル検索 | Cloudflare Vectorize |
| AI | Gemini API（Embedding・回答生成） |
| 取り込み | ローカルPython |

質問時はUIがWorkerの/api/v1/askを呼び、Workerが質問をEmbeddingしてVectorizeを検索し、D1からチャンクを取得してGeminiで回答します。取り込み時は、ローカルPythonがPDFを抽出・分割・Embeddingし、Workerの/api/v1/ingestへ送ります。公開ソースは https://github.com/sea-umi/rag-portfolio です。

## 2. 初回準備

Python、Node.js/npm、Wrangler、Gemini APIキー、INGEST_TOKEN、Cloudflareログインを用意します。対応バージョンは既存環境と合わせます（正確なバージョンは要確認）。

    git clone https://github.com/sea-umi/rag-portfolio.git
    cd rag-portfolio

    cd services/ingest
    python -m venv .venv
    & .venv/Scripts/Activate.ps1
    pip install -r requirements.txt
    cd ../worker
    npm install
    cd ../ui/web
    npm install

services/ingest/.env.exampleを.envへ、services/ui/web/.env.exampleを.env.localへコピーします。Wranglerのログイン状態や本番設定は要確認です。秘密値はファイル、Cloudflare Secret、環境変数で管理し、Gitへ登録しません。

## 3. フォルダの役割

| パス | 役割 |
|---|---|
| services/ingest | ingest.pyでPDF/Markdown/txtを抽出、ページ番号を保持して分割し、Gemini Embedding後にWorkerへ送るPython CLI |
| services/ui/web | Next.js App Routerの静的UI。Workerの質問APIを呼び、回答・出典を表示 |
| services/worker | 取り込み、Vectorize検索、D1取得、Gemini回答生成を行うCloudflare Worker |
| services/search | 旧・別実装。今回の公開Cloudflare構成では使用しない（整理は要確認） |

## 4. 環境変数

### 取り込み（services/ingest/.env）

| 変数 | 用途 |
|---|---|
| GEMINI_API_KEY | Gemini API。値は記載しない |
| GEMINI_EMBEDDING_MODEL | Embeddingモデル |
| GEMINI_EMBEDDING_DIMENSION | 実装は768 |
| CHUNK_SIZE / CHUNK_OVERLAP | 文字数ベースの分割。既定値は800/120 |
| RAG_WORKER_URL | WorkerベースURL |
| RAG_WORKER_INGEST_TOKEN | 取り込み認証。値は記載しない |

--upload-workerでは、CLIがRAG_WORKER_URLに/api/v1/ingestを付け、X-Ingest-Tokenで送ります。

### Worker・UI

WorkerのGEMINI_API_KEYとINGEST_TOKENはCloudflare Secretで管理します。D1/Vectorizeのバインディング、CORS_ORIGIN、モデル名はservices/worker/wrangler.tomlとCloudflare設定を確認します（実値は記載しません）。

UIの設定場所はservices/ui/web/.env.localまたはPagesの環境変数です。ブラウザへ公開されるNEXT_PUBLIC_はWorker URLだけに限定します。

NEXT_PUBLIC_SEARCH_API_URLはNext.jsの静的ビルド時にUIへ埋め込まれます。そのため、Pages側の環境変数の値だけを変更しても、既存サイトには反映されません。値を変更した場合は、必ずUIを再ビルドしてから再デプロイします。

    NEXT_PUBLIC_SEARCH_API_URL=https://case3-rag-worker.yujianhuanggu636.workers.dev

Geminiキー、INGEST_TOKEN、取り込みトークンはNEXT_PUBLIC_にしません。

今回公開しているWorkerの本番設定は、GitHubリポジトリ内のservices/worker/wrangler.tomlにあるプレースホルダー設定とは別に管理しています。本番のD1 ID、Vectorize ID、Worker設定、秘密情報はGitHubに書きません。リポジトリのwrangler設定をそのまま本番へデプロイしないでください。

### Pagesの手動デプロイ

今回のCloudflare Pages公開は、GitHub自動デプロイではなくWranglerによる手動デプロイです。Cloudflare PagesとGitHubの自動デプロイは未設定です。

Workers認証済みの状態で、リポジトリルートから次を実行します。

    cd services/ui/web
    npm ci
    npm run build
    cd ../../..
    npx wrangler pages deploy services/ui/web/out --project-name rag-portfolio --branch main

既存のPagesプロジェクトがある場合、プロジェクト作成は不要です。新規作成が必要な場合だけ、デプロイ前に `npx wrangler pages project create rag-portfolio` を実行します。NEXT_PUBLIC_SEARCH_API_URLを変更した場合も、上記の再ビルド・再デプロイを行います。

## 5. 新しいPDFの追加

1. 実文書PDFをGit管理外のローカルフォルダへ置きます。
2. services/ingestでJSONLを作ります。実装はpypdfでページ単位に抽出し、各チャンクへpage_numberを保持します。

    cd services/ingest
    python ingest.py C:\path\to\new-document.pdf -o chunks.jsonl
    python validate_jsonl.py chunks.jsonl

3. JSONLの行数と内容を確認します。画像だけのPDFは文字抽出エラーになります。OCRまたはテキスト版の作成方法は要確認です。
4. Embeddingを作り、Workerへ登録します。

    python ingest.py C:\path\to\new-document.pdf -o chunks.jsonl --upload-worker

このCLIはgemini-embedding-001（環境変数で変更可）と768次元を使います。Workerはcontent_hashをキーにD1へupsertし、その後Vectorizeへupsertします。登録後、D1の本文・ページ番号とVectorizeの件数・検索結果を確認します（Dashboardの表示名や件数は要確認）。

## 6. 更新時の注意

- 同じ内容はcontent_hashでupsertされますが、ファイル名や本文が変わると古いチャンクが残る可能性があります。
- 更新版へ差し替えるときは旧版をD1とVectorizeから削除して再登録します。削除用CLI/APIは実装にないため、具体的方法は要確認です。
- チャンク数が増えるほどGemini呼び出し、Worker通信、Vectorize/D1使用量が増えます。chunks.jsonlの行数を確認します。
- Geminiのレート制限・利用量とCloudflare無料枠を確認します。最新の上限・料金は公式Dashboardで要確認です。
- D1成功後にVectorizeが失敗することがあります。HTTP 500でも同じpayloadを再送できますが、両方の状態を確認してから再送します。

## 7. 12問の質問テスト

5件の教材PDFに対し、answerable質問、文書にない質問、出典表示、回答時間を含む12問を実施します。answerableは文書内の答えと回答が一致するか、文書にない質問はfound: falseと「該当する文書が見つかりませんでした」になるか、出典はファイル名・ページ番号が根拠候補と一致するか、回答時間は遅延やタイムアウトがないかを確認します。

公開UIまたは次のAPIで確認します。質問文は教材に合わせて置き換え、秘密値は送らないでください。

    $body = @{ question = '教材に記載された内容を質問する' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri 'https://case3-rag-worker.yujianhuanggu636.workers.dev/api/v1/ask' -ContentType 'application/json' -Body $body

12問の正確な問題文・期待値は実文書を公開しないため手順書に記載しません。結果はローカルの非公開記録へ保存します。

## 8. トラブルシューティング

| 症状 | 確認順 |
|---|---|
| 精度低下 | 質問が文書範囲内か、チャンクサイズ/重複、モデルと768次元の一致を確認 |
| 「該当なし」誤判定 | /api/v1/searchで候補があるか、match_thresholdが高すぎないか確認 |
| 出典不一致 | D1のfile_name・page_numberとVectorize metadata、旧版残存を確認 |
| API/Geminiエラー | URL、HTTPステータス、Workerログ、モデル名、キー有効性、利用上限を確認 |
| CORSエラー | ブラウザOriginとWorkerのCORS_ORIGIN、PagesからWorkerへの到達を確認 |
| Workerエラー | D1/Vectorize binding、migration、Secret、モデル名を確認 |

    Invoke-RestMethod -Method Get -Uri 'https://case3-rag-worker.yujianhuanggu636.workers.dev/health'

PDFエラーはpypdfの導入、テキストPDFかどうか、ページ抽出結果を確認します。ログの詳細表示方法はCloudflare設定により要確認です。

## 9. Cloudflare Dashboard

| 場所 | 確認対象 |
|---|---|
| Workers & Pages → Worker | デプロイ、Bindings、Secrets、Logs、エラー |
| Workers & Pages → D1 | document_chunksの件数・本文・ページ番号 |
| AI → Vectorize（場所は要確認） | インデックス、768次元、件数、検索 |
| Workers & Pages → Pages | 手動デプロイ、環境変数、ビルド、公開URL |
| Billing / Analytics | Cloudflare利用量、無料枠、料金 |

## 10. 漏えい時の対応

Gemini APIキーを失効・削除して再発行し、CloudflareのINGEST_TOKENも失効・再発行します。Worker Secretとローカル.envを更新し、Git履歴・ログ・画面共有に値が残っていないか確認します。必要なら漏えい期間のログと利用量を確認します。値そのものはこの手順書やチャットへ貼り付けません。

## 11. バックアップ・ログ・頻度・費用

教材PDF、生成JSONL、12問の結果、D1データは公開リポジトリと分離してバックアップします。秘密情報は混ぜません。Workerログは更新直後とエラー時に確認します。通常は月1回、またはPDF・依存関係・Cloudflare/Gemini仕様の変更時に12問を再実施します。費用はGeminiのEmbedding/生成回数、Worker、D1、Vectorizeの使用量で変わるため、無料枠と料金を定期確認します。

## 12. 現在の制約

- 認証未実装。ポートフォリオ向けで、一般利用者の認証・認可はない。
- 5件の教材PDFを使った小規模データ。
- Pagesは今回手動デプロイ。GitHub pushだけで自動公開される前提ではない。
- 出典は上位検索候補のファイル名・ページ番号を表示する仕様で、厳密な引用範囲の保証ではない。
- 国内リージョン保存の保証なし。今回は国内リージョン保存要件を適用しない。
- services/searchやSupabase関連ファイルは残っているが、今回の公開Cloudflare構成では使用しない。
- services/ui/README.mdには旧Supabase/FastAPI構成の説明が残っています。Cloudflare公開構成の運用時は、services/ui/web/README.mdとリポジトリルートのREADMEを参照します。

## 13. 運用チェックリスト

- [ ] 実文書、APIキー、INGEST_TOKENを公開していない
- [ ] .env、Worker Secret、Pages環境変数を正しく設定した
- [ ] UIのNEXT_PUBLIC_SEARCH_API_URLはWorker URLだけである
- [ ] JSONL作成後にvalidate_jsonl.pyを実行した
- [ ] ページ番号、チャンク数、D1、Vectorizeを確認した
- [ ] 重複登録と更新版の古いチャンクを確認した
- [ ] answerable質問、文書にない質問、出典、回答時間を12問で確認した
- [ ] /health、ログ、CORS、Geminiエラーを確認した
- [ ] Cloudflare無料枠とGemini利用量を確認した
- [ ] バックアップを更新した
- [ ] Pagesの手動デプロイ状態を確認した
- [ ] GitHubへのcommit/pushは承認後に行う（今回の作業では実施しない）

## 14. 今回の変更報告

変更対象はこのdocs/operation-manual.mdだけです。既存の簡易手順を活かしつつ、実装確認済みのservices/ingest/ingest.py、services/ingest/validate_jsonl.py、services/worker/src/index.ts、services/ui/web/app/page.tsxに合わせて書き直しました。

確認したコマンド・内容:

- python ingest.py ... -o chunks.jsonl
- python validate_jsonl.py chunks.jsonl
- python ingest.py ... -o chunks.jsonl --upload-worker
- WorkerのGET /health、POST /api/v1/askの形式
- services/workerのnpmスクリプトとservices/ui/webのbuild/typecheck定義

未確認事項:

- 実アカウントのCloudflare Dashboard上の件数、無料枠、ログ、Secretsの設定状態
- 実文書PDFの再取り込み結果と12問の実測回答時間
- 旧版チャンクの削除方法、OCR手順、各ツールの正確な対応バージョン
- Pagesの次回デプロイ手順と実環境のCORS設定

GitHubへのcommit/push、元課題フォルダ、Cloudflare本番設定は変更していません。
