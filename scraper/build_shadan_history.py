"""社団戦(東将連) 過去回の確定データ生成 — 第22回(H23)〜第33回(R06)。

PDFのレイアウトが回ごとに大きく異なるため(§ROADMAP 2-1「半自動＋目視」)、
本スクリプトは「PDFを目視確認した確定値」を records に保持し、
スキーマ検証つきで data/shadan/confirmed/*.json を生成する。

各値の根拠は出典PDF(source_url)そのもの。確認方法:
- 第22〜30回: NN/5nitimeitiran*.pdf(最終日順位表)を pdfplumber のテキスト抽出
  + ページ画像レンダリングの目視で照合(2026-07 実施)
- 第31回: オンライン開催。最終順位は 31/rankingA4.pdf(リーグ表A)の5部表から取得。
  順位一覧形式のPDFは公開されていない
- 第32〜33回: NN_ichiran_04.pdf のテキスト抽出で取得(第34回と同系式だが前年列なし)
- 昇降で「翌回の所属部より判定」と注記したものは、当該回PDFに昇降欄の記載が無く、
  翌回PDFの所属部の変化から確定した事実

第34回(R07)は parse_shadan.py(自動抽出)が担当する。
"""

import json
from pathlib import Path

from common import logger, validate_json

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "shadan" / "confirmed"
SCHEMA = ROOT / "data" / "shadan" / "schema.json"
BASE = "https://toushouren.world.coocan.jp/shadan"

UNIV = "shiryukai_univ"  # 現役チーム(立教大紫龍会→立教大学紫龍会)
OB = "shiryukai"         # 紫龍会

# (kai, season, season_label, ichiran相当PDFの相対パス, teams)
# teams: (team_id, team_name, division, rank, points, wins, promotion, note)
RECORDS = [
    (22, "H23", "平成23年度", "22/5nitimeitiran.pdf", [
        (OB, "紫龍会", "3部青", 5, 10, 64, None, "この年度の3部は赤・白・青の3リーグ制。"),
    ]),
    (23, "H24", "平成24年度", "23/5nitimeitiran.pdf", [
        (OB, "紫龍会", "3部赤", 9, 8, 51, None, ""),
    ]),
    (24, "H25", "平成25年度", "24/5nitimeitiran.pdf", [
        (OB, "紫龍会", "3部白", 7, 9, 53, None, ""),
    ]),
    (25, "H26", "平成26年度", "25/5nitimeitiran.pdf", [
        (OB, "紫龍会", "3部白", 3, 12, 63, "昇級", "入替戦を経て昇級(翌回2部白所属より判定)。"),
    ]),
    (26, "H27", "平成27年度", "26/5nitimeitiran.pdf", [
        (OB, "紫龍会", "2部白", 16, 2, 35, "降級",
         "翌回3部白所属より判定。出典PDFの表題は「第25回」表記だが第26回の最終順位表。"),
    ]),
    (27, "H28", "平成28年度", "27/5nitimeitiran1.pdf", [
        (OB, "紫龍会", "3部白", 14, 4, 41, None, "この回を最後に第32回まで休会。"),
        (UNIV, "立教大紫龍会", "3部赤", 16, 0, 16, "降級", "翌回4部白所属より判定。"),
    ]),
    (28, "H29", "平成29年度", "28/5nitimeitiran1.pdf", [
        (UNIV, "立教大紫龍会", "4部白", 16, 2, 36, "降級", "翌回5部白所属より判定。"),
    ]),
    (29, "H30", "平成30年度", "29/5nitimeitiran1.pdf", [
        (UNIV, "立教大紫龍会", "5部白", 5, 10, 62.5, None, ""),
    ]),
    (30, "R01", "令和1年度", "30/5nitimeitiran1.pdf", [
        (UNIV, "立教大紫龍会", "5部白", 9, 8, 56, None, ""),
    ]),
    # 第31回はコロナ禍の影響で令和4年度に開催(令和2・3年度の団体戦は中止)
    (31, "R04", "令和4年度", "31/rankingA4.pdf", [
        (UNIV, "立教大紫龍会", "5部", 4, 12, 71, "昇級",
         "オンライン併用形式・単一5部リーグ(20チーム)。12勝3敗。"
         "勝点は勝利マッチ数。入替戦を経て昇級(翌回4部赤所属より判定)。"),
    ]),
    (32, "R05", "令和5年度", "32/32_ichiran_04.pdf", [
        (UNIV, "立教大学紫龍会", "4部赤", 5, 9, 57, "昇級", "入替戦勝利により昇級(△昇)。"),
    ]),
    (33, "R06", "令和6年度", "33/33_ichiran_04.pdf", [
        (UNIV, "立教大学紫龍会", "3部白", 10, 8, 53, None, ""),
        (OB, "紫龍会", "5部白", 13, 4, 45, "降級", "第28回からの休会を経てこの回に5部で復帰(▼降)。"),
    ]),
]


def hub_url(season: str) -> str:
    return f"{BASE}/sub9-{season}.htm"


def build_season(kai, season, season_label, pdf_rel, teams) -> dict:
    src = f"{BASE}/{pdf_rel}"
    return {
        "kai": kai,
        "season": season,
        "season_label": season_label,
        "source": {"hub_url": hub_url(season), "ichiran_pdf": src},
        "teams": [
            {
                "team_id": tid, "team_name": name, "kai": kai,
                "division": div, "rank": rank, "points": pts, "wins": wins,
                "promotion": promo,
                "source_type": "shadan_pdf",
                "source_url": src,
                "league_table": None,
                "note": note,
            }
            for tid, name, div, rank, pts, wins, promo, note in teams
        ],
    }


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for rec in RECORDS:
        data = build_season(*rec)
        errors = validate_json(data, SCHEMA)
        if errors:
            raise SystemExit(f"{data['season']}: スキーマ検証エラー: {errors}")
        out = OUT_DIR / f"{data['season']}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("saved %s (第%d回, %d team(s))", out.name, data["kai"], len(data["teams"]))
    print(f"generated {len(RECORDS)} season files in {OUT_DIR}")
