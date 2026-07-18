# 立教大学将棋部 ホームページ 要件定義書

本ドキュメントは Claude Code に渡して実装してもらうための要件書です。
立教大学将棋部の公式サイトを作成し、以下2つの連盟サイトが公開する大会結果から
立教大学に関する成績を抽出・掲載することを目的とします。

- **関東大学将棋連盟**(地区大会): 全年度・全種別の個人戦・団体戦・女流戦・新人戦・選抜等。
- **全日本学生将棋連盟**(全国大会): 関東で好成績を収め全国大会へ出場した際の立教の成績。
- **過去掲示板アーカイブ**(部内記録): 部長らが投稿した団体戦の対戦相手別スコア・出場級・
  順位・(投稿によっては)個人別の勝敗など、連盟PDFには無い部内視点の記録。

---

## 0. 実装状況サマリー（2026-07-17 更新）

### 完了済み

| 項目 | 詳細 |
|------|------|
| **スクレイパー** | `fetch_kanto.py`・`fetch_bbs.py`・`parse_team.py`・`parse_individual.py`・`parse_bbs.py`・`integrate.py`・`update_kanto_tables.py` |
| **確定データ** | `data/confirmed/` に H21〜R08 の 18 年度分（77 イベント）を格納 |
| **団体戦テーブル** | `kanto_table` フィールドを 28 イベントに埋め込み済み（PDF/HTML/XLSX 全形式対応）|
| **複数日程** | `schedule` フィールド（`ScheduleDay[]`）を 12 イベントに埋め込み済み |
| **SSGサイト** | Astro によるサイト生成。全 18 年度分が表示される |
| **サイト表示** | 罫線・立教行黄色ハイライト・昇降級バッジ（順位列右）・複数日程表示 すべて実装済み |
| **バリデーション** | `data/schema.json` + CI (`validate.yml`) でスキーマ検証 |
| **GitHub Actions** | `deploy.yml`（push → GitHub Pages, Node.js 22）・`validate.yml`・`scrape.yml` 実働中 |
| **掲示板データ** | 13 イベントに `bbs_detail`（対戦相手別スコア）が付与済み |
| **公開** | **https://rikkyo-shogi.github.io/site/** で公開済み（Organization: rikkyo-shogi / repo: site）|
| **SEO（フェーズ1・2）** | robots.txt・sitemap自動生成・BaseLayout（description/canonical/OGP/Twitter Card/GSC確認タグ）・JSON-LD・OGP画像。詳細は §11 |
| **昇降級推移グラフ（ROADMAP §2-3）** | `loadData.ts` の `loadLeagueTrend()` で `data/confirmed` を集計。`LeagueTrend.astro`（Chart.js の stepped line）を大会結果ページ冒頭に配置。縦軸=リーグ名（C2〜A）、横軸=シーズン（H21春〜R08春）。昇級▲/降級▼/優勝★をマーカーで強調。データの無い半期（R02・H21秋 等）は x軸に残しつつ `spanGaps:true` で線を直線接続して表示（マーカーなし。フィードバックにより欠測を目立たせない方針に確定）。直近結果が昇級/降級の場合は次半期の所属リーグを点線＋中抜きマーカーで表示（グラフ内のみの表現とし、「予定」等の文字は凡例に出さない。ツールチップは「B1級(昇級による)」）。JS無効時は簡易テーブルにフォールバック。追加データ収集ゼロ |
| **社団戦パイプライン試作（ROADMAP §2-1/2-2）** | `scraper/fetch_shadan.py`＋`parse_shadan.py`（pdfplumber）で第34回（R07）を抽出。順位一覧PDFの2段組を座標で左右分割し（赤/白はヘッダー表記から取得）立教2チームの成績を取得 → `data/shadan/confirmed/R07.json`（`teams[]`、`league_table`は現状 null）。`source_type: shadan_pdf` を新設し `data/shadan/schema.json`＋`validate.yml` で検証（保存前にもスキーマ検証）。個人ランキングPDFは所属部から自動導出（第34回: 3部白=立教大学紫龍会14名 / 6部赤=紫龍会13名）し `data/auto/shadan/`（gitignore）にのみ出力・非公開。`site/src/pages/shadan/index.astro` で2チーム並列表示・出典PDFリンク付き、ナビに「社団戦」追加 |
| **社団戦 歴代成績（第12回〜33回）** | 資料形式が回ごとに異なるため（HTMLリーグ表→PDF・3リーグ制・3段組・オンライン開催等）、`scraper/build_shadan_history.py` に**目視確認済みの確定値**を保持しスキーマ検証つきで `data/shadan/confirmed/{H13..R06}.json` を生成（半自動＋目視方式）。判明した系譜: 立教大学紫龍会=第12回（H13）から参戦、第18回に**1部所属**（チーム史上最高）、第20回を最後に休会し第27回に3部で復帰（第31回以前は「立教大紫龍会」表記）。紫龍会=第15回から確認、第28〜32回休会、第33回に5部で復帰。第14回（H15）はリーグ表が連盟サイトに現存せず記録なし。第17〜21回は当該回の順位一覧PDF（例: `shadan/nana/page4.pdf`・`shadan/hachi/page1801.pdf`・`shadan/19/page1901.pdf`・`shadan/20/page2003.pdf`・`shadan/21/page2107.pdf`）を目視確認し全行の順位・勝点・勝数を確定（一部ファイルは名前列がテキスト抽出不可のため、対戦表内の略称参照から自チームの行を特定）。R02・R03の団体戦はコロナ禍で中止、第31回はR04にオンライン併用で開催（`31/rankingA4.pdf` から取得）。昇降欄の無い回の昇級/降級は翌回の所属部から判定し note に根拠を記録。shadanページの歴代成績はチーム別の列グループ（回×2チーム）で表示。出典リンクは各回の**リーグ表（成績順）**（第22回〜: `5nitimeseisekijun*.pdf` / `NN_league_04_g.pdf`。全ファイルの存在とチーム行の掲載を確認済み）。開催中の年度（第35回=R08、`status: "ongoing"`）は各節のリーグ表から途中経過を取り込み、ページ冒頭に単独表示（歴代テーブルには最終結果のみ）。ナビ・トップページの区分は「学生大会結果」「社団戦結果」に統一（掲示板アーカイブはナビのみ） |
| **社団戦 個人レーティング推移（保留中）** | 紫龍会・立教大学紫龍会の**出場者の個人レーティング（東将連公式・新持点）の推移を表示する**機能。一度実装したが「もう少し工夫できそう」とのフィードバックにより表示・データとも撤回（2026-07-18）。基盤（`scraper/build_shadan_players.py`・`data/shadan/player.schema.json`・CI検証枠）は将来の再実装用に維持。掲載は本人の同意を得た部員のみ・登録番号非表示の方針（§5）も維持。判明済みのデータ源: 第33回=全部門一覧PDF・第34回=部別PDF・第17〜20回（H18〜H21）=部別レーティング一覧HTML |
| **SNSリンク** | X / Instagram / note（いずれも rikkyoshogi）への公式ロゴアイコン（インラインSVG）を `BaseLayout.astro` のフッターに全ページ共通で表示 |
| **サイトカラー** | 立教大学のスクールカラー「紫紺」（公式VIガイドの指定は DIC 226。ガイドPDF実測の `#541a86` を採用）にヘッダー・見出し・リンク等を統一。出典: 立教学院デザインガイド（rec.rikkyo.ac.jp/designguide） |

### 未完了・残作業

