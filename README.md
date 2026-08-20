# Cloudflare RAG ポートフォリオ

社内文書検索を題材にした、Cloudflare Workers / Vectorize / D1 と Gemini API によるRAG構成の教材用ポートフォリオです。

## デモ

- UI（Cloudflare Pages）: 未設定
- Worker API: `https://<your-worker-domain>`（公開可。実URLはデプロイ後に記載）

## 概要

ローカルでPDFをチャンキング・Embeddingし、Cloudflare Worker経由でVectorizeへ検索用ベクトルを登録します。質問時はVectorizeとD1から根拠を取得し、Gemini APIで回答を生成します。UIはNext.jsの静的出力をCloudflare Pagesへ配信する想定です。

## 構成

`docs/architecture.md` を参照してください。実装は `services/ingest`、`services/search`、`services/ui`、`services/worker` に整理しています。

## 起動方法

各サービスのREADMEと `.env.example` を確認し、ローカル環境変数を設定してから起動します。秘密情報は `.env` やCloudflareのSecretに保存し、Gitへ登録しません。

公開用の `services/worker/wrangler.toml` は安全な例示値のみを含みます。Cloudflareで利用する場合は、各自のWorker名・D1の`database_id`・Vectorizeのインデックス名などを設定してください。実アカウントの資源IDや秘密値は登録しないでください。

## Cloudflare構成

- Cloudflare Pages: Next.js静的出力のUI
- Cloudflare Workers: API、検索、登録処理
- Cloudflare Vectorize: Embeddingベクトル検索
- Cloudflare D1: 文書チャンクとメタデータ
- Gemini API: Embeddingと生成回答

## 制約と注意

- データは教材用の小規模な架空データです。
- 今回は国内リージョン保存要件を適用外としています。
- 認証はポートフォリオ向けに簡略化しており、本番利用の認可設計は未完了です。
- 実文書PDF、実データ、秘密情報はこのリポジトリに含めません。
- UIは `services/ui/web/app` 配下のNext.js App Router構成です。`npm ci` 後に `npm run build` で静的出力を生成できます。

## ライセンス

MIT License
