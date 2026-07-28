"""社団戦(東将連) 過去回の確定データ生成 — 第12回(H13)〜第33回(R06)。

資料の形式が回ごとに大きく異なるため(§ROADMAP 2-1「半自動＋目視」)、
本スクリプトは「出典を目視確認した確定値」を records に保持し、
スキーマ検証つきで data/shadan/confirmed/*.json を生成する。

各値の根拠は出典(source_url)そのもの。確認方法(2026-07 実施):
- 第12〜15回: リーグ別HTMLページ(表列: 勝/敗/勝数/大将/順位)のテーブル抽出。
  「勝」はマッチ勝利数でこの時代の勝点に相当するため points に記録
- 第16回: shadan/roku/1605.pdf(リーグ別一覧)
- 第17〜20回: リーグ表が現存せず、公式結果ページ(上位3位まで)・部別レーティング
  一覧(所属部の判定)・第21回順位表の休会欄(前回成績)から判明する範囲のみ記録。
  順位が特定できない行は rank=null
- 第21回: 21/page2105.pdf(順位表)。立教大学紫龍会は同PDFの休会欄に記載
  (第20回成績を持って休会)のため第21回は不参加
- 第22〜30回: NN/5nitimeitiran*.pdf(最終日順位表)のテキスト抽出+ページ画像の目視。
  出典リンクは同内容の成績順リーグ表(NN/5nitimeseisekijun*.pdf)を指す(サイト表示の方針)
- 第31回: オンライン開催。最終順位は 31/rankingA4.pdf(リーグ表A)の5部表から取得
- 第32〜33回: NN_ichiran_04.pdf のテキスト抽出(第34回と同系式だが前年列なし)。
  出典リンクは成績順リーグ表(NN_league_04_g.pdf)を指す
- 第14回(H15)はリーグ表ページが連盟サイト上に現存しないため記録なし(ファイル自体を生成しない)
- 昇降で「翌回の所属部より判定」と注記したものは、当該回の資料に昇降の記載が無く、
  翌回資料の所属部の変化から確定した事実

第34回(R07)は parse_shadan.py(自動抽出)が担当する。
開催中の年度(ONGOING)は各節のリーグ表(成績順)から途中経過を記録し、
status: "ongoing" を付けて出力する(最終結果が出たら RECORDS 側へ移す)。
"""

import json
from pathlib import Path

from common import logger, validate_json

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "shadan" / "confirmed"
SCHEMA = ROOT / "data" / "shadan" / "schema.json"
SITE = "https://toushouren.world.coocan.jp"
BASE = f"{SITE}/shadan"

UNIV = "shiryukai_univ"  # 現役チーム(立教大紫龍会→立教大学紫龍会)
OB = "shiryukai"         # 紫龍会