| 項目 | 状態 |
|------|------|
| **全国連盟スクレイパー** | `fetch_national.py` 未実装。立教の全国出場実績は未確認 |
| **R02 データ** | 0件（コロナ禍による開催なし。要確認） |
| **一部年度の kanto_table 欠損** | H28秋・H22秋・H22春・H25春 等（PDF解析失敗または立教不在） |
| **個人戦データ** | R06 など一部年度で個人戦イベントなし（公式PDF取得済みだが未抽出） |

---

## 1. 背景・目的

- 関東大学将棋連盟(以下「関東連盟」)の公式サイトに、地区主催棋戦の結果が年度別に公開されている。
- 関東連盟で上位の成績を収めた大学・選手は、**全日本学生将棋連盟**(以下「全国連盟」)が
  主催する全国大会(学生王座戦・富士通杯/トリプルアイズ杯・学生名人戦・学生王将戦(十傑戦)・
  学生女流名人戦 等)へ出場する。
- 両サイトから**立教大学に関係する成績のみ**を抽出し、地区大会から全国大会までを一続きに
  追える立教大学将棋部の独自サイトとして見やすくまとめて公開する。
- あわせて、既にアーカイブ済みの過去掲示板へのリンクも掲載する。

---

## 1.5 実装方針(確定事項・最初に必ず読むこと)

以下は実装の前提。Claude Code はここを最優先で守ること。

### 1.5.1 実行環境とネットワーク
- スクレイピング(連盟サイト・掲示板へのアクセス)は **Claude Code の実行環境で直接行う**。
- **着手の最初に到達確認を行う**。次の3ドメインへ HTTP アクセスできるか確かめる:
  - `kantoshogi.web.fc2.com` / `gakurenshogi.web.fc2.com` / `d35s62fmhuthp2.cloudfront.net`
  - いずれかがブロックされる場合は、まずユーザーに「ネットワーク設定でこれらのドメインを
    許可する必要がある」と伝え、許可後に再開する。**勝手にダミーデータで進めない**。

### 1.5.2 公開タイミング
- **実データが揃うまで公開しない**。サンプル/空データでの公開はしない。
- ただし開発効率のため、コードは「データが0件でもビルドが落ちない」ように作る
  (空配列でもエラーにならず、各セクションは内部的に「データなし」を許容する)。
  これは**動作の堅牢性のためであり、空状態を公開してよいという意味ではない**。
- 公開は、受け入れ条件(§8)のデータ系項目を満たし、ユーザーが内容を確認・承認してから。

### 1.5.3 全国大会の扱い(重要)
- 全国大会(全国連盟)は**立教の出場実績が確認できた場合のみ**該当年度・大会を掲載する。
- **立教の全国出場実績は未確認**。実装時にまず全国連盟サイトを走査し、立教の登場有無を判定する。
  - 立教の記録が1件も無ければ、**全国大会の表示・セクションは作らない**(省略)。
    「記録なし」等のプレースホルダも置かない。
- したがって全国大会対応は**任意機能**。関東連盟+掲示板が主たるデータ源であり、
  全国大会はデータが存在した場合の追加と位置づける。

---

## 2. 収集対象範囲(確定事項)

### 2.1 対象年度 ― 全年度
連盟「大会結果」ページからリンクされる**全年度**を対象とする(計19年度)。

```
令和8年度(R08) / 令和7年度(R07) / 令和6年度(R06) / 令和5年度(R05) /
令和4年度(R04) / 令和3年度(R03) / 令和2年度(R02) / 令和元年度(R01) /
平成30年度(H30) / 平成29年度(H29) / 平成28年度(H28) / 平成27年度(H27) /
平成26年度(H26) / 平成25年度(H25) / 平成24年度(H24) / 平成23年度(H23) /
平成22年度(H22) / 平成21年度(H21)
```

各年度ページの URL 形式(拡張子が年度で混在する点に注意):
- 新しい年度: `http://kantoshogi.web.fc2.com/kekka/R08/R08kekka.html`
- 古い年度: `http://kantoshogi.web.fc2.com/kekka/H25/h25kekka.htm`(小文字・`.htm`)

年度一覧ページ内には前後年度への相互リンクがあるため、**起点ページから
リンクを辿って全年度ページを自動発見**する設計とする(年度 URL のハードコードに頼らない)。

### 2.2 対象大会 ― 全種別
立教が登場しうる**すべての大会種別**を対象とする。年度により開催種別・回数が異なる。
確認済みの種別(令和7年度=13大会の例):

- 春季個人戦 / 秋季個人戦
- 春季団体戦(A級/B級/C級)/ 秋季団体戦(A級/B級/C級)
- 春季女流戦 / 秋季女流戦
- 新人戦
- 東日本選抜トーナメント
- 関東オール学生個人戦
- 個人戦は年度により「選手権の部 / 奨励の部」に分かれる場合がある

PDF 命名規則は不規則(`R7harukojinkekka.pdf` / `R7shinnzinnkekka.pdf` /
`R7kantouorukozinnkekka.pdf` 等、ローマ字綴りが年度で揺れる)。
**ファイル名のパターン推測に依存せず、年度ページ内のリンクを実際に列挙して取得**する。

### 2.3 全国大会(全国連盟)― 対象年度・大会
全国連盟「大会記録」ページからリンクされる**全年度**を対象とする(2011〜2025年度、計15年度ぶん。
更新により増える)。立教が全国大会へ出場した年のみ成績が存在する。

対象大会(全国連盟の主要棋戦):
- 学生名人戦(個人・全国)
- 富士通杯争奪全国大学将棋大会 → 後継の **トリプルアイズ杯**(団体・大学対抗。年度で名称が変わる)
- 学生王座戦(団体・大学対抗の全国大会)
- 学生王将戦(十傑戦)(個人・全国)
- 学生女流名人戦(個人・全国)
- (年度により「個人総合成績」ページがある)

起点: `https://gakurenshogi.web.fc2.com/record.html`(年度別の大会記録一覧)。
補助: `https://gakurenshogi.web.fc2.com/champions.html`(2010年度以降の優勝者・優勝校一覧)。

### 2.4 立教が登場しない大会の扱い ― 立教関連のみ抽出
- **立教大学が出場・登場している成績のみを抽出して掲載**する(関東・全国とも共通)。
- 立教が含まれない大会・級は、データとして保持しなくてよい(記録に「該当なし」を残す程度で可)。
- 全大会の総合順位表や他大学の成績は掲載しない。
- 全国大会は立教の出場自体が稀なので、**出場した年・大会だけが掲載対象**になる
  (関東で上位入賞 → 全国出場、という流れを示せると望ましい。後述 6.2)。

---

## 3. データソース(重要な技術的制約)

### 3.1 関東連盟サイト(地区大会)
- 起点: `http://kantoshogi.web.fc2.com/`(「結果」→ 年度別ページ)
- **文字コードは Shift-JIS**。取得時に UTF-8 へ変換が必要
  (`requests` では `resp.encoding = "shift_jis"` 等で明示。`apparent_encoding` も併用)。
- **各大会の結果本体は原則 PDF**。HTML テーブルではない。
  - **団体戦 PDF**: 大学名 × 大学名のマトリクス(対戦表)+ 勝点・勝数・順位・入れ替え列。
    立教の行を特定し、所属級・順位・入れ替え(昇級/降級)を読む。
  - **個人戦 PDF**: トーナメント表。`氏名 (大学名+学年)` 形式(例: `青木 聖悟 (立教3)`)。
    テキスト抽出すると氏名・所属・学年がばらばらの順序で出力されやすい。
