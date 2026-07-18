"""社団戦(東将連)PDFの表抽出 — 第34回(令和7年度)試作パイプライン。

- 順位一覧PDF(ichiran)から立教2チームの最終成績(部・順位・勝点・勝数・昇降)を抽出し、
  `data/shadan/confirmed/R07.json` に teams[] 形式で出力する(league_table は順位一覧のみのため null)。
- 部別個人ランキングPDF(l3w / l6r)から立教2チーム所属者の
  {reg_no, name, rating, games, team} を抽出する。
  【重要・ROADMAP §2-2】個人の実名・レーティングはリポジトリにコミットしない。
  出力先は gitignore 済みの `data/auto/shadan/` のみ。公開ページにも個人名は出さない。

順位一覧PDFは赤/白リーグが左右2段組で、チーム名は全角1文字ずつ分割配置される。
そのため extract_words の座標でページ中央(x=width/2)で左右に分割し、
各段でトークン列を復元して対象チームの行を特定する。
"""

import io
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pdfplumber

from common import logger
import fetch_shadan

ROOT = Path(__file__).parent.parent
SHADAN_CONFIRMED = ROOT / "data" / "shadan" / "confirmed"
AUTO_DIR = ROOT / "data" / "auto" / "shadan"

KAI = 34
SEASON = "R07"
SEASON_LABEL = "令和7年度"

# 立教の2チーム(第34回)。team_id は将来の名称変更に備えた安定ID。
# division は順位一覧PDFの実データから決定する(ここには書かない=単一チーム/固定部の前提にしない)。
TARGET_TEAMS = [
    {"team_id": "shiryukai_univ", "team_name": "立教大学紫龍会", "ranking_key": "ranking_l3w",
     "note": ""},
    {"team_id": "shiryukai", "team_name": "紫龍会", "ranking_key": "ranking_l6r",
     "note": ("順位一覧PDF(34_ichiran_04.pdf)では6部リーグ赤9位。"
              "前年5部白13位からの降級で、個人ランキングも l6r に掲載。"
              "課題前提の『5部赤』とは異なるためPDF実データを採用した。")},
]

CIRCLED = set("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳")


def _num(tok: str):
    """"1" "30.5" 等を int/float に。数値でなければ None。"""
    try:
        f = float(tok)
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def _lines(page) -> list[list[dict]]:
    """ページのワードを行(topのまとまり)ごとにまとめ、x昇順で返す。"""
    buckets: dict[int, list[dict]] = defaultdict(list)
    for w in page.extract_words():
        buckets[round(w["top"] / 3)].append(w)
    return [sorted(buckets[k], key=lambda w: w["x0"]) for k in sorted(buckets)]


def _parse_half(tokens: list[dict], bu: int, side: str) -> dict | None:
    """左右いずれかの段のトークン列から1行分の成績を復元する。

    列並び: 順位 / チーム名(1文字ずつ) / 前年(例 "3白⑩") / 勝点 / 勝数 / 経過 / 昇降
    """
    if not tokens:
        return None
    texts = [t["text"] for t in tokens]
    if not re.fullmatch(r"\d+", texts[0]):  # 丸数字(②等)は isdigit()=True になるため除外
        return None
    rank = int(texts[0])

    # 前年欄(丸数字を含む合成トークン)の位置を探す → その手前までがチーム名
    nen_idx = None
    for i in range(1, len(texts)):
        if any(c in CIRCLED for c in texts[i]):
            nen_idx = i
            break
    if nen_idx is None:
        return None
    name = "".join(texts[1:nen_idx])
    rest = texts[nen_idx + 1:]

    nums = [_num(t) for t in rest]
    numeric = [n for n in nums if n is not None]
    if len(numeric) < 2:
        return None
    points, wins = numeric[0], numeric[1]

    promotion = None
    for t in rest:
        if "昇" in t:
            promotion = "昇級"
            break
        if "降" in t:
            promotion = "降級"
            break

    division = f"{bu}部{'赤' if side == 'left' else '白'}"
    return {"name": name, "division": division, "rank": rank,
            "points": points, "wins": wins, "promotion": promotion}


