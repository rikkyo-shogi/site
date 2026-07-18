"""社団戦(東将連)PDF取得。

`common.py` のキャッシュ・スリープ・リトライ作法を踏襲する
(取得は `common.fetch` に委譲し、`cache/shadan/` に保存)。
着手時に §1.5.1 に準じて対象ドメインへの到達確認を行い、
不達ならダミーデータで進めず停止する。

第34回(令和7年度)を対象とする。回によってチーム数・所属部は変わるため、
所属部(division)や個人ランキングのリーグ指定は取り込みのたびに確認すること。
"""

from common import fetch, logger

HUB_URL = "https://toushouren.world.coocan.jp/shadan/sub9-R07.htm"
BASE = "https://toushouren.world.coocan.jp/shadan/34"
EDITION = "04"  # 最終節(第4節)の集計
REACH_HOST = "toushouren.world.coocan.jp"

# 第34回で取得するPDF群。
# 立教の2チームの所属部(2026-07 時点の順位一覧PDFで確認):
#   立教大学紫龍会 = 3部リーグ白 → 個人ランキングは l3w
#   紫龍会         = 6部リーグ赤 → 個人ランキングは l6r
#   ※ 課題前提では紫龍会=5部赤とされていたが、順位一覧PDFでは6部赤(前年5部白13位→降級)。
#     個人ランキングも l5r には無く l6r に掲載されている。
PDF_URLS = {
    "ichiran": f"{BASE}/34_ichiran_{EDITION}.pdf",       # 全リーグ最終順位・勝点・勝数・昇降
    "league_u": f"{BASE}/34_league_{EDITION}_u.pdf",      # リーグ表(通常版・対戦表)
    "league_g": f"{BASE}/34_league_{EDITION}_g.pdf",      # リーグ表(成績順)
    "ranking_l3w": f"{BASE}/34_ranking_{EDITION}_l3w.pdf",  # 3部白: 立教大学紫龍会
    "ranking_l6r": f"{BASE}/34_ranking_{EDITION}_l6r.pdf",  # 6部赤: 紫龍会
}


def check_reachable() -> bool:
    """対象ドメインへ到達できるか(ハブページ取得可否)で確認する。"""
    raw = fetch(HUB_URL, subdir="shadan")
    ok = raw is not None
    logger.info("reachability %s: %s", REACH_HOST, "OK" if ok else "NG")
    return ok


def fetch_all() -> dict[str, bytes]:
    """必要なPDFをすべて取得して {key: bytes} を返す。到達不可なら停止。"""
    if not check_reachable():
        raise SystemExit(
            f"到達不可: {REACH_HOST}. §1.5.1 によりダミーデータで進めず停止する。"
            " ネットワーク設定で当該ドメインを許可してから再実行すること。"
        )
    out: dict[str, bytes] = {}
    for key, url in PDF_URLS.items():
        raw = fetch(url, subdir="shadan")
        if raw is None:
            raise SystemExit(f"取得失敗: {url}")
        out[key] = raw
    return out


if __name__ == "__main__":
    for k, v in fetch_all().items():
        print(f"{k}: {len(v)} bytes")