- **年度ごとの形式差が大きい**:
  - 古い年度は PDF 化されておらず HTML 直書きの場合がある。HTML テーブル形式のものは
    `kanto_html`、Excel(xlsx)形式のものは `kanto_xlsx` として扱う（H21〜H27 前後）。
  - 未公開大会・欠番 PDF による 404 が発生しうる。

**既知のパース上の注意点（実装済み対処を含む）:**
- HTML テーブルのデータ行に末尾の空文字列セルが混入することがある。stats 解析前に除去する。
- 一部年度（H23 等）はチーム名列ヘッダーが `''` ではなく `大学名` のため、スキップ対象に含める。
- 一部年度（H26秋 等）はシード列がなく、先頭セルが即チーム名（暗黙シード）である。
- PDF に `入れ替え` 列がある場合、pdfplumber が座標値（1000以上の float）をセル値として
  出力することがある。これは数値アーティファクトとして除去する。
- H27春は Excel（xlsx）形式。`parse_full_table_xlsx` で対応済み。

### 3.2 全国連盟サイト(全国大会)
- 起点: `https://gakurenshogi.web.fc2.com/record.html`(年度別一覧)。
  トップ `https://gakurenshogi.web.fc2.com/` にも直近年度の結果が掲載される。
- **ファイル形式が年度・大会で混在する**(関東連盟以上に不揃い):
  - 2023年度以降: 主に **PDF**(例 `record/2025/gakumei_result2025.pdf`)。
  - 2011〜2021年度頃: 主に **HTML** ページ(例 `record/2019/gakumei2019.html`)。
  - 一部に **xlsx / docx** や Google Drive リンク、トップページに**地の文(HTML本文)**として
    優勝者だけ記載されるケースもある。
- **ファイル名の綴りが不規則**:
  - 学生王座戦: `ouzasen` / `ouzasenn` / `ouza` / `ouzasen_result2024` / `ouzasen2_result2025`
  - 学生王将戦(十傑戦): `jikketsu` / `jukketsu` / `gakuseiosyo` / `gakuseiousyo`
  - 女流名人戦: `joryu` / `zyoryuu`
  - 富士通杯/トリプルアイズ杯: `fujitsu20xx` / `3-ize_result20xx` / `toripuru20xx`
  - → **ファイル名推測に依存せず、record.html 内のリンクを実際に列挙して取得**する。
- 文字コードは Shift-JIS の可能性が高いので関東連盟と同様にデコード処理する。
- HTML ページ・PDF・本文記載の3パターンすべてから立教を抽出できるようにする。
  立教が全国で上位なら本文の「優勝/準優勝/第三位」一覧にも載る。

### 3.3 立教抽出のキー
- 大学名は **「立教」** を含む文字列でマッチング。表記揺れ
  (`立教大学` / `立教大` / `立教` / `(立教3)` / `（立教大学3年）`)を正規化して吸収する。
- 全国大会では「(立教大学◯年)」のように**学年がカッコ書きで全角**になることがある点に注意。

### 3.4 過去掲示板アーカイブ(部内記録)― データソース兼リンク先
- トップ: `https://d35s62fmhuthp2.cloudfront.net/`
  - 現役部員掲示板: `https://d35s62fmhuthp2.cloudfront.net/rikkyo_shogi/rikkyoshogiclub/bbs.html`
  - OB会掲示板: `https://d35s62fmhuthp2.cloudfront.net/rikkyo_shogi_ob/poemfactory/bbs.html`
- **構造**(両掲示板共通):
  - 一覧は10件ずつ。ページURL は `bbs@page=N&.html`(N=2,3,…)。1ページ目は `bbs.html`。
  - **ページ下部のナビは前後数ページしか出さないスライド式**。最大ページ番号は表示されないので、
    総件数(「全352件」等)から **ページ数を算出**(= ceil(件数/10))して N を 1 から最後まで
    機械的に巡回する。リンクのクリックだけに頼らない。
  - 各投稿の個別ページは `bbs/NNN.html`(NNN=連番、例 358)。本文取得はこちらが確実。
  - 各投稿は「件名 / 投稿者 / 投稿日時 / 本文」。本文は**自由記述**。
  - 現役部員掲示板: 全352件(大会結果の主な情報源)。OB会掲示板: 全161件
    (総会・忘年会・合宿の連絡が中心で大会結果はほぼ無いが、念のため同様に巡回する)。
- **大会結果の記録のされ方(掲示板を全ページ確認した結果、複数の書式が併存)**:
  以下はすべて現役部員掲示板に実在する書式。パーサはこれらを正面から構造化対象とする。
  1. **団体戦・対戦相手別チームスコア**(記事358/383/384/385 等):
     「対○○大 4-3 勝ち」「対都市大 3-4 負け」+ 出場級「B2級で出場」+「最終順位は4位」。
     スコアは左が立教(§9 で確定)。日別(初日/2日目/最終日)に分割投稿されることもある。
  2. **回戦別の個人/小チーム戦績**(記事374 等):
     「4回戦 対 法政大C 2勝0敗(不戦勝1)」のように、回戦ごとに勝敗数と不戦勝/不戦敗を記載。
  3. **個人戦の個人別結果**(記事364「斎藤、二村、吉武 予選一回戦突破」、記事370「吉武が予選1回戦突破」等):
     **個人名**と成績(予選○回戦突破 等)が書かれる。新人戦・秋季個人戦など。
  4. **交流戦・古新戦など非公式の対外戦**(記事365/369/371/374 等):
     連盟非公式の練習試合。**抽出するのは日付と相手校のみ**(参加人数・形式・内容は不要)。
     ただし古新戦のように相手校別スコアや個人別戦績が明記されている回は、それも抽出してよい。
     公式戦と区別してタグ付けする(`is_official: false`。下記 §3.4 末尾)。
  - 「初日/中間報告」と「最終結果/最終日」が混在するので、**同一大会は最新・最終を採用**する。
  - 個人名つき戦績は確実に存在するため、`bbs_detail.players` は積極的に抽出する
    (取れないこともあるが「ほぼ取れない」わけではない)。
- **抽出の留意点**:
  - 大会結果の投稿は全件中の一部。新歓・合宿・総会・指導日など無関係な投稿が大半。
    → 件名・本文に「団体戦/個人戦/新人戦/結果/級/勝ち/負け/勝/負/優勝/順位/回戦/対」等の
    キーワードを含む投稿を候補抽出する(候補を広めに取り、後で人手確認)。
  - 書式は §上記の4類型に整理できるが、投稿者ごとの表記ゆれ(全角/半角、「勝ち」/「勝」/「○」、
    「対○○大」/「○○大学」)があるため、正規化を入れる。
  - **交流戦・古新戦など非公式戦も含め、掲示板に載っている大会はすべてサイトに掲載する**。
    ただし `is_official`(公式戦=連盟主催 / 非公式戦=交流戦・古新戦等)でタグ付けし、
    サイト表示では公式/非公式が区別できるようにする(ラベル等。省略はしない)。
  - 自動抽出後は**人手で確認・補正**して確定させる(§6.3)。書式が読めれば自動化率は高いが、
    最終的な正しさは人手確認で担保する。
  - 一部投稿に旧 Google サイト(`sites.google.com/site/rikkyoshogiclub/...`)へのリンクがあるが、
    現存しない可能性が高い。リンク先は深追いしない(取得できれば補助情報として利用)。
