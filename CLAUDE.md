# 立教大学将棋部サイト — Claude Code 向け運用メモ

要件・背景・データ仕様・実装状況は **`requirements.md` が唯一の正**（§0 実装状況サマリー / §5 フィールド正式定義 / §11 SEO要件と実装状況）。
このファイルには毎セッション必要な運用情報だけを置く。作業ログや要件をここに追記しないこと。

## リポジトリ構成

```
.
├── requirements.md      # 要件定義書 + データ仕様 + 実装状況（更新はこちらに）
├── ROADMAP.md           # 将来構想・未確定アイデア（確定したらrequirements.mdへ反映）
├── data/
│   ├── confirmed/       # 関東大会 確定データ（*.json、schema.jsonでCI検証。H01〜H16・H21〜R08）
│   ├── picture/         # 部内アルバム写真（H01〜H13の団体戦結果の原本。個人情報のためgitignore済み・未コミット、ローカルのみ）
│   └── shadan/
│       ├── confirmed/   # 社団戦 確定データ（*.json、shadan/schema.jsonでCI検証）
│       ├── schema.json
│       └── player.schema.json   # 個人レーティング用（本人同意者のみ利用・現状未使用）
├── scraper/              # Python製スクレイパー（fetch_kanto/fetch_shadan/build_shadan_history 等）
├── site/                 # Astro製の公開サイト本体
│   ├── src/layouts/BaseLayout.astro   # head メタ・共通ヘッダー/フッターの一元管理
│   ├── src/components/{TeamEvent,IndividualEvent,SeasonSection,LeagueTrend}.astro
│   ├── src/pages/{index,result/index,archives/index,shadan/index}.astro
│   └── public/{robots.txt,ogp.png,...}
└── .github/workflows/{deploy,validate,scrape}.yml
```

## ビルド・デプロイ

- 公開URL: `https://rikkyo-shogi.github.io/site/`（Astro v6、`output:'static'`、`base:'/site'`）
- ローカル: `cd site && npm ci && npm run build`（確認は `npm run preview`）
- デプロイ: `main` への push で自動（`data/confirmed/**`・`data/shadan/**`・`site/**` の変更が対象）
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
- 部の旧公式サイト（`www2.rikkyo.ac.jp/web/z4000060/homepage1/` 等、実在するURLだが関東連盟の公式サイトではない）
  由来のデータは `source_type: "club_html"`（出典ラベルは「(旧)部サイト」表示）
- `season.note`（string|null）でその年度の注記（新型コロナ等による開催中止等）をシーズン見出し直下に表示できる
- H01〜H13の対戦表（`kanto_table`、マス目）は写真からの読み取りを複数回試みたが精度不足（相互チェックで
  矛盾を複数検出）と判断し見送った。安易に再試行せず、必要なら人力での確認を依頼すること
- `schedule` が2件以上あると `TeamEvent.astro` が「1日目/2日目…」表示、1件以下は `event.date` にフォールバック。
  日付表記は「平成〇年〇月〇日」「令和〇年〇月〇日」（元年は「平成元年」「令和元年」、「1年」としない）
- 新しい `source_type` 値を使う場合は `data/schema.json` の enum への追記と `requirements.md` §5 の更新が必要
- ローカルでのスキーマ検証（関東）:
  `python3 -c "import json,jsonschema,sys; from pathlib import Path; schema=json.loads(Path('data/schema.json').read_text()); [print('FAIL',f.name) or sys.exit(1) for f in sorted(Path('data/confirmed').glob('*.json')) if list(jsonschema.Draft7Validator(schema).iter_errors(json.loads(f.read_text())))]"`
- ローカルでのスキーマ検証（社団戦）: 同様のワンライナーで `data/schema.json`→`data/shadan/schema.json`、`data/confirmed`→`data/shadan/confirmed` に置き換えて実行
- 社団戦の歴代成績は `scraper/build_shadan_history.py` の `RECORDS`（目視確認済みの確定値）から `data/shadan/confirmed/*.json` を生成する。修正時はこのファイルを編集して再実行すること（JSONを直接手編集しない）
- 個人（実名・レーティング）データは本人の同意がない限りリポジトリにコミットしない（`requirements.md` §5 の `shadan_pdf` 説明・ROADMAP §2-2）。gitignore済みの `data/auto/shadan/` にのみ出力する

## 既知の環境上の注意点

- 環境によって `.git/*.lock` が `rm` できないことがある（`mv` でのリネームは可能）。git が `unable to unlink` 警告を出しても処理自体は成功していることが多いので、警告だけで失敗と判断しない