# (kai, season, season_label, 出典の代表相対パス, teams)
# teams: (team_id, team_name, division, rank, points, wins, promotion, note[, source_rel])
# source_rel を指定した行はチーム個別の出典(リーグ別ページ等)を使う。
RECORDS = [
    (12, "H13", "平成13年度", "shadan/2-r.htm", [
        (UNIV, "立教大学紫龍会", "2部赤", 14, 4, 46, "降級",
         "列構成は勝/敗/勝数(4勝11敗)。翌回3部青所属より降級と判定。"),
    ]),
    (13, "H14", "平成14年度", "shadan/san/13-3b.htm", [
        (UNIV, "立教大学紫龍会", "3部青", 1, 13, 76, "昇級",
         "13勝2敗で優勝。第14回の資料は現存しないが第15回2部赤所属より昇級と判定。"),
    ]),
    # 第14回(H15)はリーグ表ページが現存しないため記録なし
    (15, "H16", "平成16年度", "shadan/go/2r.htm", [
        (UNIV, "立教大学紫龍会", "2部赤", 10, 7, 50.5, None, "7勝8敗。"),
        (OB, "紫龍会", "3部赤", 8, 8, 58, None, "8勝7敗。", "shadan/go/3r.htm"),
    ]),
    (16, "H17", "平成17年度", "shadan/roku/1605.pdf", [
        (UNIV, "立教大学紫龍会", "2部白", 8, 7, 53, None, "7勝8敗。"),
        (OB, "紫龍会", "3部緑", 9, 7, 56, None, "7勝8敗。"),
    ]),
    (17, "H18", "平成18年度", "shadan/nana/page4.pdf", [
        (UNIV, "立教大学紫龍会", "2部赤", 2, 13, 65, "昇級",
         "13勝2敗。順位一覧の凡例(▲昇級1-2位)より確定。"),
        (OB, "紫龍会", "3部緑", 6, 11, 59, None,
         "11勝4敗。順位一覧の凡例(□残留6-10位)より残留確定。"),
    ]),
    (18, "H19", "平成19年度", "shadan/hachi/page1801.pdf", [
        (UNIV, "立教大学紫龍会", "1部", 14, 2, 36, "降級",
         "2勝13敗(チーム史上最高の1部)。順位一覧の凡例(▼降級13-16位)より確定。"),
        (OB, "紫龍会", "3部赤", 8, 9, 58, None,
         "9勝6敗。順位一覧の凡例(□残留5-8位)より残留確定。"),
    ]),
    (19, "H20", "平成20年度", "shadan/19/page1901.pdf", [
        (UNIV, "立教大学紫龍会", "2部赤", 11, 6, 55, None,
         "6勝9敗。順位一覧の凡例では▽入替11-13位(残留/降級の入替戦対象)。"
         "翌回も2部赤所属のため入替戦を制して残留したと判定。"),
        (OB, "紫龍会", "3部青", 12, 5, 45, "降級",
         "5勝10敗。順位一覧の凡例では◇調整9-16位(自動昇降ではない調整枠)。"
         "翌回4部白所属より降級と判定。"),
    ]),
    (20, "H21", "平成21年度", "shadan/20/page2003.pdf", [
        (UNIV, "立教大学紫龍会", "2部赤", 9, 8, 57, None,
         "8勝7敗。この回を最後に第26回まで休会し、第27回に3部で復帰。"),
        (OB, "紫龍会", "4部白", 4, 11, 64, "昇級",
         "11勝4敗。この順位一覧に凡例行が無いため昇降の直接記載はなし。"
         "翌回3部青所属より昇級と判定。"),
    ]),
    (21, "H22", "平成22年度", "shadan/21/page2107.pdf", [
        (OB, "紫龍会", "3部青", 12, 6, 49, None,
         "6勝9敗。順位一覧の凡例では◇調整9-14位(自動昇降ではない調整枠)。"
         "立教大学紫龍会はこの回から休会。"),
    ]),
    (22, "H23", "平成23年度", "22/5nitimeseisekijun.pdf", [
        (OB, "紫龍会", "3部青", 5, 10, 64, None, "この年度の3部は赤・白・青の3リーグ制。"),
    ]),
    (23, "H24", "平成24年度", "23/5nitimeseisekijun.pdf", [
        (OB, "紫龍会", "3部赤", 9, 8, 51, None, ""),
    ]),
    (24, "H25", "平成25年度", "24/5nitimeseisekijun.pdf", [
        (OB, "紫龍会", "3部白", 7, 9, 53, None, ""),
    ]),
    (25, "H26", "平成26年度", "25/5nitimeseisekijun.pdf", [
        (OB, "紫龍会", "3部白", 3, 12, 63, "昇級", "入替戦を経て昇級(翌回2部白所属より判定)。"),
    ]),
    (26, "H27", "平成27年度", "26/5nitimeseisekijun.pdf", [
        (OB, "紫龍会", "2部白", 16, 2, 35, "降級",
         "翌回3部白所属より判定。出典PDFの表題は「第25回」表記だが第26回の最終順位表。"),
    ]),
    (27, "H28", "平成28年度", "27/5nitimeseisekijun1.pdf", [
        (OB, "紫龍会", "3部白", 14, 4, 41, None, "この回を最後に第32回まで休会。"),
        (UNIV, "立教大紫龍会", "3部赤", 16, 0, 16, "降級",
         "第21回からの休会を経てこの回に3部で復帰。翌回4部白所属より降級と判定。"),
    ]),
    (28, "H29", "平成29年度", "28/5nitimeseisekijun1.pdf", [
        (UNIV, "立教大紫龍会", "4部白", 16, 2, 36, "降級", "翌回5部白所属より判定。"),
    ]),
    (29, "H30", "平成30年度", "29/5nitimeseisekijun1.pdf", [
        (UNIV, "立教大紫龍会", "5部白", 5, 10, 62.5, None, ""),
    ]),
    (30, "R01", "令和元年度", "30/5nitimeseisekijun1.pdf", [
        (UNIV, "立教大紫龍会", "5部白", 9, 8, 56, None, ""),
    ]),
    # 第31回はコロナ禍の影響で令和4年度に開催(令和2・3年度の団体戦は中止)
    (31, "R04", "令和4年度", "31/rankingA4.pdf", [
        (UNIV, "立教大紫龍会", "5部", 4, 12, 71, "昇級",
         "オンライン併用形式・単一5部リーグ(20チーム)。12勝3敗。"
         "勝点は勝利マッチ数。入替戦を経て昇級(翌回4部赤所属より判定)。"),
    ]),
    (32, "R05", "令和5年度", "32/32_league_04_g.pdf", [
        (UNIV, "立教大学紫龍会", "4部赤", 5, 9, 57, "昇級", "入替戦勝利により昇級(△昇)。"),
    ]),
    (33, "R06", "令和6年度", "33/33_league_04_g.pdf", [
        (UNIV, "立教大学紫龍会", "3部白", 10, 8, 53, None, ""),
        (OB, "紫龍会", "5部白", 13, 4, 45, "降級", "第28回からの休会を経てこの回に5部で復帰(▼降)。"),
    ]),
]