- 掲示板は**新サイトからのリンク先**でもある(後述 6.1)。閲覧専用アーカイブとしてそのまま案内する。

### 3.5 3ソースの突き合わせ方針
- 同じ団体戦について、**連盟PDF(公式の級・順位)と掲示板(対戦相手別スコア・部内コメント)**の
  両方が存在しうる。年度・シーズン(春/秋)・大会種別で名寄せし、可能なら統合表示する。
- 公式記録(連盟)を一次とし、掲示板由来の詳細(対戦相手別スコア・個人勝敗)は補足として付す。
- 出典は両方を併記する(どの情報がどのソース由来か分かるようにする)。

---

## 4. 公開先・ドメイン(確定: GitHub Pages 推奨)

独自ドメインは保有していないため、無料でサブドメインに「立教将棋」を示す文字列を
入れられる **GitHub Pages** を第一推奨とする。

- 形式例: `rikkyo-shogi.github.io`(GitHub 組織/ユーザー名がそのままサブドメインになる)。
  - 「rikkyo」「shogi」を含められ、立教将棋部であることを URL で示せる。
- 採用理由:
  - 完全無料・SSL 自動・静的サイトに最適。
  - リポジトリ push だけで自動デプロイでき、部の代替わり後も引き継ぎやすい。
  - 既存掲示板アーカイブ(S3+CloudFront)とは別系統だが、相互リンクで問題ない。
- 代替案(同等に可): Cloudflare Pages(`rikkyo-shogi.pages.dev`)、Netlify(`...netlify.app`)。
- 注意: `.ac.jp`(大学公式ドメイン)は大学の許可が必要で個人取得不可。将来部として
  大学公認を得た場合の移行を見据え、**URL 直書きを避け相対パス/ベースパス設定で構築**する。

**現状**: GitHub Actions ワークフロー (`deploy.yml`) は実装済み。GitHub リポジトリの作成と
`git push` はユーザー手動作業として残っている。

---

## 5. データ収集方針(半自動運用)

スクレイピングは Claude Code 実行環境で行う(§1.5.1)。ただし PDF のレイアウト崩れと
年度ごとの形式差により**完全自動での無人定期実行は信頼できない**ため、
「自動抽出 → 人手確認 → 確定」の半自動運用を前提に設計する。

1. **収集スクリプト**(Python)で:
   1. 関東連盟: 起点ページから全年度ページのリンクを発見 → 各年度の大会リンク(PDF/HTML/xlsx)を列挙。
   2. 全国連盟: `record.html` から全年度の大会リンク(PDF/HTML/xlsx/docx)を列挙。
      トップページ本文に直書きされた優勝者情報も拾う。
   3. 掲示板: `bbs.html` および `bbs@page=N&.html` を全ページ巡回し、各投稿(`bbs/NNN.html`)を取得。
      件名・本文に大会結果キーワード(団体戦/個人戦/結果/級/勝ち/負け/優勝/順位 等)を含む投稿を
      候補抽出し、対戦相手別スコア・出場級・順位・個人別勝敗・年月を構造化する。
   4. 各ファイルをダウンロードし、形式に応じて抽出
      (PDF=`pdfplumber`、HTML=`beautifulsoup4`、xlsx=`openpyxl`、いずれも Shift-JIS 対応)。
      docx は数が少なく優先度低。`python-docx` で読むか、無ければ手入力で補う。
   5. 各ソースとも「立教」を含む行・トークンを抽出(掲示板は立教視点なので主語省略に注意)。
2. 抽出結果を **§スキーマに従い正規化**し、`data/auto/<season>.json`(`confidence: "auto"`)へ出力。
   連盟由来と掲示板由来を年度・シーズン(`season_half`)・大会種別で名寄せして統合する。
3. 生PDF/HTML/xlsx/抽出テキストを `cache/` に保存し、人手確認時に突き合わせられるようにする。
4. 人手確認を経た `data/confirmed/<season>.json` のみをサイト生成に使う(§6.3)。

### 抽出 JSON スキーマ例

```json
{
  "season": "R08",
  "season_label": "令和8年度",
  "events": [
    {
      "level": "regional",
      "type": "team",
      "name": "春季団体戦",
      "division": "C級",
      "season_half": "spring",
      "date": "2026-05-24/2026-05-31",
      "venue": "東京理科大学神楽坂キャンパス",
      "source_url": "http://kantoshogi.web.fc2.com/kekka/R08/R8harudantaiCkekka.pdf",
      "source_type": "kanto_pdf",
      "rikkyo_present": true,
      "rikkyo_result": {
        "rank": 3, "wins": 5, "losses": 2, "points": 18,
        "promotion": "昇級", "note": ""
      },
      "schedule": [
        { "day": 1, "date": "5月24日", "venue": "東京理科大学" },
        { "day": 2, "date": "5月31日", "venue": "東京理科大学" }
      ],
      "kanto_table": {
        "division": "C級",
        "teams": ["立教大学", "○○大学", ...],
        "team_abbrevs": ["立教", "○○", ...],
        "rows": [
          {
            "seeding": 1,
            "team": "立教大学",
            "scores": [null, 4, 3, ...],
            "wins": 5,
            "points": 18,
            "rank": 3,
            "promotion": "昇級"
          },
          ...
        ]
      },
      "confidence": "confirmed"
    },
    {
      "level": "regional",
      "type": "individual",
      "name": "春季個人戦選手権の部",
      "date": "2026-05-10/2026-05-17",
      "venue": "東京理科大学神楽坂キャンパス",
      "source_url": "http://kantoshogi.web.fc2.com/kekka/R08/R8harukojinsensyukenkekka.pdf",
      "rikkyo_present": true,
      "rikkyo_players": [
        { "name": "青木 聖悟", "grade": 3, "best_result": "本戦出場", "rank": null }
      ]
    },
    {
      "_comment": "↓全国大会の例は説明用。立教の全国出場が実在するかは実装時に要確認(§1.5.3)",
      "level": "national",
      "type": "team",
      "name": "学生王座戦",
      "season_half": null,
      "date": "2025-12",
      "venue": "",
      "source_url": "https://gakurenshogi.web.fc2.com/record/2025/ouzasen2_result2025.pdf",
      "source_type": "national_pdf",
      "national_qualification": "関東秋季団体戦上位により全国出場",
      "rikkyo_present": true,
      "rikkyo_result": {
        "rank": null, "wins": null, "losses": null, "points": null,
        "promotion": null, "note": "予選リーグ敗退"
      },
      "confidence": "auto"
    },
    {
      "level": "regional",
      "type": "team",
      "name": "春季団体戦",
      "division": "B2級",
      "season_half": "spring",
      "date": "2016-05",
      "venue": null,
      "source_url": "https://d35s62fmhuthp2.cloudfront.net/rikkyo_shogi/rikkyoshogiclub/bbs/358.html",
      "source_type": "bbs",
      "rikkyo_present": true,
      "rikkyo_result": {
        "rank": 4, "wins": 4, "losses": 3, "points": null,
        "promotion": null, "note": ""
      },
      "bbs_detail": {
        "source_url": "https://d35s62fmhuthp2.cloudfront.net/rikkyo_shogi/rikkyoshogiclub/bbs/358.html",
        "is_official": true,
        "opponents": [],
        "matches": [
          { "opponent": "東京電機大学", "rikkyo_score": 4, "opponent_score": 3, "result": "勝ち", "round": null, "walkover": null },
          { "opponent": "芝浦工業大学", "rikkyo_score": 2, "opponent_score": 5, "result": "負け", "round": null, "walkover": null }
        ],
        "players": [],
        "comment": "秋団体戦までの課題: 終盤対策、棋力中間層の底上げ"
      },
      "confidence": "confirmed"
    }
  ]
}
```

