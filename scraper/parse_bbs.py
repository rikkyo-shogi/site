"""掲示板パーサー: 4類型の大会結果書式から構造化データを抽出する。"""

import re
from datetime import datetime

# =========================================================
# 正規化ユーティリティ
# =========================================================

def _normalize_score(s: str) -> str:
    """全角数字・ハイフンを半角に正規化する。"""
    s = s.translate(str.maketrans("０１２３４５６７８９ー－", "0123456789--"))
    return s


def _to_int(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(_normalize_score(s).strip())
    except ValueError:
        return None


def _normalize_uni(name: str) -> str:
    """大学名の略称・表記ゆれを正規化する。"""
    replacements = [
        (r"東大(?!学院)", "東京大学"),
        (r"理科大|理科大学", "東京理科大学"),
        (r"都立大", "東京都立大学"),
        (r"東京農大|農大", "東京農業大学"),
        (r"農工大", "東京農工大学"),
        (r"電通大", "電気通信大学"),
        (r"一橋大", "一橋大学"),
    ]
    for pat, rep in replacements:
        name = re.sub(pat, rep, name)
    return name.strip()


# =========================================================
# 類型 1: 団体スコア型
#   「対○○大 4-3 勝ち」「○○大学 4ー3 勝ち」
# =========================================================

# 行内に「対」が含まれる場合は「対」の直後からのみマッチ
TEAM_SCORE_WITH_TAI_RE = re.compile(
    r"対\s*([^\d\n 　が、。]{2,10}(?:大学?|院)?)[がはで]?\s*"
    r"([0-9０-９]+)\s*[-ー－]\s*([0-9０-９]+)\s*"
    r"(勝ち|負け|引[き分]|○|●|勝|負)"
)
# 「対」なし: 行頭から大学名 N-M 勝ち の形式
TEAM_SCORE_NO_TAI_RE = re.compile(
    r"^([^\d\n 　が、。]{2,10}(?:大学?|院)?)[がはで]?\s*"
    r"([0-9０-９]+)\s*[-ー－]\s*([0-9０-９]+)\s*"
    r"(勝ち|負け|引[き分]|○|●|勝|負)"
)
ROUND_PREFIX_RE = re.compile(r"^([0-9０-９]+回戦)")


def _extract_match_note(text_after: str) -> str | None:
    """スコア直後の括弧内テキスト「(村上、小金沢勝ち)」を抽出する。"""
    m = re.search(r"[（(]([^）)]+)[）)]", text_after)
    if m:
        return m.group(1).strip()
    return None


def _make_match(m: re.Match, round_str: str | None, note: str | None = None) -> dict:
    opponent = _normalize_uni(m.group(1).strip("　 "))
    rikkyo_score = _to_int(m.group(2))
    opp_score = _to_int(m.group(3))
    result_raw = m.group(4)
    if result_raw in ("勝ち", "勝", "○"):
        result = "勝ち"
    elif result_raw in ("負け", "負", "●"):
        result = "負け"
    else:
        result = "引分"
    return {
        "opponent": opponent,
        "rikkyo_score": rikkyo_score,
        "opponent_score": opp_score,
        "result": result,
        "round": round_str,
        "note": note,
        "walkover": None,
    }


def parse_team_scores(body: str) -> list[dict]:
    """
    本文から対戦相手別スコアを抽出する。
    スコアは左=立教、右=相手 で確定(§9)。
    """
    matches = []
    seen_keys: set[tuple] = set()

    for line in body.split("\n"):
        line = _normalize_score(line.strip())
        round_m = ROUND_PREFIX_RE.match(line)
        round_str = round_m.group(1) if round_m else None

        if "対" in line:
            for m in TEAM_SCORE_WITH_TAI_RE.finditer(line):
                note = _extract_match_note(line[m.end():])
                entry = _make_match(m, round_str, note)
                key = (entry["opponent"], entry["rikkyo_score"], entry["opponent_score"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    matches.append(entry)
        else:
            m = TEAM_SCORE_NO_TAI_RE.match(line)
            if m:
                note = _extract_match_note(line[m.end():])
                entry = _make_match(m, round_str, note)
                key = (entry["opponent"], entry["rikkyo_score"], entry["opponent_score"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    matches.append(entry)

    return matches


# =========================================================
# 類型 2: 回戦別型
#   「4回戦 対 法政大C 2勝0敗（不戦勝1）」
# =========================================================

ROUND_MATCH_RE = re.compile(
    r"([0-9０-９]+回戦)\s+(?:対\s*)?([^\d\n\s]{2,15})\s+"
    r"([0-9０-９]+)勝([0-9０-９]+)敗"
    r"(?:[\(（]不戦勝([0-9０-９]+)[\)）])?"
    r"(?:[\(（]不戦敗([0-9０-９]+)[\)）])?"
)


def parse_round_results(body: str) -> list[dict]:
    matches = []
    for line in body.split("\n"):
        line = _normalize_score(line.strip())
        for m in ROUND_MATCH_RE.finditer(line):
            round_str = m.group(1)
            opponent = _normalize_uni(m.group(2))
            wins = _to_int(m.group(3))
            losses = _to_int(m.group(4))
            wv_win = _to_int(m.group(5))
            wv_loss = _to_int(m.group(6))
            walkover = None
            if wv_win is not None or wv_loss is not None:
                walkover = {"win": wv_win or 0, "loss": wv_loss or 0}
            total_wins = (wins or 0) + (wv_win or 0)
            total_losses = (losses or 0) + (wv_loss or 0)
            result = "勝ち" if total_wins > total_losses else ("負け" if total_wins < total_losses else "引分")
            note = _extract_match_note(line[m.end():])
            matches.append({
                "opponent": opponent,
                "rikkyo_score": wins,
                "opponent_score": losses,
                "result": result,
                "round": round_str,
                "note": note,
                "walkover": walkover,
            })
    return matches


# =========================================================
# 類型 3: 個人別型
#   「吉武が予選1回戦突破」「斎藤、二村、吉武 予選一回戦突破」
# =========================================================

# 長い語を先に置く(「準優勝」が「優勝」にマッチしないよう)
RESULT_STR = r"予選[一二三四五六七八九十百\d]*回戦を?[突通]破|予選敗退|本戦出場|ベスト\d+|準優勝|優勝|[一二三四五六七八九十\d]+位"

PLAYER_RESULT_RE = re.compile(
    r"([^\d\s:：,、。\n]{2,5}(?:[，、,][^\d\s:：,、。\n]{2,5})*)\s*"
    r"(?:\d*[人名]?とも結果は|が予選|が本戦|は予選)?\s*"
    r"(" + RESULT_STR + r")"
)
PLAYER_WIN_RE = re.compile(
    r"([^\d\s,、。\n]{2,5})(?:が|は)\s*"
    r"(予選\d?[一二三四五六七八九十百\d]*回戦を?[突通]破|予選敗退|本戦出場|ベスト\d+|優勝|準優勝)"
)
# 「吉田：準優勝」「大平：4位」のようなコロン区切り形式
PLAYER_COLON_RE = re.compile(
    r"([^\d\s:：,、。\n]{2,5})\s*[:：]\s*(" + RESULT_STR + r")"
)
# 「久保田、吉田ともにベスト32」のような複数名+ともに形式
PLAYER_TOMONI_RE = re.compile(
    r"([^\d\s,、。\n]{2,5}(?:[，、,　][^\d\s,、。\n]{2,5})+)\s*とも(?:に|の)?\s*(" + RESULT_STR + r")"
)


# 「2日目進出：久保田4 大平2 吉田2」「1日目敗退：小金沢3」形式
DAY_PROGRESSION_RE = re.compile(
    r"(\d+日目)(進出|敗退)[：:\s]+([^\n]+)"
)


def parse_day_progression(body: str) -> list[dict]:
    """「N日目進出：名前...」形式から立教選手の進出/敗退を抽出する。"""
    players = []
    seen: set[tuple] = set()

    for line in body.split("\n"):
        for m in DAY_PROGRESSION_RE.finditer(line):
            day = m.group(1)      # 「2日目」
            status = m.group(2)   # 「進出」or「敗退」
            names_str = m.group(3)  # 「久保田4 大平2 吉田2」
            result = "本戦出場" if status == "進出" else "予選敗退"

            # 名前を抽出(苗字2-4文字 + 数字の学年は除く)
            for token in re.split(r"[\s　,、]+", names_str.strip()):
                name = re.sub(r"\d+$", "", token.strip())  # 末尾の学年数字を除去
                if name and 2 <= len(name) <= 5 and not re.match(r"^\d", name):
                    key = (name, result)
                    if key not in seen:
                        seen.add(key)
                        players.append({
                            "name": name, "result": result,
                            "wins": None, "losses": None, "board": None
                        })

    return players


def parse_individual_results(body: str) -> list[dict]:
    """個人名つき戦績を抽出する。"""
    players = []
    seen = set()

    INVALID_CONTAINS = re.compile(r"結果|参加|初日|2日目|最終|全員|が|に|も|で|と|を|[：:]")
    INVALID_NAMES = {"総合", "全", "部員"}

    def add(name: str, result: str) -> None:
        for n in re.split(r"[，、,　]", name):
            n = n.strip().rstrip("：:")  # コロンを末尾から除去
            if (n and n not in INVALID_NAMES
                    and not re.match(r"^\d", n)
                    and not INVALID_CONTAINS.search(n)
                    and 1 <= len(n) <= 8
                    and (n, result) not in seen):
                seen.add((n, result))
                players.append({"name": n, "result": result, "wins": None, "losses": None, "board": None})

    for line in body.split("\n"):
        # コロン区切り形式「吉田：準優勝」
        for m in PLAYER_COLON_RE.finditer(line):
            add(m.group(1), m.group(2))
        # ともに形式「久保田、吉田ともにベスト32」
        for m in PLAYER_TOMONI_RE.finditer(line):
            add(m.group(1), m.group(2))
        # 「が」「は」形式
        for m in PLAYER_WIN_RE.finditer(line):
            add(m.group(1), m.group(2))
        # 一般形式
        for m in PLAYER_RESULT_RE.finditer(line):
            add(m.group(1), m.group(2))

    return players


# =========================================================
# 類型 4: 非公式戦型(交流戦・古新戦等)
# =========================================================

UNOFFICIAL_KEYWORDS = re.compile(r"交流戦|練習試合|古新戦|古豪新鋭戦|非公式|フレンドリー")
OPPONENT_RE = re.compile(r"(?:対\s*|vs\.?\s*)([^\d\n　 ]{2,12}(?:大学?|大))")


def is_unofficial(subject: str, body: str) -> bool:
    return bool(UNOFFICIAL_KEYWORDS.search(subject + "\n" + body))


def parse_opponents(body: str) -> list[str]:
    """非公式戦から相手校名を抽出する。"""
    opponents = []
    seen: set[str] = set()
    for m in OPPONENT_RE.finditer(body):
        uni = _normalize_uni(m.group(1))
        if uni not in seen:
            seen.add(uni)
            opponents.append(uni)
    return opponents


# =========================================================
# 共通: 出場級・順位・日付の抽出
# =========================================================

DIVISION_RE = re.compile(r"([A-Z]\d?級|[A-Z]級)")
RANK_RE = re.compile(r"(?:最終)?順位[はが]?\s*([1-9一二三四五六七八九十]+)位|([1-9一二三四五六七八九十]+)位(?:でし|でした|$)")
DATE_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月(?:\s*(\d{1,2})日)?")


def extract_meta(subject: str, body: str) -> dict:
    combined = subject + "\n" + body
    division = None
    m = DIVISION_RE.search(combined)
    if m:
        division = m.group(1)

    rank = None
    for m in RANK_RE.finditer(combined):
        rank = m.group(1) or m.group(2)

    date_str = None
    m = DATE_RE.search(combined)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        date_str = f"{y}-{int(mo):02d}" + (f"-{int(d):02d}" if d else "")

    return {"division": division, "rank_str": rank, "date": date_str}


# =========================================================
# メイン: 1投稿を構造化
# =========================================================

def parse_post(post: dict) -> dict | None:
    """
    掲示板の1投稿を解析して bbs_detail 形式の dict を返す。
    大会結果と判断できない場合は None を返す。
    """
    subject = post.get("subject", "")
    body = post.get("body", "")
    url = post.get("url", "")

    unofficial = is_unofficial(subject, body)
    team_matches = parse_team_scores(body)
    round_matches = parse_round_results(body)
    all_matches = team_matches + round_matches
    players = parse_individual_results(body)
    if not players:
        players = parse_day_progression(body)
    opponents = parse_opponents(body) if (unofficial and not all_matches) else []
    meta = extract_meta(subject, body)

    if not all_matches and not players and not opponents:
        return None

    return {
        "post_id": post.get("id"),
        "subject": subject,
        "date": meta["date"],
        "division": meta["division"],
        "bbs_detail": {
            "source_url": url,
            "is_official": not unofficial,
            "opponents": opponents,
            "matches": all_matches,
            "players": players,
            "comment": "",
        },
    }
