"""社団戦(東将連) 個人レーティング推移の抽出 — 公開同意者のみ。

【重要・ROADMAP §2-2】個人の実名・レーティングは原則コミットしない。
本スクリプトが出力する data/shadan/players/*.json は、
**本人の同意(依頼)を得て公開サイトに掲載すると決めた人の分のみ**。
登録番号(reg_no)は年をまたぐ安定キーとしてデータには保持するが、
公開ページには表示しない。

レーティング(新持点)の公開PDFは第33回(全部門一覧)・第34回(部別)のみ確認。
それ以前(第22〜30回)の順位表PDFに個人レーティングは掲載されておらず、
第31回のA/B表・第32回一覧、コロナ期個人戦(K1/K2)にも対象者の記載なし。
"""

import io
import json
from pathlib import Path

import pdfplumber

from common import logger, validate_json
import fetch_shadan

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "shadan" / "players"
SCHEMA = ROOT / "data" / "shadan" / "player.schema.json"
BASE = "https://toushouren.world.coocan.jp/shadan"

# 公開同意者。reg_no で各回のランキングPDFを検索する。
# sources: (kai, season, season_label, PDF相対パス)
CONSENTED = [
    {
        "player_id": "kubota-kosuke",
        "name": "久保田 耕介",
        "reg_no": 8855,
        "consent": "本人の依頼により公開(2026-07-18)",
        "sources": [
            (33, "R06", "令和6年度", "33/33_ranking_04_all.pdf"),
            (34, "R07", "令和7年度", "34/34_ranking_04_l6r.pdf"),
        ],
    },
]


def find_in_ranking(pdf_bytes: bytes, reg_no: int) -> dict | None:
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


if __name__ == "__main__":
    fetch_shadan.ensure_reachable()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in CONSENTED:
        history = []
        for kai, season, season_label, rel in spec["sources"]:
            url = f"{BASE}/{rel}"
            row = find_in_ranking(fetch_shadan.fetch_pdf(url), spec["reg_no"])
            if row is None:
                raise SystemExit(
                    f"{spec['name']} (reg {spec['reg_no']}) が {rel} に見つかりません。"
                    " 掲載形式の変更の可能性があるため停止。"
                )
            history.append({
                "kai": kai, "season": season, "season_label": season_label,
                "team": row["team"], "division": row["division"],
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
