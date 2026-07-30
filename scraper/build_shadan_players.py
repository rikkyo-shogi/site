"""社団戦(東将連) 個人レーティング推移の抽出 — 公開同意者のみ。

【重要・ROADMAP §2-2】個人の実名・レーティングは原則コミットしない。
本スクリプトが出力する data/shadan/players/*.json は、
**本人の同意(依頼)を得て公開サイトに掲載すると決めた人の分のみ**。
登録番号(reg_no)は年をまたぐ安定キーとしてデータには保持するが、
公開ページには表示しない。

レーティング(新持点)は2種類の資料形式で公開されている(2026-07 調査):
  - PDF「全部門一覧」「部別ランキング」(第32〜34回): 表形式のテキスト抽出
  - HTML「参加者全員のランキング」(第20〜30回): <PRE>タグの固定幅テキスト
    (第17〜19回・第31回・第32回一覧には対象者の記載なし。
     コロナ期個人戦(K1/K2)は社団戦本戦ではないため対象外)
"""

import io
import json
import re
from pathlib import Path

import pdfplumber

from common import fetch_html, logger, validate_json
import fetch_shadan

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "shadan" / "players"
SCHEMA = ROOT / "data" / "shadan" / "player.schema.json"

# 公開同意者。reg_no で各回のランキング資料(PDF/HTML)を検索する。
# sources: (kai, season, season_label, 資料の絶対URL)
CONSENTED = [
    {
        "player_id": "kubota-kosuke",
        "name": "久保田 耕介",
        "reg_no": 8855,
        "consent": "本人の依頼により公開(2026-07-18)",
        "sources": [
            (20, "H21", "平成21年度", "https://toushouren.world.coocan.jp/shadan/20/20junni2.htm"),
            (21, "H22", "平成22年度", "https://toushouren.world.coocan.jp/shadan/21/21junni2.htm"),
            (22, "H23", "平成23年度", "https://toushouren.world.coocan.jp/shadan/22/22juni5_2_2.htm"),
            (23, "H24", "平成24年度", "https://toushouren.world.coocan.jp/shadan/23/23juni5_2_2.htm"),
            (24, "H25", "平成25年度", "https://toushouren.world.coocan.jp/shadan/24/24juni55_2_2.htm"),
            (25, "H26", "平成26年度", "https://toushouren.world.coocan.jp/shadan/25/25juni5_2_2.htm"),
            (26, "H27", "平成27年度", "https://toushouren.world.coocan.jp/shadan/26/26juni5_3_3.htm"),
            (27, "H28", "平成28年度", "https://toushouren.world.coocan.jp/shadan/27/1611091540_3_1540.htm"),
            (28, "H29", "平成29年度", "https://toushouren.world.coocan.jp/shadan/28/1802071815_2_770.htm"),
            (29, "H30", "平成30年度", "https://toushouren.world.coocan.jp/shadan/29/1812061710_2_772.htm"),
            (30, "R01", "令和元年度", "https://toushouren.world.coocan.jp/shadan/30/2009251507_2_776.htm"),
            (33, "R06", "令和6年度", "https://toushouren.world.coocan.jp/shadan/33/33_ranking_04_all.pdf"),
            (34, "R07", "令和7年度", "https://toushouren.world.coocan.jp/shadan/34/34_ranking_04_l6r.pdf"),
        ],
    },
]


