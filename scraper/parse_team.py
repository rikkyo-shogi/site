"""団体戦PDF/HTMLパーサー: 関東連盟マトリクス形式から立教大学の成績を抽出する。"""

import re
from collections import defaultdict
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup

from common import decode_html, is_rikkyo, logger

PROMOTION_KEYWORDS = {"昇級", "降級", "優勝", "準優勝"}
ROUND_ROBIN_HEADERS = re.compile(r"勝点|勝数|順位")


def _group_words_by_line(page, tolerance: int = 5) -> list[list[str]]:
    """ページの単語を y 座標でグルーピングして行リストに変換する。"""
    words = page.extract_words()
    rows: dict[int, list[str]] = defaultdict(list)
    for w in words:
        key = round(w["top"] / tolerance) * tolerance
        rows[key].append(w["text"])
    return [rows[k] for k in sorted(rows.keys())]


def _parse_rikkyo_row(tokens: list[str]) -> dict | None:
    """
    立教を含む行トークンから成績を抽出する。
    形式: [seeding] [name] [N-1 opponent scores] [勝数] [勝点] [順位] [入れ替え?]
    右端から解析する。「8降」のような複合トークンや浮動小数点ゴミにも対応。
    """
    promotion = None

    # 末尾の整数でないゴミ(浮動小数点・座標等)を除去
    # ただし「8降」「1昇」のような複合トークンは有効
    while tokens:
        last = tokens[-1]
        if (re.match(r"^\d+$", last)
                or last in PROMOTION_KEYWORDS
                or re.match(r"^[昇降優準]", last)
                or re.match(r"^(\d+)(昇|降|昇級|降級|優勝|準優勝)$", last)):
            break
        tokens = tokens[:-1]

    if not tokens:
        return None

    # 右端が昇降級ワードなら取る
    if tokens[-1] in PROMOTION_KEYWORDS:
        promotion = tokens[-1]
        tokens = tokens[:-1]
    # 「8降」「1昇」のような複合トークンを分離
    elif re.match(r"^(\d+)(昇|降|昇級|降級|優勝|準優勝)$", tokens[-1]):
        m = re.match(r"^(\d+)(昇|降|昇級|降級|優勝|準優勝)$", tokens[-1])
        promotion = "昇級" if "昇" in m.group(2) else "降級"
        tokens = tokens[:-1] + [m.group(1)]

    # 以降: [...scores...] 勝数 勝点 順位
    if len(tokens) < 3:
        return None

    try:
        rank = int(tokens[-1])
        points = int(tokens[-2])    # 勝点(ボード合計)
        wins_matches = int(tokens[-3])  # 勝数(試合勝数)
    except (ValueError, IndexError):
        return None

    return {
        "rank": rank,
        "wins": wins_matches,
        "losses": None,
        "points": points,
        "promotion": promotion,
        "note": "",
    }


DIVISION_RE = re.compile(
    r"([A-ZＡ-Ｚ][0-9０-９]?(?:\s*[0-9０-９])?[級])"
)


def _normalize_division(div: str) -> str:
    """全角文字の級名を半角に正規化する。"""
    div = div.translate(str.maketrans("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃ０１２３４５６７８９　",
                                       "ABCDEFGHIJKLMNOPQRSTUVWXYZabc0123456789 "))
    return div.strip()


def _find_division(lines: list[list[str]], rikkyo_line_idx: int) -> str | None:
    """立教行の上方向に走査して直近の級名(A級/B2級等)を探す。半角・全角両対応。"""
    for i in range(rikkyo_line_idx - 1, -1, -1):
        text = " ".join(lines[i])
        m = DIVISION_RE.search(text)
        if m:
            return _normalize_division(m.group(1))
    return None