注: `rikkyo_present: false` のイベントは原則 JSON に保存しない(§2.4)。
スクレイパが「立教なし」を検知した場合は、保存ではなく走査ログに記録する。

`level` は `"regional"`(関東連盟)/ `"national"`(全国連盟)。
全国大会のイベントには、可能なら `national_qualification`(どの地区成績で全国に出たか)を持たせ、
地区→全国の関連付けを表示できるようにする。
`bbs_detail` は掲示板由来の補足(対戦相手別スコア・回戦別戦績・個人別勝敗 `players`・部内コメント)。
`matches` のスコアは掲示板の慣習に従い **`rikkyo_score`(立教)= 左、`opponent_score`(相手)= 右**
として格納する(例「4-3」→ 立教4・相手3)。
連盟PDFが無く掲示板だけが情報源の年度は、`source_url` を掲示板記事にして単独で成立させてよい。

`schedule` は複数日程がある団体戦で使用する(`ScheduleDay[]`)。各要素は
`{ "day": int, "date": string|null, "venue": string|null }`。
HTML/xlsx ファイル先頭行付近から `1日目 ○月○日 於 ○○大学` 形式で抽出する。

掲示板由来の追加フィールド:
- `is_official`(bool): 連盟公式戦=true、交流戦・古新戦など非公式=false。
- `opponents`(array of string): 非公式戦で結果数値が無い場合の相手校名。
  例 `["東京農業大学"]`。スコアのある `matches` が取れる回はそちらを使い、`opponents` は空でよい。
- `matches[].round`(string|null): 「4回戦」等の回戦表記があれば格納(無ければ null)。
- `matches[].walkover`(object|null): 不戦勝敗があれば `{ "win": int, "loss": int }`。
- `players[]`: 個人名つき戦績。**書かれていれば必ず格納する**。
  `{ "name": string, "result": string|null, "wins": int|null, "losses": int|null, "board": string|null }`
  - 例: `{ "name": "吉武", "result": "予選1回戦突破" }`(記事370)
  - 例: `{ "name": "斎藤", "result": "予選一回戦突破" }`(記事364)
  - 個人名のみで姓のフルネームが不明な場合は書かれたまま格納し、個人情報配慮(§9)を適用。
- 非公式戦(`is_official: false`)は最低限 `date`(イベントの)+ 相手校(`opponents` か `matches`)が
  あればよい。参加人数・形式・内容は格納しない。

### フィールド正式定義(必ずこの定義に従う)

ファイル単位: **1年度 = 1 JSON ファイル**(例 `data/confirmed/R08.json`)。
ルートは `{ "season", "season_label", "events": [...] }`。`events` は0件でも可(空配列)。

| フィールド | 型 | 必須 | 説明・許容値 |
| --- | --- | --- | --- |
| `season` | string | ✓ | 年度キー。関東は `R08`〜`H21`、全国は西暦 `2016` 等。ファイル名と一致させる |
| `season_label` | string | ✓ | 表示用。`令和8年度` / `2016年度` |
| `events[].level` | enum | ✓ | `regional` \| `national` |
| `events[].type` | enum | ✓ | `team`(団体)\| `individual`(個人) |
| `events[].name` | string | ✓ | 大会名。`春季団体戦` `秋季個人戦` `学生王座戦` 等 |
| `events[].division` | string\|null | 団体のみ | 級。`A級` `B2級` `C級` 等。無ければ `null` |
| `events[].season_half` | enum\|null | – | `spring` \| `autumn` \| `null`(名寄せ用。春秋の判別) |
| `events[].date` | string\|null | – | 判明範囲で。`YYYY` / `YYYY-MM` / `YYYY-MM-DD` / 期間は `開始/終了`。不明は `null` |
| `events[].venue` | string\|null | – | 会場。不明は `null` か `""` |
| `events[].source_url` | string | ✓ | 一次情報の URL(連盟PDF/HTMLページ/掲示板記事のいずれか) |
| `events[].source_type` | enum | ✓ | `kanto_pdf` \| `kanto_html` \| `kanto_xlsx` \| `national_pdf` \| `national_html` \| `national_xlsx` \| `bbs` \| `manual` |
| `events[].rikkyo_present` | bool | ✓ | 立教が登場するか。`false` のイベントは原則保存しない(§2.4) |
| `events[].rikkyo_result` | object\|null | 団体 | 下記参照。個人イベントでは `null` |
| `events[].rikkyo_players` | array | 個人 | 下記参照。団体イベントでは省略可 |
| `events[].national_qualification` | string\|null | – | 全国出場の経緯(自動判定困難。手入力で可) |
| `events[].bbs_detail` | object\|null | – | 掲示板由来の補足。下記参照 |
| `events[].kanto_table` | object\|null | – | 全チーム対戦表（`update_kanto_tables.py` が自動追加）|
| `events[].schedule` | array\|null | – | 複数日程（`ScheduleDay[]`）。HTML/xlsx から自動抽出 |
| `events[].confidence` | enum | ✓ | `confirmed`(人手確認済み)\| `auto`(自動抽出のみ・未確認) |

- `manual` は黒板写真・口頭情報など非公式ソースの手動入力（サイト上の出典ラベルは「部内記録」表示）。
  公式PDFが後から公開されたら該当の `kanto_*` に変更し `source_url` を実URLへ更新する。
  enum を増やす場合は `data/schema.json` にも追記が必要。
- `shadan_pdf` は社団戦（東将連 社会人団体リーグ戦）PDF由来の `source_type`。関東学生団体戦とは
  名前空間を分離するため、上記の関東用 enum（`data/schema.json`）には**含めない**。
  データは `data/shadan/confirmed/RXX.json`、スキーマは `data/shadan/schema.json`（CI `validate.yml` で検証）。
  構造は `teams[]` 配列（`{ team_id, team_name, kai, division, rank, points, wins, promotion, source_type, source_url, league_table, note }`）。
  `team_id` は名称変更に備えた安定ID（例 `shiryukai_univ`＝立教大学紫龍会 / `shiryukai`＝紫龍会）。
  `league_table` は関東 `kanto_table` に準じた対戦表（順位一覧のみから作成時は `null`）。
  **個人ランキング（実名・レーティング）は原則リポジトリにコミットしない**（ROADMAP §2-2）。
  抽出物は gitignore 済みの `data/auto/shadan/` にのみ出力し、公開ページにも個人名を出さない。
  例外は**本人の同意（依頼）を得て公開すると決めた人のみ**: `data/shadan/players/<player_id>.json`
  （スキーマ `data/shadan/player.schema.json`、生成は `scraper/build_shadan_players.py`）にコミットし、
  shadan ページにレーティング推移を表示する。登録番号（reg_no）は内部キーでありページには表示しない。

`rikkyo_result`(団体): `{ "rank": int|null, "wins": int|null, "losses": int|null, "points": int|null, "promotion": "昇級"|"降級"|null, "note": string }`
- `wins`/`losses` は**チームマッチ単位**の勝敗数（「5勝2敗」表示用）。

