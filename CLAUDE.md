# 立教大学将棋部サイト — Claude Code 向け運用メモ

要件・背景・実装状況は **`requirements.md` が唯一の正**（§0 実装状況サマリー / §11 SEO要件と実装状況）。
このファイルには毎セッション必要な運用情報だけを置く。作業ログや要件をここに追記しないこと。

## リポジトリ構成

```
.
├── requirements.md      # 要件定義書 + 実装状況（更新はこちらに）
├── data/confirmed/      # 確定データ（*.json、schema.jsonでCI検証）
├── scraper/             # Python製スクレイパー
├── site/                # Astro製の公開サイト本体
│   ├── src/layouts/BaseLayout.astro   # head メタ・共通ヘッダー/フッターの一元管理
│   ├── src/pages/{index,result/index,archives/index}.astro
│   └── public/{robots.txt,ogp.png,...}
└── .github/workflows/deploy.yml
```

## ビルド・デプロイ

- 公開URL: `https://rikkyo-shogi.github.io/site/`（Astro v6、`output:'static'`、`base:'/site'`）
- ローカル: `cd site && npm ci && npm run build`（確認は `npm run preview`）
- デプロイ: `main` への push で自動（`data/confirmed/**`・`site/**` の変更が対象）

## 触る際の注意

- ページのメタ情報（title/description/OGP等）は `BaseLayout.astro` の props で渡す。各ページに直接 meta を書かない
- `base: '/site'` があるため、URL生成は `import.meta.env.BASE_URL` / `Astro.site` 経由で行う（ハードコード禁止）
- Google Search Console の確認トークンは `BaseLayout.astro` に**設定済み**。プレースホルダに戻さない
- 見た目に関わる変更をしたら、ビルド出力の差分（body DOM / CSS）で意図しない変化がないか確認する
- 環境によって `.git/*.lock` が `rm` できないことがある（`mv` は可能）。git が `unable to unlink` 警告を出しても処理自体は成功していることが多いので、警告だけで失敗と判断しない