def parse_team_pdf(pdf_path: Path, event_name: str) -> dict | None:
    """
    団体戦 PDF を解析し、立教の成績を返す。
    立教が出場していない場合は None を返す。
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = _group_words_by_line(page)
            for idx, tokens in enumerate(lines):
                line_text = " ".join(tokens)
                if not is_rikkyo(line_text):
                    continue
                # ヘッダー行(列名として「立教」が出る)はスキップ
                if "勝点" in tokens or "勝数" in tokens:
                    continue

                result = _parse_rikkyo_row(tokens[:])
                if result is None:
                    logger.warning("立教行の解析失敗: %s", line_text)
                    continue

                division = _find_division(lines, idx)
                logger.info("立教発見: %s %s rank=%s wins=%s points=%s promotion=%s",
                            event_name, division or "?",
                            result["rank"], result["wins"], result["points"], result["promotion"])
                return {"division": division, "result": result}

    return None


def parse_team_html(html_path: Path, event_name: str) -> dict | None:
    """
    団体戦 HTML(Excel 由来の表)を解析し、立教の成績を返す。
    ＼ が対角線マーカー。右端から 順位・勝点・勝数 を読む。
    """
    raw = html_path.read_bytes()
    html = decode_html(raw)
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        last_header_cells: list[str] = []
        division = None
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if not cells:
                continue

            # ヘッダー行(勝点/勝数を含む行)を記憶
            joined = " ".join(cells)
            if "勝点" in joined or "勝数" in joined:
                last_header_cells = cells
                m = DIVISION_RE.search(joined)
                if m:
                    division = _normalize_division(m.group(1))
                continue

            # 立教行かチェック
            if not is_rikkyo(joined):
                continue

            # 立教大学が見つかった列インデックスを特定
            rikkyo_idx = next(
                (i for i, c in enumerate(cells) if is_rikkyo(c)), 0
            )
            relevant_cells = cells[rikkyo_idx:]  # 立教大学セルから右側

            # ヘッダー行で立教列より手前にある最後の division ラベルを探す
            if last_header_cells:
                best_div = None
                for col_i, hcell in enumerate(last_header_cells):
                    m = DIVISION_RE.match(hcell.strip())
                    if m and col_i <= rikkyo_idx:
                        best_div = _normalize_division(m.group(1))
                if best_div:
                    division = best_div

            # ＼(対角線)を除去して数値のみ抽出
            nums = [c for c in relevant_cells[1:] if c and c not in ("＼", "\\", "／", "")]
            try:
                # 順位セルが「2昇」「3降」のように promotion を含む場合を分離
                promotion = None
                rank_raw = None
                clean_nums = []
                for n in nums:
                    if re.match(r"^\d+$", n):
                        clean_nums.append(int(n))
                    elif re.match(r"^(\d+)(昇|降|昇級|降級|優勝|準優勝)", n):
                        m_p = re.match(r"^(\d+)(昇|降|昇級|降級|優勝|準優勝)", n)
                        rank_raw = int(m_p.group(1))
                        promo_char = m_p.group(2)
                        promotion = "昇級" if "昇" in promo_char else "降級"
                    elif n in PROMOTION_KEYWORDS:
                        promotion = n

                if rank_raw is not None:
                    # 順位が別セル(rank_raw)に入っている場合:
                    # clean_nums は [...scores, 勝数, 勝点]
                    rank = rank_raw
                    points = clean_nums[-1] if clean_nums else None
                    wins_matches = clean_nums[-2] if len(clean_nums) >= 2 else None
                else:
                    # 順位が clean_nums の末尾にある場合:
                    # clean_nums は [...scores, 勝数, 勝点, 順位]
                    rank = clean_nums[-1]
                    points = clean_nums[-2] if len(clean_nums) >= 2 else None
                    wins_matches = clean_nums[-3] if len(clean_nums) >= 3 else None
            except (ValueError, IndexError):
                logger.warning("HTML立教行の解析失敗: %s", cells[:8])
                continue

            logger.info("立教発見(HTML): %s %s rank=%s wins=%s points=%s",
                        event_name, division or "?", rank, wins_matches, points)
            return {"division": division, "result": {
                "rank": rank,
                "wins": wins_matches,
                "losses": None,
                "points": points,
                "promotion": promotion,
                "note": "",
            }}

    return None


def extract_team_losses(result: dict, total_teams: int | None = None) -> dict:
    """勝数と総チーム数から負数を補完する(可能な場合)。"""
    r = result.copy()
    if r.get("wins") is not None and total_teams is not None:
        r["losses"] = (total_teams - 1) - r["wins"]
    return r