`rikkyo_players[]`(個人): `{ "name": string, "grade": int|null, "best_result": string|null, "rank": int|null }`
- `best_result` は表示用の自由文字列だが、可能な範囲で次の語彙に寄せる:
  `優勝` / `準優勝` / `第三位` / `ベスト4` / `ベスト8` / `ベスト16` / `本戦出場` / `予選敗退` / `出場`。

`bbs_detail`: `{ "source_url": string, "is_official": bool, "opponents": [string], "matches": [...], "players": [...], "comment": string }`
- `matches[]`: `{ "opponent": string, "rikkyo_score": int|null, "opponent_score": int|null, "round": string|null, "walkover": {"win":int,"loss":int}|null, "result": "勝ち"|"負け"|"引分" }`
- `players[]`: `{ "name": string, "result": string|null, "wins": int|null, "losses": int|null, "board": string|null }`
  個人名つき戦績が投稿にあれば必ず格納(§3.4)。

`kanto_table`: `{ "division": string, "teams": [string], "team_abbrevs": [string], "rows": [...] }`
- `rows[]`: `{ "seeding": int, "team": string, "scores": [(number|null)], "wins": number|null, "points": number|null, "rank": int|null, "promotion": "昇級"|"降級"|null }`
- `rows[].wins` = **勝数**（個人戦局の合計勝利数、対戦表の「勝数」列）、
  `rows[].points` = **勝点**（チームマッチの勝利数、対戦表の「勝点」列）。
  `rikkyo_result` の `wins`/`losses`（チームマッチ単位）とは意味が異なる点に注意。
- `update_kanto_tables.py --force` で全年度を再処理できる。

`ScheduleDay`: `{ "day": int, "date": string|null, "venue": string|null }`

**重要**: スクレイパが出力した未確認データは `confidence: "auto"`。人手で確認したら `confirmed` に上げる。
**公開ビルドには `confirmed` のみ含める**(§1.5.2・§6.3 と整合)。

### リポジトリ / ディレクトリ構成（現在の実際の構成）

```
repo-root/
├─ scraper/                     # Python 収集スクリプト
│  ├─ fetch_kanto.py            # 関東連盟: 年度発見→大会リンク列挙→DL ✓
│  ├─ fetch_bbs.py              # 掲示板: 全ページ巡回→結果投稿候補抽出 ✓
│  ├─ parse_team.py             # 団体戦パーサ(PDF/HTML/XLSX) ✓
│  ├─ parse_individual.py       # 個人戦パーサ(トーナメント表) ✓
│  ├─ parse_bbs.py              # 掲示板パーサ(正規表現) ✓
│  ├─ parse_team_xlsx.py        # XLSX専用パーサ補助モジュール ✓
│  ├─ integrate.py              # 連盟+掲示板のイベント統合 ✓
│  ├─ run_kanto.py              # 関東連盟一括取得実行スクリプト ✓
│  ├─ update_kanto_tables.py    # kanto_table / schedule を confirmed に追記 ✓
│  ├─ common.py                 # Shift-JIS デコード/HTTP/キャッシュ/バリデーション ✓
│  └─ requirements.txt          # ✓
├─ cache/                       # 取得した生PDF/HTML/xlsx (gitignore)
├─ data/
│  ├─ schema.json               # JSON Schema ✓（kanto_table・schedule・ScheduleDay 含む）
│  ├─ auto/                     # スクレイパ出力(未確認) ✓ H21〜R08
│  └─ confirmed/                # 人手確認済み ✓ H21〜R08(18年度・77イベント)
├─ site/                        # Astro SSG ✓
│  └─ src/
│     ├─ components/
│     │  ├─ TeamEvent.astro     # 団体戦カード・kanto_table・schedule 表示 ✓
│     │  ├─ IndividualEvent.astro
│     │  └─ SeasonSection.astro
│     ├─ pages/
│     │  ├─ index.astro         # 大会結果ページ ✓
│     │  └─ archives/           # 掲示板アーカイブリンク ✓
│     └─ utils/
│        └─ loadData.ts         # confirmed/ 読み込み・型定義 ✓
└─ .github/workflows/
   ├─ deploy.yml                # push → GitHub Pages 自動デプロイ ✓
   ├─ validate.yml              # confirmed/ スキーマ検証 CI ✓
   └─ scrape.yml                # スクレイパ手動実行ワークフロー ✓
```

---

## 6. 機能要件

### 6.1 ページ構成(初版はシンプルに)
初版は次の2つがあれば十分。大会ごとにページを分けず、**年度ごとにまとめる**。

1. **大会結果ページ**: 全年度の立教の成績を**年度ごとにまとめて**一覧表示。
   - 1年度ぶんを1セクションとし、その中に関東公式戦(個人戦・団体戦・その他)・
     全国大会・**掲示板由来の大会(非公式の交流戦・古新戦を含む)**をまとめる。
     大会ごとに別ページを作る必要はない。
   - **掲示板に載っている大会はすべて掲載する**(非公式戦も省略しない)。
     公式戦と非公式戦はラベル等で区別する。
   - 全国大会の立教実績が存在する年度のみ、そのセクション内に全国の小見出しを追加する
     (実績ゼロなら全国の表示自体を出さない。§1.5.3)。
   - 年度の新しい順に並べ、ページ内リンク or 年度切替で各年度へ飛べるとよい。
2. **掲示板アーカイブへのリンク**: 現役部員掲示板・OB会掲示板アーカイブへのリンク。

将来的な拡張(部紹介・入部案内・連絡先・大会別詳細など)は任意。初版スコープには含めない。

### 6.2 表示要件
- 1年度のまとまりの中で、団体戦・個人戦・全国大会を見出しで区切って表示する。
- 団体戦は「大会(春秋)/ 級 / 順位 / 昇降級」を示す。掲示板由来の対戦相手別スコアは
  立教を左に揃えて表示(例「東京電機 4-3○ / 芝浦 2-5● …」、左が立教)。
  個人別勝敗があればその下に折りたたみ等で添える。
- 個人戦・その他は「大会 / 氏名 / 学年 / 成績(順位 or ベスト◯/出場)」を示す。
- **交流戦・古新戦などの非公式戦も掲載する**が、載せるのは「いつ・どこの大学と行ったか」の
  事実のみ(日付+相手校)。参加人数・対局形式・内容・感想などは載せない。
  「交流戦」「非公式」等のラベルを付け、公式戦と混同しない形で表示する。
  ※古新戦のように相手校別スコアや個人別戦績が明記されている回は、それも表示してよい
  (交流戦で結果数値が無い回は日付+相手校だけでよい)。
- 全国大会は実績がある年度のみ「全国」バッジで区別して表示。可能なら
  「関東◯◯戦 上位 → 全国◯◯戦 出場」を年度内で示す(実績ゼロなら全国表示は出さない)。
- 各結果に**出典(連盟PDF/ページ・掲示板記事)へのリンク**を併記。どのソース由来か分かるように。
- 立教が入賞(優勝・準優勝・上位入賞)・全国出場した結果はハイライト表示。
- レスポンシブ対応(スマホ閲覧前提)。日本語表示・年度は和暦(全国は西暦併記可)で。
- **団体戦結果表の表示仕様**（実装済み）:
  - 全チーム対戦表（`kanto_table`）を罫線付きテーブルで表示
  - 立教の行は黄色ハイライト（`background: #fff8d8`）
  - 昇降級バッジは順位列の右に表示（緑=昇級、赤=降級）
  - 複数日程は `1日目 / 2日目 / 3日目` で日付・会場を列挙

### 6.3 データ収集〜公開フロー(具体手順)