def find_team_standing(pdf, team_name: str) -> dict | None:
    """順位一覧PDFから team_name の行(部・順位・勝点・勝数・昇降)を特定する。"""
    for page in pdf.pages:
        mid = page.width / 2
        bu = None
        for line in _lines(page):
            joined = unicodedata.normalize("NFKC", "".join(w["text"] for w in line))
            m = re.search(r"(\d+)部リーグ", joined)
            if m:
                bu = int(m.group(1))
                continue
            if bu is None:
                continue
            left = [w for w in line if w["x0"] < mid]
            right = [w for w in line if w["x0"] >= mid]
            for side, toks in (("left", left), ("right", right)):
                parsed = _parse_half(toks, bu, side)
                if parsed and parsed["name"] == team_name:
                    return parsed
    return None


def parse_ranking(pdf_bytes: bytes, team_name: str) -> list[dict]:
    """部別ランキングPDFから team_name 所属者の個人成績を抽出する(実名を含む)。

    列: 順位 / 登録番号 / 氏名(姓 名で空白を含みうる) / 新持点 / 通算対局数 / チーム名
    末尾3列(チーム名・通算対局数・新持点)を右から確定し、間を氏名として復元する。
    """
    members: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for ln in (page.extract_text() or "").splitlines():
                toks = ln.split()
                if len(toks) < 6:
                    continue
                if not (toks[0].isdigit() and toks[1].isdigit()):
                    continue
                if not (toks[-2].isdigit() and toks[-3].isdigit()):
                    continue
                team = toks[-1]
                if team != team_name:  # 完全一致(部分一致にしない)
                    continue
                members.append({
                    "reg_no": int(toks[1]),
                    "name": "".join(toks[2:-3]),
                    "rating": int(toks[-3]),
                    "games": int(toks[-2]),
                    "team": team,
                })
    return members


def build() -> dict:
    data = fetch_shadan.fetch_all()
    ichiran_pdf = pdfplumber.open(io.BytesIO(data["ichiran"]))

    teams = []
    individual_counts = {}
    for spec in TARGET_TEAMS:
        stand = find_team_standing(ichiran_pdf, spec["team_name"])
        if stand is None:
            raise SystemExit(
                f"順位一覧PDFで '{spec['team_name']}' の行を特定できませんでした。"
                " レイアウト変更の可能性。推測で埋めず停止して報告すること。"
            )
        teams.append({
            "team_id": spec["team_id"],
            "team_name": spec["team_name"],
            "kai": KAI,
            "division": stand["division"],
            "rank": stand["rank"],
            "points": stand["points"],
            "wins": stand["wins"],
            "promotion": stand["promotion"],
            "source_type": "shadan_pdf",
            "source_url": fetch_shadan.PDF_URLS["ichiran"],
            "league_table": None,  # 順位一覧のみから作成。対戦表はリーグ表PDFの解析(将来)で付与
            "note": spec.get("note", ""),
        })

        # 個人ランキング(gitignore側にのみ出力)
        members = parse_ranking(data[spec["ranking_key"]], spec["team_name"])
        AUTO_DIR.mkdir(parents=True, exist_ok=True)
        out = AUTO_DIR / f"{SEASON}_{spec['team_id']}.json"
        out.write_text(json.dumps({
            "kai": KAI, "season": SEASON, "team_id": spec["team_id"],
            "team_name": spec["team_name"], "division": stand["division"],
            "source_url": fetch_shadan.PDF_URLS[spec["ranking_key"]],
            "members": members,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        individual_counts[spec["team_id"]] = len(members)
        logger.info("個人ランキング %s: %d名 -> %s (非コミット)", spec["team_name"], len(members), out)

    result = {
        "kai": KAI,
        "season": SEASON,
        "season_label": SEASON_LABEL,
        "source": {
            "hub_url": fetch_shadan.HUB_URL,
            "ichiran_pdf": fetch_shadan.PDF_URLS["ichiran"],
            "league_pdf": [fetch_shadan.PDF_URLS["league_u"], fetch_shadan.PDF_URLS["league_g"]],
        },
        "teams": teams,
    }
    return result, individual_counts


if __name__ == "__main__":
    result, counts = build()
    SHADAN_CONFIRMED.mkdir(parents=True, exist_ok=True)
    out = SHADAN_CONFIRMED / f"{SEASON}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {out}")
    for t in result["teams"]:
        print(f"  {t['team_name']}: {t['division']} {t['rank']}位 "
              f"勝点{t['points']} 勝数{t['wins']} {t['promotion'] or ''}")
    print("個人抽出(非コミット・件数のみ):",
          ", ".join(f"{k}={v}名" for k, v in counts.items()))
