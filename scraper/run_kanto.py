"""関東連盟の全年度PDFをダウンロードし、立教の成績を data/auto/<season>.json に出力する。"""

import json
import sys
from pathlib import Path

from common import _cache_path, is_rikkyo, logger, save_auto, validate_json
from fetch_kanto import (
    START_URL,
    discover_season_urls,
    fetch_season,
    season_label,
)
from parse_team import parse_team_html, parse_team_pdf
from parse_individual import parse_individual_html, parse_individual_pdf


def build_team_event(ev: dict, season_key: str) -> dict | None:
    """団体戦イベントを処理してスキーマ準拠の dict を返す。"""
    url = ev["source_url"]
    path = _cache_path(url, f"kanto/{season_key}")
    if not path.exists():
        logger.warning("キャッシュなし: %s", url)
        return None

    source_type = ev.get("source_type", "kanto_pdf")
    if source_type == "kanto_html":
        res = parse_team_html(path, ev["name"])
    else:
        res = parse_team_pdf(path, ev["name"])
    if res is None:
        return None  # 立教なし

    return {
        "level": "regional",
        "type": "team",
        "name": ev["name"],
        "division": res["division"] or ev.get("division"),
        "season_half": ev.get("season_half"),
        "date": ev.get("date"),
        "venue": ev.get("venue"),
        "source_url": url,
        "source_type": ev.get("source_type", "kanto_pdf"),
        "rikkyo_present": True,
        "rikkyo_result": res["result"],
        "confidence": "auto",
    }


def build_individual_event(ev: dict, season_key: str) -> dict | None:
    """個人戦イベントを処理してスキーマ準拠の dict を返す。"""
    url = ev["source_url"]
    path = _cache_path(url, f"kanto/{season_key}")
    if not path.exists():
        logger.warning("キャッシュなし: %s", url)
        return None

    source_type = ev.get("source_type", "kanto_pdf")
    if source_type == "kanto_html":
        players = parse_individual_html(path, ev["name"])
    else:
        players = parse_individual_pdf(path, ev["name"])
    if not players:
        return None  # 立教なし

    return {
        "level": "regional",
        "type": "individual",
        "name": ev["name"],
        "division": ev.get("division"),
        "season_half": ev.get("season_half"),
        "date": ev.get("date"),
        "venue": ev.get("venue"),
        "source_url": url,
        "source_type": ev.get("source_type", "kanto_pdf"),
        "rikkyo_present": True,
        "rikkyo_players": players,
        "confidence": "auto",
    }


def process_season(season_key: str, season_url: str, season_events: list[dict], do_download: bool = True) -> dict:
    """1年度分を処理して JSON データを返す。"""
    if do_download:
        fetch_season(season_key, season_url, dry_run=False)

    events = []
    for ev in season_events:
        if ev.get("type") == "team":
            built = build_team_event(ev, season_key)
        else:
            built = build_individual_event(ev, season_key)

        if built:
            events.append(built)
            logger.info("  追加: %s [立教あり]", ev["name"])
        else:
            logger.info("  スキップ: %s [立教なし or 未取得]", ev["name"])

    return {
        "season": season_key,
        "season_label": season_label(season_key),
        "events": events,
    }


def main(seasons: list[str] | None = None) -> None:
    """
    全年度(または指定年度)を処理して data/auto/<season>.json に出力する。
    seasons: None の場合は全年度を処理。
    """
    # 1. 全年度 URL を発見(起点からリンクを辿る)
    index_path = Path("data/auto/kanto_index.json")
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        season_urls = {k: v["season_url"] for k, v in index.items()}
        season_event_map = {k: v["events"] for k, v in index.items()}
    else:
        logger.info("インデックス未生成。fetch_kanto.py を先に実行してください。")
        return

    target = seasons if seasons else sorted(season_urls.keys(), reverse=True)
    logger.info("処理対象: %s", target)

    for key in target:
        if key not in season_urls:
            logger.warning("未知の年度: %s", key)
            continue

        logger.info("=== %s (%s) ===", key, season_label(key))
        data = process_season(key, season_urls[key], season_event_map.get(key, []))

        errors = validate_json(data)
        if errors:
            logger.error("スキーマエラー(%s): %s", key, errors)
        else:
            out_path = save_auto(data, key)
            logger.info("出力: %s (%d件)", out_path, len(data["events"]))


if __name__ == "__main__":
    # コマンドライン引数で年度を指定可能: python run_kanto.py R08 R07
    seasons_arg = sys.argv[1:] or None
    main(seasons=seasons_arg)