「人手」= サイト運用者(初期はユーザー本人 / 将来は部員)。手順は以下に固定する。

1. 収集: `python scraper/fetch_kanto.py` / `python scraper/fetch_bbs.py` を実行 → `data/auto/<season>.json` に
   `confidence: "auto"` で出力。生ファイルは `cache/` に保存。
2. テーブル追記: `python scraper/update_kanto_tables.py [--force]` を実行 →
   `data/confirmed/*.json` に `kanto_table` と `schedule` を自動追記。
3. 確認: 運用者が `data/auto/<season>.json` を開き、`cache/` の生PDF/HTMLと突き合わせて検証。
   - 正しければ `confidence` を `confirmed` にし、`data/confirmed/<season>.json` へ移動(コピー)。
   - 誤りは手で修正。掲示板のスコアなど自動で取れない値はここで補う。
4. 検証: `data/confirmed/*.json` を `data/schema.json`(JSON Schema)でバリデーション。
   CI でも実行し、スキーマ不適合ならビルドを止める。
5. ビルド: SSG は **`data/confirmed/` のみ**を読み込んで静的生成(`auto` は使わない)。
6. 公開: 内容をプレビュー確認し、ユーザー承認後に `main` へ push → Actions がデプロイ。
   - 実データが揃い §8 のデータ系項目を満たすまで公開しない(§1.5.2)。

新しい大会結果が出たら 1〜6 を該当年度ぶんだけ再実行する。

---

## 7. 非機能要件 / 技術スタック

- **静的サイト**(SSG)。GitHub Pages で公開(GitHub Actions で自動ビルド・デプロイ)。
  - フレームワークは **Astro**（実装済み。Node 20 + astro v6）。
  - GitHub Pages のベースパス(`/<repo>/`)に対応できるよう、リンクは相対 or ベースパス設定で。
- 収集スクリプトは **Python**(`requests` + `pdfplumber` + `beautifulsoup4` + `openpyxl`)。
  - PDF / HTML / xlsx の3形式に対応(全国連盟は形式が混在するため)。
  - Shift-JIS デコード処理を共通化(`common.py`)。
  - 両連盟サーバへ負荷をかけないよう逐次・スリープ・リトライ付き・キャッシュあり。
  - venv: リポジトリ直下の `.venv`（全パッケージ収録済み・gitignore対象）
- 取得した PDF/HTML/xlsx とテキストは `cache/` に保存し、再実行時は差分のみ取得。
  キャッシュファイル名は URL の MD5 ハッシュ（例: `3148d858544ab5407409e44db8f1c9bb.xlsx`）。
- 文字コードは全て UTF-8 で出力。
- 抽出ロジックは **団体戦パーサ / 個人戦パーサ / 掲示板パーサ**を分離し、
  年度・形式差を設定で吸収できるようにする（全国連盟パーサは未実装）。
- 掲示板は自由記述のため、キーワード候補抽出 + 正規表現で次を拾い、人手確認に回す:
  対戦相手別スコア(`(対)?大学名 + 数字-数字 + 勝ち/負け`)、回戦別戦績(`N回戦 対 ○○ M勝K敗`)、
  不戦勝敗(`不戦勝/不戦敗 N`)、個人別結果(`氏名 + 予選○回戦突破` 等)、出場級・順位。
  公式戦/非公式戦(交流戦・古新戦)の判別もここで行う。
  非公式戦は日付+相手校名のみ拾えばよい(参加人数・形式・内容は抽出しない)。

---

## 8. 受け入れ条件(Definition of Done)

**着手前提**
- [x] 着手時に3ドメインへの到達確認を行い、不可ならユーザーに許可を依頼してから進めている。

**データ収集**
- [x] 関東連盟の起点ページから全19年度のページを自動発見できる。
- [x] 各年度ページ内の全大会リンクを列挙し、PDF/HTML/xlsx を取得・テキスト抽出できる。
- [x] 掲示板の全ページを巡回し(総件数からページ数を算出)、大会結果を含む投稿を候補抽出して構造化できる。
- [x] 掲示板の個人別戦績(氏名つき)・回戦別戦績・不戦勝敗を構造化できる(書かれている場合)。
- [x] 交流戦・古新戦など非公式戦も `is_official: false` でタグ付けして抽出・**サイトに掲載**できる(公式戦とラベルで区別)。
- [ ] 全国連盟サイトを走査し、立教の登場有無を判定できる(実績があれば抽出、無ければ省略)。**未実装**
- [x] 立教が登場する大会のみを保存し、登場しない大会は保存せず走査ログに記録できる。
- [x] 出力 JSON が `data/schema.json` のバリデーションを通る。
- [x] スクレイパ出力は `auto`、人手確認後に `confirmed` へ移す運用が回る。

**サイト表示**
- [x] 大会結果ページが**年度ごとにまとまって**表示される(大会別の個別ページは不要)。
- [x] 団体戦で立教の級・順位・昇降級が表示され、掲示板由来のスコア・個人勝敗があれば添えられる。
- [x] 全チーム対戦表（kanto_table）が罫線付き・立教行ハイライトで表示される。
- [x] 昇降級バッジが順位列の右に表示される。
- [x] 複数日程（1日目・2日目・3日目）が日付・会場付きで表示される。
- [ ] 個人戦・その他棋戦で立教の出場者・学年・最高成績が表示される(出典リンク付き)。**一部年度未対応**
- [ ] 全国大会の立教実績がある年度のみ「全国」バッジ付きで表示される(無い年度は出さない)。**データ未取得**
- [x] 各結果に出典(連盟PDF/ページ・掲示板記事)へのリンクが付き、ソースが区別できる。
- [x] 掲示板アーカイブ2件へのリンクがある。
- [x] データ0件でもビルドが落ちない(ただし0件状態は公開しない)。
- [x] スマホ表示が崩れない。

**公開**
- [x] SSG は `data/confirmed/` のみを読んでビルドする。
- [x] GitHub Actions ワークフロー（deploy.yml・validate.yml）が用意されている。
- [x] `https://rikkyo-shogi.github.io/site/` で公開されている（Organization: rikkyo-shogi / repo: site）。
- [x] 実データが揃い、ユーザーが内容を承認してから公開している。

---

## 9. 実装上の注意・既知のリスク

- PDF テキスト抽出は**順序保証がない**。個人戦トーナメント表は氏名・所属・学年が
  バラバラに出力されるため、`pdfplumber` の座標情報(`word.x0/top`)を使った位置ベース
  再構成を検討。難しい年度は手入力フォールバックを用意する。
- **古い年度ほど形式が異なる**(`.htm`、PDF 化されていない、PDF が無い大会がある等)。
  まず関東 令和8〜令和6年度で確実に動かし、古い年度は順次対応する段階的実装でよい。
- **全国連盟サイトは形式の混在が激しい**(PDF / HTML / xlsx / docx / 本文直書き / Google Drive)。
  すべてを完全自動化せず、立教出場年は数が限られるため**手入力フォールバックを併用**してよい。
- 両連盟サイトとも Shift-JIS かつ FC2 ホスティング。文字化け・404(未公開大会)を想定し、
  エラーは握りつぶさずログに残す。
- 立教の表記揺れ(`立教大学` / `立教大` / `立教` / `(立教3)` / `（立教大学3年）`)に対応する
  正規化を必ず入れる(全角・半角カッコ、全角学年表記の両対応)。
- 地区→全国の関連付け(`national_qualification`)は自動判定が難しいため、
  人手で補えるフィールドとして用意する。
