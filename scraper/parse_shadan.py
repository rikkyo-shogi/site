"""社団戦(東将連)PDFの表抽出 — 第34回(令和7年度)試作パイプライン。

- 順位一覧PDF(ichiran)から立教2チームの最終成績(部・順位・勝点・勝数・昇降)を抽出し、
  `data/shadan/confirmed/R07.json` に teams[] 形式で出力する(league_table は
  リーグ表PDF未解析のため null)。
- 部別個人ランキングPDFから立教2チーム所属者の {reg_no, name, rating, games, team} を
  抽出する。対象PDF(l3w 等)は順位一覧から得た division から導出する。
  【重要・ROADMAP §2-2】個人の実名・レーティングはリポジトリにコミットしない。
  出力先は gitignore 済みの `data/auto/shadan/` のみ。公開ページにも個人名は出さない。

順位一覧PDFは赤/白リーグが左右2段組で、チーム名は全角1文字ずつ分割配置される。
そのため extract_words の座標でページ中央(x=width/2)で左右に分割し、
各段でトークン列を復元する。左右の赤/白はヘッダー行の表記から取る
(ヘッダーに赤/白が無い単一リーグ(1部)は「N部」のみとする)。
"""

import io
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pdfplumber

from common import logger, validate_json
import fetch_shadan

ROOT = Path(__file__).parent.parent
SHADAN_CONFIRMED = ROOT / "data" / "shadan" / "confirmed"
SHADAN_SCHEMA = ROOT / "data" / "shadan" / "schema.json"
AUTO_DIR = ROOT / "data" / "auto" / "shadan"

KAI = 34
SEASON = "R07"
SEASON_LABEL = "令和7年度"

# 立教の2チーム(第34回)。team_id は将来の名称変更に備えた安定ID。
# division・個人ランキングの対象PDFは順位一覧PDFの実データから決定する
# (ここには書かない=単一チーム/固定部の前提にしない)。
# note は出典PDFから読み取れる事実のみを書く(公開ページには表示されない)。
TARGET_TEAMS = [
    {"team_id": "shiryukai_univ", "team_name": "立教大学紫龍会", "note": ""},
    {"team_id": "shiryukai", "team_name": "紫龍会",
     "note": "前年(第33回)は5部白13位。降級により第34回は6部リーグ赤所属で、個人ランキングも6部赤に掲載。"},
]

CIRCLED = set("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳")

_PLAIN_INT = re.compile(r"\d+")


def _num(tok: str):
    """"1" "30.5" 等を int/float に。全角数字はNFKCで半角化。数値でなければ None。"""
    tok = unicodedata.normalize("NFKC", tok)
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


def _parse_half(tokens: list[dict], division: str) -> dict | None:
    """左右いずれかの段のトークン列から1行分の成績を復元する。

    列並び: 順位 / チーム名(1文字ずつ) / 前年(例 "3白⑩") / 勝点 / 勝数 / 経過 / 昇降
    """
    if not tokens:
        return None
    texts = [unicodedata.normalize("NFKC", t["text"]) for t in tokens]
    # 丸数字(②等)は isdigit()=True になるため、半角化した上で明示パターンで判定
    if not _PLAIN_INT.fullmatch(texts[0]):
        return None
    rank = int(texts[0])

    # 前年欄(丸数字を含む合成トークン)の位置を探す → その手前までがチーム名
    nen_idx = None
    for i in range(1, len(tokens)):
        if any(c in CIRCLED for c in tokens[i]["text"]):
            nen_idx = i
            break
    if nen_idx is None:
        return None
    name = "".join(t["text"] for t in tokens[1:nen_idx])
    rest = texts[nen_idx + 1:]

    numeric = [n for n in (_num(t) for t in rest) if n is not None]
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

    return {"name": name, "division": division, "rank": rank,
            "points": points, "wins": wins, "promotion": promotion}


_HEADER = re.compile(r"(\d+)部リーグ(赤|白)?")