# 開催中の年度(途中経過)。リーグ表(成績順)の値を目視確認して更新する。
# (kai, season, season_label, note, 出典相対パス, teams)
ONGOING = (
    35, "R08", "令和8年度", "第2節終了時点の途中経過",
    "35/35_league_02_u.pdf",
    [
        (UNIV, "立教大学紫龍会", "4部白", 4, 6, 32, None, "第2節終了時点で6勝2敗(前節8位から4つ上昇)。"),
        (OB, "紫龍会", "6部白", 13, 3, 16, None, "第2節終了時点で3勝5敗(前節15位から2つ上昇)。"),
    ],
)


def hub_url(season: str) -> str:
    # 第12〜20回(H13〜H21)の年度ページはサイト直下、H22以降は /shadan/ 配下
    era, num = season[0], int(season[1:])
    if era == "H" and num <= 21:
        return f"{SITE}/sub9-{season}.htm"
    return f"{BASE}/sub9-{season}.htm"


def _abs_url(rel: str) -> str:
    # 旧年度のHTMLはサイト直下からの相対パス("shadan/..."や"17shadan2.htm")、
    # 新しいPDFは /shadan/ 配下からの相対パス("34/34_ichiran_04.pdf")
    if rel.startswith("shadan/") or rel.endswith(".htm"):
        return f"{SITE}/{rel}"
    return f"{BASE}/{rel}"


def build_season(kai, season, season_label, src_rel, teams) -> dict:
    src = _abs_url(src_rel)
    team_objs = []
    for row in teams:
        tid, name, div, rank, pts, wins, promo, note = row[:8]
        team_src = _abs_url(row[8]) if len(row) > 8 else src
        team_objs.append({
            "team_id": tid, "team_name": name, "kai": kai,
            "division": div, "rank": rank, "points": pts, "wins": wins,
            "promotion": promo,
            "source_type": "shadan_pdf",
            "source_url": team_src,
            "league_table": None,
            "note": note,
        })
    return {
        "kai": kai,
        "season": season,
        "season_label": season_label,
        "source": {"hub_url": hub_url(season), "ichiran_pdf": src},
        "teams": team_objs,
    }


def _save(data: dict) -> None:
    errors = validate_json(data, SCHEMA)
    if errors:
        raise SystemExit(f"{data['season']}: スキーマ検証エラー: {errors}")
    out = OUT_DIR / f"{data['season']}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("saved %s (第%d回, %d team(s))", out.name, data["kai"], len(data["teams"]))


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for rec in RECORDS:
        _save(build_season(*rec))

    kai, season, label, note, src_rel, teams = ONGOING
    data = build_season(kai, season, label, src_rel, teams)
    data["status"] = "ongoing"
    data["note"] = note
    data["source"] = {"hub_url": SITE, "league_pdf": [_abs_url(src_rel)]}
    _save(data)
    print(f"generated {len(RECORDS)} final + 1 ongoing season files in {OUT_DIR}")
