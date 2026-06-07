"""個人戦PDFパーサー: トーナメント表・リーグ表から立教選手を抽出する。"""

import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

from common import is_rikkyo, logger

# 立教選手を示すパターン: 「氏名 (立教N)」「氏名(立教大N)」等
# 改行・閉じ括弧を名前に含めないよう除外。「（立教大学2年）」の「年」にも対応
RIKKYO_PLAYER_RE = re.compile(
    r"([^\s(（)）]+(?:[ \t]+[^\s(（)）]+)?)\s*[（(]立教(?:大学?)?(\d+)?年?[）)]"
)

# トップ成績の行: 優勝/準優勝/3位/4位/5位 etc.
TOP_RESULT_RE = re.compile(r"^(優勝|準優勝|([1-9３４５]位|3位|4位|5位))\s+(.+)")

# ベスト◯ の語彙マッピング（トーナメント深さ → 語彙）
# 64人トーナメント: 6回戦
# 32人トーナメント: 5回戦
DEPTH_TO_RESULT = {
    0: "出場",
    1: "本戦出場",    # 1回戦負け
    2: "ベスト16",    # 2回戦負け (実際には32〜64人規模で変動)
    3: "ベスト8",
    4: "ベスト4",
    5: "準優勝",
    6: "優勝",
}

RESULT_VOCAB = {"優勝", "準優勝", "第三位", "ベスト4", "ベスト8", "ベスト16", "本戦出場", "予選敗退", "出場"}


def _group_words_by_line(page, tolerance: int = 5) -> list[list[str]]:
    words = page.extract_words()
    rows: dict[int, list[str]] = defaultdict(list)
    for w in words:
        key = round(w["top"] / tolerance) * tolerance
        rows[key].append(w["text"])
    return [rows[k] for k in sorted(rows.keys())]


def _extract_players_from_text(text: str) -> list[dict]:
    """
    テキスト全体から 立教選手 を全て検索し、名前と出現回数を返す。
    出現回数が多いほど深いラウンドまで進んだと推定する。
    """
    players: dict[str, dict] = {}

    for m in RIKKYO_PLAYER_RE.finditer(text):
        raw_name = m.group(1).strip()
        # 先頭のシード番号を除去(例: "10 福田" → "福田")
        name = re.sub(r"^\d+\s+", "", raw_name).strip()
        grade_str = m.group(2)
        grade = int(grade_str) if grade_str else None
        if name not in players:
            players[name] = {"name": name, "grade": grade, "appearances": 1}
        else:
            players[name]["appearances"] += 1

    return list(players.values())


def _count_name_occurrences(name: str, text: str) -> int:
    """選手の姓(苗字)がブラケット本文中に何回登場するかを数える。"""
    surname = name.split()[0] if " " in name else name
    # 括弧内の表記を除く純粋なブラケット内の勝者表示のみカウント
    # 大学表記付きはカウント除外
    bracket_occurrences = re.findall(
        rf"(?<![（(])(?<!\w){re.escape(surname)}(?!\s*[（(])(?!\w)", text
    )
    return len(bracket_occurrences)


def _check_top_results(text: str) -> dict[str, str]:
    """
    PDF/HTML冒頭の入賞者一覧から立教選手の最終成績を読む。
    古いHTMLでは結果ラベルと選手名が別行なため前後2行も確認する。
    {名前: 成績} を返す。
    """
    result_map: dict[str, str] = {}
    result_vocab = {
        "優勝": "優勝", "準優勝": "準優勝",
        "3位": "第三位", "三位": "第三位",
        "4位": "ベスト4", "5位": "ベスト8",
    }

    lines = text.split("\n")[:300]  # 入賞者一覧は長い HTML で遅れることがある
    for i, line in enumerate(lines):
        if not is_rikkyo(line):
            continue
        # 同行 or 前5行以内に入賞ラベルがあるか確認(空行を挟む場合に対応)
        # 長いキー優先でチェック(準優勝 > 優勝 などの包含関係を回避)
        sorted_vocab = sorted(result_vocab.items(), key=lambda x: -len(x[0]))
        for back in range(0, 6):
            if i - back < 0:
                break
            check_line = lines[i - back].strip()
            for key, val in sorted_vocab:
                # 行に完全に含まれ、かつ前後が非文字であることを確認
                if re.search(r"(?<![^\s])" + re.escape(key) + r"(?![^\s])", check_line):
                    m = RIKKYO_PLAYER_RE.search(line)
                    if m:
                        name = re.sub(r"^\d+\s+", "", m.group(1).strip())
                        if name not in result_map:
                            result_map[name] = val
                    break

    return result_map