def parse_standings(pdf_bytes: bytes) -> dict[str, dict]:
    """順位一覧PDFを1パスで走査し、{チーム名: 成績} を返す。

    ヘッダー行(例「３部リーグ赤３部リーグ白」)から左右それぞれの division を決める。
    赤/白の無い単一リーグ(1部)は「N部」のみとし、左右分割は同じ division で扱う。
    """
    standings: dict[str, dict] = {}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            mid = page.width / 2
            div_left: str | None = None
            div_right: str | None = None
            for line in _lines(page):
                joined = unicodedata.normalize("NFKC", "".join(w["text"] for w in line))
                headers = _HEADER.findall(joined)
                if headers:
                    bu, color = headers[0]
                    div_left = f"{bu}部{color}"
                    if len(headers) > 1:
                        bu2, color2 = headers[1]
                        div_right = f"{bu2}部{color2}"
                    else:
                        div_right = div_left
                    continue
                if div_left is None:
                    continue
                for division, toks in (
                    (div_left, [w for w in line if w["x0"] < mid]),
                    (div_right, [w for w in line if w["x0"] >= mid]),
                ):
                    parsed = _parse_half(toks, division)
                    if parsed and parsed["name"] not in standings:
                        standings[parsed["name"]] = parsed
    return standings


def ranking_suffix(division: str) -> str:
    """division からランキングPDFのファイル名サフィックスを導出する。

    例: 3部白 → l3w / 6部赤 → l6r / 1部 → l1
    """
    m = re.fullmatch(r"(\d+)部(赤|白)?", division)
    if not m:
        raise SystemExit(f"division '{division}' からランキングPDF名を導出できません。")
    bu, color = m.groups()
    return f"l{bu}" + ("" if color is None else ("r" if color == "赤" else "w"))


def parse_ranking(pdf_bytes: bytes, team_name: str, expected_division: str) -> list[dict]:
    """部別ランキングPDFから team_name 所属者の個人成績を抽出する(実名を含む)。

    列: 順位 / 登録番号 / 氏名(姓 名で空白を含みうる) / 新持点 / 通算対局数 / チーム名
    末尾3列(チーム名・通算対局数・新持点)を右から確定し、間を氏名として復元する。
    """
    members: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # 取り違え防止: PDF冒頭に部名(例「3部白」)が記載されているはずなので照合する
        head = (pdf.pages[0].extract_text() or "")[:100]
        if expected_division not in unicodedata.normalize("NFKC", head).replace(" ", ""):
            raise SystemExit(
                f"ランキングPDFの冒頭に想定の部名 '{expected_division}' が見つかりません"
                f"(冒頭: {head[:40]!r})。対象PDFの取り違えの可能性があるため停止。"
            )
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


def build() -> tuple[dict, dict[str, int]]:
    """チーム成績JSONと、チーム別の個人抽出件数(報告用)を返す。"""
    fetch_shadan.ensure_reachable()
    standings = parse_standings(fetch_shadan.fetch_pdf(fetch_shadan.ICHIRAN_URL))

    teams = []
    individual_counts: dict[str, int] = {}
    for spec in TARGET_TEAMS:
        stand = standings.get(spec["team_name"])
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
            "source_url": fetch_shadan.ICHIRAN_URL,
            "league_table": None,  # 順位一覧のみから作成。対戦表はリーグ表PDFの解析(将来)で付与
            "note": spec["note"],
        })

        # 個人ランキング: 対象PDFを division から導出して取得(gitignore側にのみ出力)
        suffix = ranking_suffix(stand["division"])
        url = fetch_shadan.ranking_url(suffix)
        members = parse_ranking(fetch_shadan.fetch_pdf(url), spec["team_name"], stand["division"])
        if not members:
            raise SystemExit(
                f"ランキングPDF({suffix})に '{spec['team_name']}' の所属者が1人も"
                " 見つかりませんでした。チーム名表記の変更等の可能性があるため停止。"
            )
        AUTO_DIR.mkdir(parents=True, exist_ok=True)
        out = AUTO_DIR / f"{SEASON}_{spec['team_id']}.json"
        out.write_text(json.dumps({
            "kai": KAI, "season": SEASON, "team_id": spec["team_id"],
            "team_name": spec["team_name"], "division": stand["division"],
            "source_url": url,
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
            "ichiran_pdf": fetch_shadan.ICHIRAN_URL,
            "league_pdf": fetch_shadan.LEAGUE_URLS,
        },
        "teams": teams,
    }
    return result, individual_counts


if __name__ == "__main__":
    result, counts = build()
    errors = validate_json(result, SHADAN_SCHEMA)
    if errors:
        raise SystemExit(f"スキーマ検証エラー(保存中止): {errors}")
    SHADAN_CONFIRMED.mkdir(parents=True, exist_ok=True)
    out = SHADAN_CONFIRMED / f"{SEASON}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {out}")
    for t in result["teams"]:
        print(f"  {t['team_name']}: {t['division']} {t['rank']}位 "
              f"勝点{t['points']} 勝数{t['wins']} {t['promotion'] or ''}")
    print("個人抽出(非コミット・件数のみ):",
          ", ".join(f"{k}={v}名" for k, v in counts.items()))
