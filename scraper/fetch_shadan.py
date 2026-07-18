"""社団戦(東将連)PDF取得。

`common.py` のキャッシュ・スリープ・リトライ作法を踏襲する
(取得は `common.fetch` に委譲し、`cache/shadan/` に保存)。
着手時に §1.5.1 に準じて対象ドメインへの到達確認を行い、
不達ならダミーデータで進めず停止する。到達確認はキャッシュを経由せず
毎回実際にネットワークへ出る(キャッシュヒットで素通りさせない)。

第34回(令和7年度)を対象とする。回によってチーム数・所属部は変わるため、
所属部(division)は順位一覧PDFの実データから毎回決定し、部別個人ランキングの
PDFファイル名(l3w 等)もその division から導出する(コードに固定しない)。
"""

import requests

from common import SESSION, fetch, logger

HUB_URL = "https://toushouren.world.coocan.jp/shadan/sub9-R07.htm"
BASE = "https://toushouren.world.coocan.jp/shadan/34"
EDITION = "04"  # 最終節(第4節)の集計
REACH_HOST = "toushouren.world.coocan.jp"

# 順位一覧表(全リーグの最終順位・勝点・勝数・昇降)。チーム成績の一次情報。
ICHIRAN_URL = f"{BASE}/34_ichiran_{EDITION}.pdf"

# リーグ表(対戦表)。league_table 対応(将来)まで解析しないため取得もしない。
# R07.json の source メタデータとしてURLのみ記録する。
LEAGUE_URLS = [
    f"{BASE}/34_league_{EDITION}_u.pdf",  # 通常版
    f"{BASE}/34_league_{EDITION}_g.pdf",  # 成績順
]


def ranking_url(suffix: str) -> str:
    """部別個人ランキングPDFのURL。suffix は division から導出した 'l3w' 等。"""
    return f"{BASE}/34_ranking_{EDITION}_{suffix}.pdf"


def check_reachable() -> bool:
    """対象ドメインへ実際に到達できるか確認する(§1.5.1)。キャッシュは使わない。"""
    try:
        resp = SESSION.get(HUB_URL, timeout=20)
        resp.raise_for_status()
        ok = True
    except requests.RequestException as e:
        logger.warning("reachability check failed: %s", e)
        ok = False
    logger.info("reachability %s: %s", REACH_HOST, "OK" if ok else "NG")
    return ok


def ensure_reachable() -> None:
    """到達不可ならダミーデータで進めず停止する(§1.5.1)。"""
    if not check_reachable():
        raise SystemExit(
            f"到達不可: {REACH_HOST}. §1.5.1 によりダミーデータで進めず停止する。"
            " ネットワーク設定で当該ドメインを許可してから再実行すること。"
        )


def fetch_pdf(url: str) -> bytes:
    """PDFを1件取得する(キャッシュ利用)。失敗したら停止。"""
    raw = fetch(url, subdir="shadan")
    if raw is None:
        raise SystemExit(f"取得失敗: {url}")
    return raw


if __name__ == "__main__":
    ensure_reachable()
    print(f"ichiran: {len(fetch_pdf(ICHIRAN_URL))} bytes")
