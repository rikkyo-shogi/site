# 立教大学将棋部サイト — Claude Code 向けプロジェクトメモ

このファイルはセッション開始時に自動で読み込まれる想定のメモです。プロジェクトの詳細仕様（データ収集方針・スクレイパー設計・受け入れ条件など）は `requirements.md` を参照してください。ここには **リポジトリの基本情報** と **直近の作業ログ（特にSEO対応）** をまとめます。

## リポジトリ構成

```
.
├── requirements.md      # 元の要件定義書（データ収集・サイト機能の詳細仕様）
├── data/                # スクレイパーが取得した確定データ（data/confirmed/*.json）
├── scraper/             # Python製スクレイパー（関東大学将棋連盟・掲示板）
├── site/                # Astro製の公開サイト本体
│   ├── astro.config.mjs
│   ├── src/
│   │   ├── layouts/BaseLayout.astro   # 共通レイアウト（後述）
│   │   ├── pages/{index,result,archives}/...
│   │   └── components/{SeasonSection,TeamEvent,IndividualEvent}.astro
│   └── public/{robots.txt,ogp.png,favicon.*}
└── .github/workflows/deploy.yml   # push→build→GitHub Pagesデプロイ
```

- 公開URL: `https://rikkyo-shogi.github.io/site/`
- フレームワーク: Astro v6.4.4、`output: 'static'`、`base: '/site'`
- サイトのビルド/確認: `cd site && npm ci && npm run build`（`npm run preview` でローカル確認可）
- デプロイ: `main` へのpushで `.github/workflows/deploy.yml` が自動ビルド・デプロイ（`data/confirmed/**` と `site/**` の変更が対象）

## 2026-07-17: SEO対策 フェーズ1・2 実装（完了・デプロイ済み）

サイトがGoogle検索にヒットしない問題を解消するため、以下を実装済み。コミット: `085f4c5`, `ae00232`（`main` にpush済み）。

**フェーズ1（クロール・インデックス対応）**
- `site/public/robots.txt` を新規作成（全ページ許可、sitemap所在を明記）
- `@astrojs/sitemap` を導入し、ビルド時に `sitemap-index.xml` / `sitemap-0.xml` を自動生成
- Google Search Console の所有権確認用 `meta name="google-site-verification"` を `BaseLayout.astro` に設置。**トークンは設定済み**（`qN0VQQih3Z4914kmqTSb8TKGqnw3QYmaQX6eDsmvnBo`）。TODOプレースホルダではないので、以後のセッションで再設定不要。

**フェーズ2（メタ情報の整備）**
- `site/src/layouts/BaseLayout.astro` を新規作成し、`<head>` 情報（title・description・canonical・OGP・Twitter Card・GSC確認タグ）を props 経由で一元管理する形に統一
- 既存3ページ（index / result / archives）を `BaseLayout` でラップし、ページ固有の description を設定
- トップページに `SportsOrganization` の JSON-LD 構造化データを追加
- OGP画像 `site/public/ogp.png`（1200×630）を新規作成
- 見た目・既存CSSは変更なし（ビルド差分で確認済み）

**Google Search Console の状況（2026-07-17時点）**
- プロパティ `https://rikkyo-shogi.github.io/site/` 登録・所有権確認 完了
- トップページ: インデックス登録済み確認
- result / archives ページ: 未インデックス（サイトマップの初回取得がデプロイ完了前のタイミングと重なり「取得できませんでした」表示。sitemap-index.xml 自体は直接アクセスで正常配信を確認済み。Googleの再クロール待ち、または個別に「インデックス登録をリクエスト」で手動対応中）

**未着手（フェーズ3・今後の課題）**
- 被リンク獲得（立教大学公式サークル一覧、関東大学将棋連盟サイト、部のSNSアカウントからのリンク）
- Core Web Vitals / PageSpeed Insights での確認（未実施、Astro静的サイトのため大きな問題は想定していない）

## 既知の環境上の注意点

- このリポジトリを操作する環境によっては、`.git/index.lock` 等のロックファイルが `rm` で削除できない（`mv` でのリネームは可能）ケースがある。通常のローカル環境では発生しないはずだが、`git` コマンドが `unable to unlink` の警告を出しつつも実際には正常に処理を完了していることがあるため、警告だけで失敗と判断しないこと。