def find_in_pdf_ranking(pdf_bytes: bytes, reg_no: int) -> dict | None:
    """ランキングPDFから登録番号一致の行を探し {rating, games, team, division} を返す。

    列構成(確認済み):
      部別:   順位 登録番号 氏名 新持点 通算対局数 チーム名
      全部門: 順位 登録番号 氏名 持点 通算対局数 クラス チーム名 (クラス例「５部（白）」)
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for ln in (page.extract_text() or "").splitlines():
                toks = ln.split()
                if len(toks) < 6 or not (toks[0].isdigit() and toks[1].isdigit()):
                    continue
                if int(toks[1]) != reg_no:
                    continue
                # 右から: チーム名 / (クラス) / 通算対局数 / 持点
                if toks[-2].isdigit() and toks[-3].isdigit():
                    # 部別形式: ... 持点 対局数 チーム名
                    return {"rating": int(toks[-3]), "games": int(toks[-2]),
                            "team": toks[-1], "division": None}
                if len(toks) >= 7 and toks[-3].isdigit() and toks[-4].isdigit():
                    # 全部門形式: ... 持点 対局数 クラス チーム名
                    division = toks[-2].replace("（", "").replace("）", "")
                    return {"rating": int(toks[-4]), "games": int(toks[-3]),
                            "team": toks[-1], "division": division}
    return None


# HTML版「参加者全員のランキング」(<PRE>固定幅テキスト)の列構成:
# 順位 会員番号 氏名(姓+全角スペース+名) 点数 全局数 リーグ 所属チーム名
HTML_ROW_RE = re.compile(
    r"(?P<reg>\d+)\s+(?P<name>\S+(?:\s\S+)?)\s{2,}"
    r"(?P<rating>\d+)\s+(?P<games>\d+)\s+(?P<division>\S+)\s+(?P<team>\S.*)"
)


def find_in_html_ranking(html_text: str, reg_no: int) -> dict | None:
    """<PRE>形式のランキングHTMLから登録番号一致の行を探す。"""
    for ln in html_text.splitlines():
        if str(reg_no) not in ln:
            continue
        m = HTML_ROW_RE.search(ln)
        if m and int(m.group("reg")) == reg_no:
            return {
                "rating": int(m.group("rating")),
                "games": int(m.group("games")),
                "division": m.group("division"),
                "team": m.group("team").strip(),
            }
    return None


def find_in_ranking(url: str, reg_no: int) -> dict | None:
    if url.endswith(".pdf"):
        return find_in_pdf_ranking(fetch_shadan.fetch_pdf(url), reg_no)
    text = fetch_html(url, subdir="shadan")
    if text is None:
        raise SystemExit(f"取得失敗: {url}")
    return find_in_html_ranking(text, reg_no)


# 部別ランキングPDFのファイル名サフィックス(例: ..._l6r.pdf → 6部赤)。
# parse_shadan.py の division→suffix 変換(l{部}{r|w})の逆変換。
DIVISION_SUFFIX_RE = re.compile(r"_l(\d+)([rw])?\.pdf$")
ZEN2HAN_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def division_from_url(url: str) -> str | None:
    """部別ランキングPDF(全部門一覧のような division 列を持たない形式)のURLから所属部を復元する。"""
    m = DIVISION_SUFFIX_RE.search(url)
    if not m:
        return None
    bu, color = m.groups()
    return f"{bu}部" + {"r": "赤", "w": "白"}.get(color, "")


def normalize_division(division: str | None) -> str | None:
    """全角数字・全角/半角括弧の表記ゆれを吸収し、サイト他所と同じ「4部白」形式に揃える。"""
    if division is None:
        return None
    d = division.translate(ZEN2HAN_DIGITS)
    for ch in "（）()":
        d = d.replace(ch, "")
    return d


if __name__ == "__main__":
    fetch_shadan.ensure_reachable()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in CONSENTED:
        history = []
        for kai, season, season_label, url in spec["sources"]:
            row = find_in_ranking(url, spec["reg_no"])
            if row is None:
                raise SystemExit(
                    f"{spec['name']} (reg {spec['reg_no']}) が {url} に見つかりません。"
                    " 掲載形式の変更の可能性があるため停止。"
                )
            division = normalize_division(row["division"] or division_from_url(url))
            history.append({
                "kai": kai, "season": season, "season_label": season_label,
                "team": row["team"], "division": division,
                "rating": row["rating"], "games": row["games"],
                "source_url": url,
            })
        data = {
            "player_id": spec["player_id"],
            "name": spec["name"],
            "reg_no": spec["reg_no"],
            "consent": spec["consent"],
            "history": history,
        }
        errors = validate_json(data, SCHEMA)
        if errors:
            raise SystemExit(f"{spec['player_id']}: スキーマ検証エラー: {errors}")
        out = OUT_DIR / f"{spec['player_id']}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("saved %s (%d point(s))", out.name, len(history))
        print(f"{spec['name']}: " + ", ".join(
            f"第{h['kai']}回 R{h['rating']}({h['games']}局)" for h in history))
