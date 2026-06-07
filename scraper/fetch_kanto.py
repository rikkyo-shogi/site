"""関東連盟: 起点ページから全年度を発見し、大会ファイルをダウンロードしてインデックスを出力する。"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from common import fetch, fetch_html, logger, CACHE_DIR

START_URL = "http://kantoshogi.web.fc2.com/kekka/R08/R08kekka.html"
BASE_URL = "http://kantoshogi.web.fc2.com/kekka/"
DATA_DIR = Path(__file__).parent.parent / "data"


def season_from_url(url: str) -> str:
    """URL のディレクトリ部分から年度キー(R08, H30 等)を抽出する。"""
    parts = urlparse(url).path.strip("/").split("/")
    # /kekka/R08/... → parts = ['kekka', 'R08', ...]
    for part in parts:
        if re.match(r"^(R|H)\d{2}$", part, re.IGNORECASE):
            return part.upper()
    return "UNKNOWN"


def season_label(key: str) -> str:
    """年度キーを表示用ラベルに変換する。例: R08→令和8年度、H30→平成30年度。"""
    m = re.match(r"^(R|H)(\d+)$", key, re.IGNORECASE)
    if not m:
        return key
    era = "令和" if m.group(1).upper() == "R" else "平成"
    num = int(m.group(2))
    return f"{era}{num}年度"


def infer_event_type(name: str) -> tuple[str, str | None]:
    """大会名から type と division を推定する。"""
    if "団体" in name:
        t = "team"
        div = None
        for grade in ("A級", "B1級", "B2級", "B級", "C級"):
            if grade in name:
                div = grade
                break
        return t, div
    return "individual", None


def infer_season_half(name: str) -> str | None:
    if "春" in name:
        return "spring"
    if "秋" in name:
        return "autumn"
    return None


def discover_season_urls(start_url: str) -> dict[str, str]:
    """起点ページのリンクから全年度ページのURLを発見して {season_key: url} で返す。"""
    html = fetch_html(start_url, subdir="kanto/index")
    if not html:
        logger.error("起点ページの取得に失敗: %s", start_url)
        return {}

    soup = BeautifulSoup(html, "html.parser")
    season_urls: dict[str, str] = {}

    # 起点ページ自身も登録
    season_urls[season_from_url(start_url)] = start_url

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # 他年度へのリンクは ../ で始まる相対パス
        if not href.startswith("../"):
            continue
        abs_url = urljoin(start_url, href)
        key = season_from_url(abs_url)
        if key != "UNKNOWN" and key not in season_urls:
            season_urls[key] = abs_url
            logger.info("発見: %s -> %s", key, abs_url)

    return season_urls


def fetch_season(season_key: str, season_url: str, dry_run: bool = False) -> list[dict]:
    """1年度ページを取得し、大会ファイルを列挙・ダウンロードしてイベントリストを返す。"""
    html = fetch_html(season_url, subdir=f"kanto/{season_key}")
    if not html:
        logger.warning("年度ページ取得失敗: %s", season_url)
        return []

    soup = BeautifulSoup(html, "html.parser")
    events = []

    # テーブル行から大会情報を抽出
    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        link_cell = None
        date_str = None
        venue_str = None

        for i, cell in enumerate(cells):
            if cell.find("a"):
                link_cell = cell
                # テーブルの典型構造: 日付 | 大会名(リンク) | 会場
                if i > 0:
                    date_str = cells[i - 1].get_text(strip=True)
                if i + 1 < len(cells):
                    venue_str = cells[i + 1].get_text(strip=True)
                break

        if not link_cell:
            continue

        a = link_cell.find("a")
        href = a["href"]
        name = a.get_text(strip=True)

        # 他年度へのナビリンクはスキップ
        if href.startswith("../") or href.startswith("http"):
            continue

        file_url = urljoin(season_url, href)
        suffix = Path(href.split("?")[0]).suffix.lower()

        if suffix == ".pdf":
            source_type = "kanto_pdf"
        elif suffix in (".htm", ".html"):
            source_type = "kanto_html"
        else:
            continue  # PDF/HTML 以外は対象外

        event_type, division = infer_event_type(name)
        season_half = infer_season_half(name)

        event = {
            "level": "regional",
            "type": event_type,
            "name": name,
            "division": division,
            "season_half": season_half,
            "date": date_str,
            "venue": venue_str or None,
            "source_url": file_url,
            "source_type": source_type,
            "rikkyo_present": None,  # パーサが後で更新
            "confidence": "auto",
        }
        events.append(event)
        logger.info("  大会: %s [%s]", name, source_type)

        if not dry_run:
            fetch(file_url, subdir=f"kanto/{season_key}")

    return events


def main(dry_run: bool = False) -> None:
    season_urls = discover_season_urls(START_URL)
    logger.info("発見した年度数: %d", len(season_urls))

    index = {}
    for key in sorted(season_urls.keys(), reverse=True):
        url = season_urls[key]
        logger.info("=== %s ===", key)
        events = fetch_season(key, url, dry_run=dry_run)
        index[key] = {
            "season": key,
            "season_label": season_label(key),
            "season_url": url,
            "events": events,
        }

    out_path = DATA_DIR / "auto" / "kanto_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("インデックス出力: %s", out_path)
    logger.info("総年度数: %d, 総大会数: %d",
                len(index),
                sum(len(v["events"]) for v in index.values()))


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
