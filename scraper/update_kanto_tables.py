"""
data/confirmed/*.json の団体戦イベントに kanto_table フィールドを追加する。
関東連盟 PDF/HTML キャッシュからフルテーブルを解析して埋め込む。

使い方:
    python update_kanto_tables.py          # 全 confirmed ファイルを処理
    python update_kanto_tables.py R07 H24  # 指定年度のみ処理
    python update_kanto_tables.py --force  # 既存の kanto_table も上書き
"""

import json
import sys
from pathlib import Path

from common import _cache_path, logger, validate_json
from parse_team import (
    parse_full_table_html,
    parse_full_table_pdf,
    parse_full_table_xlsx,
    parse_schedule_from_html,
    parse_schedule_from_xlsx,
)

DATA_DIR = Path(__file__).parent.parent / "data"
CONFIRMED_DIR = DATA_DIR / "confirmed"


def get_table(ev: dict, season_key: str) -> dict | None:
    """confirmed イベントに対応するキャッシュファイルから kanto_table を取得する。"""
    source_type = ev.get("source_type", "")
    url = ev.get("source_url", "")
    division = ev.get("division")

    if source_type == "kanto_pdf":
        path = _cache_path(url, f"kanto/{season_key}")
        if not path.exists():
            logger.warning("キャッシュなし(PDF): %s", url[-50:])
            return None
        result = parse_full_table_pdf(path, target_division=division)
    elif source_type == "kanto_html":
        path = _cache_path(url, f"kanto/{season_key}")
        if not path.exists():
            logger.warning("キャッシュなし(HTML): %s", url[-50:])
            return None
        result = parse_full_table_html(path, target_division=division)
    elif source_type == "kanto_xlsx":
        path = _cache_path(url, f"kanto/{season_key}")
        if not path.exists():
            logger.warning("キャッシュなし(XLSX): %s", url[-50:])
            return None
        result = parse_full_table_xlsx(path, target_division=division)
    else:
        return None

    if result is None:
        logger.warning("テーブル抽出失敗: %s %s", season_key, ev.get("name", ""))
    return result


def get_schedule(ev: dict, season_key: str) -> list | None:
    """confirmed イベントに対応するキャッシュファイルから日程情報を取得する。"""
    source_type = ev.get("source_type", "")
    url = ev.get("source_url", "")

    if source_type == "kanto_html":
        path = _cache_path(url, f"kanto/{season_key}")
        if not path.exists():
            return None
        sched = parse_schedule_from_html(path)
    elif source_type == "kanto_xlsx":
        path = _cache_path(url, f"kanto/{season_key}")
        if not path.exists():
            return None
        sched = parse_schedule_from_xlsx(path)
    else:
        return None

    return sched if sched else None


def process_file(path: Path, force: bool = False) -> bool:
    """1 confirmed ファイルを処理して kanto_table を追加する。変更があれば True を返す。"""
    season_key = path.stem
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    for ev in data.get("events", []):
        if ev.get("type") != "team":
            continue
        if not ev.get("source_type", "").startswith("kanto"):
            continue
        if ev.get("kanto_table") is not None and not force:
            continue

        table = get_table(ev, season_key)
        if table:
            ev["kanto_table"] = table
            logger.info("  kanto_table追加: %s %s (%d チーム)",
                        season_key, ev.get("name", ""), len(table.get("teams", [])))
            changed = True

        # schedule は HTML/XLSX 団体戦のみ抽出
        if ev.get("schedule") is None or force:
            sched = get_schedule(ev, season_key)
            if sched:
                ev["schedule"] = sched
                logger.info("  schedule追加: %s %s (%d 日)", season_key, ev.get("name", ""), len(sched))
                changed = True

    if changed:
        errors = validate_json(data)
        if errors:
            logger.error("スキーマエラー(%s): %s", season_key, errors[:3])
            return False
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("書き込み: %s", path.name)

    return changed


def main(seasons: list[str] | None = None, force: bool = False) -> None:
    files = sorted(CONFIRMED_DIR.glob("*.json"))
    if seasons:
        files = [f for f in files if f.stem in seasons]

    for path in files:
        logger.info("=== %s ===", path.stem)
        process_file(path, force=force)


if __name__ == "__main__":
    args = sys.argv[1:]
    force = "--force" in args
    seasons_arg = [a for a in args if not a.startswith("--")] or None
    main(seasons=seasons_arg, force=force)