def _is_round_robin(text: str) -> bool:
    """テキストが総当たりリーグ(round-robin)形式かどうかを判定する。"""
    return bool(re.search(r"[○◯×][　\s]*[○◯×]", text))


def _parse_round_robin(text: str, lines: list[list[str]]) -> list[dict]:
    """
    総当たりリーグ形式の個人戦(女流戦等)から立教選手を抽出する。
    形式: N 氏名(大学年) × ◯ ... 勝数 順位
    """
    players = []
    for tokens in lines:
        line = " ".join(tokens)
        if not is_rikkyo(line):
            continue
        m = RIKKYO_PLAYER_RE.search(line)
        if not m:
            continue
        raw_name = m.group(1).strip()
        name = re.sub(r"^\d+\s+", "", raw_name).strip()
        grade_str = m.group(2)
        grade = int(grade_str) if grade_str else None

        # 右端から: 順位 勝数 [○×...]
        nums = [t for t in tokens if re.match(r"^\d+$", t)]
        rank = int(nums[-1]) if len(nums) >= 1 else None
        wins = int(nums[-2]) if len(nums) >= 2 else None

        # ベスト○ に変換
        if rank == 1:
            best = "優勝"
        elif rank == 2:
            best = "準優勝"
        elif rank == 3:
            best = "第三位"
        else:
            best = f"{rank}位" if rank else "出場"

        players.append({"name": name, "grade": grade, "best_result": best, "rank": rank})
        logger.info("  立教選手(RR): %s 学年%s rank=%s best=%s", name, grade, rank, best)

    return players


def _parse_tournament_bracket(text: str, lines: list[list[str]]) -> list[dict]:
    """
    トーナメント表から立教選手を抽出する。
    出現回数(勝利数)からラウンド深さを推定する。
    """
    # まずトップ成績を確認
    top_results = _check_top_results(text)

    # 立教選手の初出現情報を収集
    raw_players = _extract_players_from_text(text)
    if not raw_players:
        return []

    # 総選手数を推定(行数 or シード番号から)
    seedings = [int(t) for toks in lines for t in toks if re.match(r"^\d{1,3}$", t)]
    max_seed = max(seedings) if seedings else 64
    total_rounds = (max_seed - 1).bit_length()  # log2(N) に相当

    result = []
    for p in raw_players:
        name = p["name"]
        grade = p["grade"]

        # トップ成績リストに載っているなら優先
        if name in top_results:
            best = top_results[name]
            rank = {"優勝": 1, "準優勝": 2, "第三位": 3}.get(best)
            result.append({"name": name, "grade": grade, "best_result": best, "rank": rank})
            logger.info("  立教選手(T): %s 学年%s best=%s(top列挙)", name, grade, best)
            continue

        # 括弧なし登場回数を数えてラウンド推定
        surname = name.split()[0] if " " in name else name
        bracket_count = len(re.findall(
            rf"(?<!\w){re.escape(surname)}(?!\s*[（(（])(?!\w)", text
        ))
        # 初出現(シード表記)を1として、追加登場 = 勝利数
        wins = max(0, bracket_count - 1)
        # 全員がトーナメント出場者なので最低でも本戦出場
        if wins == 0:
            best = "本戦出場"
        elif wins >= total_rounds - 1:
            best = "優勝"
        elif wins >= total_rounds - 2:
            best = "準優勝"
        else:
            best = DEPTH_TO_RESULT.get(wins, "本戦出場")

        result.append({"name": name, "grade": grade, "best_result": best, "rank": None})
        logger.info("  立教選手(T): %s 学年%s bracket出現%d → %s", name, grade, bracket_count, best)

    return result


