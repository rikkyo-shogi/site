# 立教大学将棋部サイト — Claude Code 向け運用メモ

要件・背景・データ仕様・実装状況は **`requirements.md` が唯一の正**（§0 実装状況サマリー / §5 フィールド正式定義 / §11 SEO要件と実装状況）。
このファイルには毎セッション必要な運用情報だけを置く。作業ログや要件をここに追記しないこと。

## リポジトリ構成

```
.
├── requirements.md      # 要件定義書 + データ仕様 + 実装状況（更新はこちらに）
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
- スクレイピング作業の前に `requirements.md` §1.5.1 の到達確認を必ず実施（不達なら勝手にダミーデータで進めない）

## サイトを触る際の注意

- ページのメタ情報（title/description/OGP等）は `BaseLayout.astro` の props で渡す。各ページに直接 meta を書かない
- `base: '/site'` があるため、URL生成は `import.meta.env.BASE_URL` / `Astro.site` 経由で行う（ハードコード禁止）
- Google Search Console の確認トークンは `BaseLayout.astro` に**設定済み**。プレースホルダに戻さない
- 見た目に関わる変更をしたら、ビルド出力の差分（body DOM / CSS）で意図しない変化がないか確認する

## データを触る際の注意

- フィールドの意味・スキーマ定義は `requirements.md` §5「フィールド正式定義」が正（`kanto_table` の `wins`=勝数、`points`=勝点 など）
- 黒板写真・口頭情報など非公式ソースの手動入力は `source_type: "manual"`（出典ラベルは「部内記録」表示）。
  公式PDFが後から公開されたら `kanto_pdf` 等に戻し `source_url` を実URLへ更新する
- `schedule` が2件以上あると `TeamEvent.astro` が「1日目/2日目…」表示、1件以下は `event.date` にフォールバック。
  日付表記は「平成〇年〇月〇日」「令和〇年〇月〇日」
- 新しい `source_type` 値を使う場合は `data/schema.json` の enum への追記と `requirements.md` §5 の更新が必要
- ローカルでのスキーマ検証:
  `python3 -c "import json,jsonschema,sys; from pathlib import Path; schema=json.loads(Path('data/schema.json').read_text()); [print('FAIL',f.name) or sys.exit(1) for f in sorted(Path('data/confirmed').glob('*.json')) if list(jsonschema.Draft7Validator(schema).iter_errors(json.loads(f.read_text())))]"`

## 既知の環境上の注意点

- 環境によって `.git/*.lock` が `rm` できないことがある（`mv` でのリネームは可能）。git が `unable to unlink` 警告を出しても処理自体は成功していることが多いので、警告だけで失敗と判断しない