- **掲示板は自由記述で雑多**。大会結果は全件中の一部で、新歓・合宿・総会等に埋もれるため
  キーワードで候補抽出する。ただし書式は4類型(団体スコア/回戦別/個人別/非公式戦)に
  整理でき、**個人名つき戦績も実在するため正規表現で構造化可能**。
  「中間報告」と「最終結果」が混在する点(同一大会は最終を採用)、投稿者により表記がゆれる点に注意。
  自動化率は高めに見込めるが、最終的な正しさは人手確認で担保する。
- 掲示板は立教視点の投稿なので、対戦相手だけ書かれ**主語(立教)が省略**されることが多い。
  **スコアは「左が立教・右が相手」で確定**(例「東京電機大学 4-3 勝ち」→ 立教4・相手3)。
  パーサはこの前提でスコアを解釈してよい。明らかに矛盾する箇所(勝敗とスコアの不一致等)のみ
  人手で確認する。
- 掲示板由来の情報は個人名を含むため、後述の個人情報配慮を特に適用する。
- 連盟PDFと掲示板で順位・級の表記が食い違う場合は**連盟(公式)を優先**し、掲示板は補足扱い。
- 各サイトの著作物(連盟PDF・掲示板投稿本文)を丸ごと再配布せず、
  **立教関連の事実情報の抽出 + 出典リンク**に留める。掲示板本文の長文転載は避ける。
- 個人情報配慮: 学生氏名を扱うため、現役部員の希望に応じて氏名のイニシャル化等を
  切り替えられる設定を用意することが望ましい。
- **HTML テーブルのパース注意点（実装済み対処）**:
  - 末尾の空文字列セルを stats 解析前に除去する（`[s for s in cells if s.strip()]`）。
  - ヘッダーに `大学名`・`チーム`・`対校` 等の表記がある年度では、それをチーム名列と判定してスキップ。
  - シード列がない年度（暗黙シード）は先頭セルが数字でなくともチーム行として扱う。
  - PDF の `入れ替え` 列由来の座標アーティファクト（値 ≥ 1000）は除去する。
  - XLSX のキャッシュ名は URL の MD5 ハッシュ。ファイルを手動配置する場合はこの名前に合わせる。

---

## 10. 段階的実装の推奨順序

0. **到達確認**: 3ドメインへ HTTP アクセスできるか確認。不可ならユーザーに許可依頼(§1.5.1)。 ✓
1. データ層の土台: `data/schema.json` 定義 + `auto`/`confirmed` ディレクトリ + バリデーション。 ✓
2. 関東連盟: 起点 → 全年度ページ発見クローラ(Shift-JIS 対応)→ 大会リンク列挙。 ✓
3. 団体戦 PDF パーサ(マトリクス形式、立教行抽出)。 ✓ PDF/HTML/XLSX 全形式対応済み
4. 個人戦 PDF パーサ(座標ベース、立教選手抽出)。 ✓
5. SSG で大会結果ページ(年度ごとにまとめ)+ 掲示板リンクを生成。データ0件でも落ちないこと。 ✓
6. 掲示板クローラ + パーサ(対戦相手別スコア・個人勝敗の候補抽出)→ 団体戦に統合表示。 ✓
7. ここまでで関東+掲示板の実データを人手確認 → `confirmed` 化 → ユーザー承認 → 初回公開。 **← 現在地**
   - `data/confirmed/` に H21〜R08 の 18 年度分・77 イベントが格納済み
   - ユーザーが内容を確認・承認してから公開する
8. GitHub Actions 自動デプロイ → `https://rikkyo-shogi.github.io/site/`。 ✓
   - Organization: rikkyo-shogi / repo: site / Node.js 22 / `deploy.yml` 実働中
9. (任意)全国連盟: サイト走査で立教実績を確認 → あればパーサ実装し全国成績を追加。 **未実装**
10. (任意)地区→全国の関連付け表示。 **未実装**
11. 古い年度(関東=平成期 / 全国=2011年度〜 / 掲示板=遡及分)の形式差に順次対応。 ✓ 対応済み(H21〜)

---

## 11. SEO要件と実装状況（2026-07-17 追加）

### 11.1 背景・目的

公開後、サイトが Google 検索にヒットしない問題が判明した。原因は SEO の土台の欠如
（sitemap.xml / robots.txt なし、meta description・canonical・OGP・構造化データなし、
Google Search Console 未登録）。検索エンジンにサイトを発見・インデックスさせ、
検索結果での見え方を改善することを目的に、フェーズを分けて対応する。

### 11.2 要件

**フェーズ1: Googleに発見・インデックスさせる（実装済み）**
- robots.txt を配信し、全ページのクロールを許可し、sitemap の場所を明示する
- sitemap.xml をビルド時に自動生成し、全公開ページを本番絶対URLで含める
- Google Search Console の所有権確認用 meta タグを設置する

**フェーズ2: インデックス後の評価・見え方を改善する（実装済み）**
- 全ページに固有の meta description / 自己参照 canonical（絶対URL）を設定
- 全ページに OGP 一式・Twitter Card（summary_large_image）を設定
- トップページに SportsOrganization の JSON-LD 構造化データを埋め込む
- メタ情報は共通レイアウト経由で一元管理し、ページ側は props を渡すだけにする

**フェーズ3: 被リンク・継続改善（未着手）**
- 被リンク獲得: 立教大学公式サークル一覧・関東大学将棋連盟サイト・部のSNSからのリンク
- Core Web Vitals / PageSpeed Insights の確認（Astro静的サイトのため優先度低）

### 11.3 実装内容（コミット: 085f4c5, ae00232）

| 変更 | 内容 |
|------|------|
| `site/public/robots.txt` | 新規。全ページ許可 + `Sitemap:` 行 |
| `@astrojs/sitemap` v3.7.3 | `astro.config.mjs` の `integrations` に追加。ビルドで `sitemap-index.xml` / `sitemap-0.xml` を自動生成 |
| `site/src/layouts/BaseLayout.astro` | 新規。title/description/image/ogType/footerText を props で受け、head メタ一式と共通ヘッダー・フッターを一元管理。GSC 確認トークン設定済み |
| 3ページの BaseLayout 化 | index / result / archives。ページ固有 description 設定。見た目・CSSは不変（ビルド差分で検証済み） |
| JSON-LD | index に SportsOrganization を埋め込み |
| `site/public/ogp.png` | 新規作成（1200×630、サイト配色） |

実装上の注意:
- canonical / og:url は `new URL(Astro.url.pathname, Astro.site)` で生成。
  `Astro.url.pathname` は base(`/site`)を含むため二重付与・欠落は起きない（ビルドで検証済み）
- result ページ固有のモバイルヘッダー縮小は、ヘッダーがレイアウト側に移ったため
  ページ内 `<style is:global>` で維持している（スコープCSSでは届かない）

### 11.4 Google Search Console の状況（2026-07-17 時点）

- プロパティ `https://rikkyo-shogi.github.io/site/`（URLプレフィックス型）登録・所有権確認 完了
- トップページ: インデックス登録済み
- result / archives: 未インデックス。サイトマップ初回取得がデプロイ完了前と重なり
  「取得できませんでした」表示のまま（sitemap-index.xml 自体は正常配信を確認済み）。
  Google の再クロール待ち + URL検査からの個別インデックス登録リクエストで対応中
- 確認方法: サイトマップのステータスが「成功」/ URL検査で「登録されています」/
  `site:rikkyo-shogi.github.io` 検索でのヒット