def parse_individual_pdf(pdf_path: Path, event_name: str) -> list[dict]:
    """
    個人戦 PDF を解析し、立教選手リストを返す。
    [{"name": str, "grade": int|None, "best_result": str, "rank": int|None}, ...]
    """
    full_text = ""
    all_lines: list[list[str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"
            all_lines.extend(_group_words_by_line(page))

    if not is_rikkyo(full_text):
        return []

    if _is_round_robin(full_text):
        players = _parse_round_robin(full_text, all_lines)
    else:
        players = _parse_tournament_bracket(full_text, all_lines)

    if not players:
        # フォールバック: 立教選手名だけ取れる場合
        for m in RIKKYO_PLAYER_RE.finditer(full_text):
            name = re.sub(r"^\d+\s+", "", m.group(1).strip())
            players.append({
                "name": name,
                "grade": int(m.group(2)) if m.group(2) else None,
                "best_result": "出場",
                "rank": None,
            })

    return players


def _merge_multiline_players(text: str) -> str:
    """
    古い HTML では名前・姓/名・(大学) が別行に分割されることがある。
    `(立教...)` の直前行をマージして1行化することで正規表現マッチを可能にする。
    例: 「久保田\n耕介\n(立教)」 → 「久保田 耕介(立教)」
    """
    lines = text.split("\n")
    out = []
    i = 0
    RIKKYO_BRACKET = re.compile(r"^[（(]立教(?:大学?)?(\d+)?年?[）)]")
    while i < len(lines):
        line = lines[i].strip()
        if RIKKYO_BRACKET.match(line):
            # 直前の非空行を最大2つ走査して名前パーツを収集(空行はスキップ)
            parts = []
            j = i - 1
            found = 0
            while j >= 0 and found < 2:
                prev = lines[j].strip()
                j -= 1
                if not prev:
                    continue  # 空行はスキップ
                if re.match(r"^[^\d(（)）\s]{1,6}$", prev):
                    parts.insert(0, prev)
                    found += 1
                else:
                    break
            if parts:
                # out から対応行を除去(空行を除く実非空行を parts 数分削除)
                removed = 0
                while removed < len(parts) and out:
                    popped = out.pop()
                    if popped.strip():
                        removed += 1
                out.append(" ".join(parts) + line)
            else:
                out.append(line)
        else:
            out.append(line)
        i += 1
    return "\n".join(out)


def parse_individual_html(html_path: Path, event_name: str) -> list[dict]:
    """
    個人戦 HTML を解析し、立教選手リストを返す。
    古い HTML の多行分割に対応し、テキスト化後は PDF と同じロジックを使う。
    """
    from bs4 import BeautifulSoup
    raw = html_path.read_bytes()
    from common import decode_html
    html = decode_html(raw)

    if not is_rikkyo(html):
        return []

    soup = BeautifulSoup(html, "html.parser")
    raw_text = soup.get_text(separator="\n")

    # 複数行に分割された「姓\n名\n(立教)」を1行化
    full_text = _merge_multiline_players(raw_text)

    all_lines = [[t] for t in full_text.split("\n") if t.strip()]

    if _is_round_robin(full_text):
        players = _parse_round_robin(full_text, all_lines)
    else:
        players = _parse_tournament_bracket(full_text, all_lines)

    if not players:
        for m in RIKKYO_PLAYER_RE.finditer(full_text):
            name = re.sub(r"^\d+\s+", "", m.group(1).strip())
            players.append({
                "name": name,
                "grade": int(m.group(2)) if m.group(2) else None,
                "best_result": "出場",
                "rank": None,
            })

    return players
