"""
掲示板データと関東連盟データを名寄せして統合し、
data/auto/<season>.json を更新する。

掲示板投稿は年度・シーズン・大会種別で既存イベントに紐付けるか、
単独イベントとして追加する。
"""

import json
import re
import sys
from pathlib import Path

from common import logger, save_auto, validate_json
from fetch_bbs import BBS_BASES, _extract_post_body, crawl_bbs, save_candidates
from parse_bbs import extract_meta, is_unofficial, parse_post

DATA_DIR = Path(__file__).parent.parent / "data"

SEASON_KEYWORDS = {
    "春": "spring",
    "秋": "autumn",
}

EVENT_NAME_KEYWORDS = {
    "団体": "団体戦",
    "個人": "個人戦",
    "新人": "新人戦",
    "女流": "女流戦",
    "古新": "古新戦",
    "交流": "交流戦",
    "練習": "練習試合",
}


def _guess_season_half(text: str) -> str | None:
    for kw, val in SEASON_KEYWORDS.items():
        if kw in text:
            return val
    return None


def _guess_event_type(text: str) -> str:
    if "団体" in text:
        return "team"
    return "individual"


def _guess_season_key(text: str, date: str | None) -> str | None:
    """投稿の日付から年度キーを推定する(簡易)。"""
    if not date:
        return None
    m = re.match(r"(\d{4})", date)
    if not m:
        return None
    year = int(m.group(1))
    # 4月以前なら前年度の扱い
    month = int(re.search(r"\d{4}-(\d{2})", date).group(1)) if re.search(r"\d{4}-(\d{2})", date) else 4
    if month < 4:
        year -= 1

    # 西暦→和暦変換
    if year >= 2019:
        num = year - 2018
        return f"R{num:02d}"
    else:
        num = year - 1988
        return f"H{num:02d}"


def load_auto(season_key: str) -> dict | None:
    path = DATA_DIR / "auto" / f"{season_key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def integrate_bbs_into_season(season_data: dict, bbs_posts: list[dict]) -> dict:
    """
    掲示板候補投稿を年度データに統合する。
    既存イベントに bbs_detail を付加するか、新規イベントとして追加する。
    """
    events = season_data.get("events", [])

    for post_data in bbs_posts:
        parsed = parse_post(post_data)
        if not parsed:
            continue

        bbs_detail = parsed["bbs_detail"]
        meta = extract_meta(post_data["subject"], post_data["body"])
        season_half = _guess_season_half(post_data["subject"] + post_data.get("body", ""))
        event_type = _guess_event_type(post_data["subject"])
        date = meta["date"] or parsed.get("date")
        unofficial = is_unofficial(post_data["subject"], post_data.get("body", ""))

        subj = post_data.get("subject", "")

        def _match_score(ev: dict) -> int:
            """BBS 件名と公式イベント名の一致度スコア。"""
            score = 0
            ev_name = ev.get("name", "")
            for kw in re.findall(r"[春秋]季|個人戦|団体戦|新人戦|女流|関東オール|古新|交流", subj):
                if kw in ev_name:
                    score += 3
            # 日目番号のマッチ(1日目 vs 2日目 等)
            day_m = re.search(r"([1-9１-９一二三])日目", subj)
            if day_m:
                day = day_m.group(1)
                if day in ev_name:
                    score += 2
                elif re.search(r"[1-9１-９一二三]日目", ev_name):
                    score -= 2  # 日目が違う
            if season_half == "spring" and "春" in ev_name:
                score += 1
            elif season_half == "autumn" and "秋" in ev_name:
                score += 1
            elif season_half and ev.get("season_half") and ev.get("season_half") != season_half:
                score -= 5
            return score

        # 既存イベントと名寄せ(件名スコアが最大かつ正のものを選択)
        matched = False
        candidates = []
        for ev in events:
            if ev.get("type") != event_type:
                continue
            if ev.get("bbs_detail") is not None:
                continue
            if meta["division"] and ev.get("division") and ev.get("division") != meta["division"]:
                continue
            score = _match_score(ev)
            candidates.append((score, ev))

        # 非公式戦(古新・交流戦等)は既存の公式イベントと紐付けない
        if unofficial:
            matched = False
        elif candidates:
            best_score, best_ev = max(candidates, key=lambda x: x[0])
            if best_score > 0:
                matched_ev = best_ev
                matched_ev["bbs_detail"] = bbs_detail
                logger.info("  紐付け: post[%s] -> %s (score=%d)", post_data["id"], matched_ev["name"], best_score)
                # 個人戦: BBS players で rikkyo_players の best_result を更新
                if event_type == "individual" and bbs_detail.get("players"):
                    existing = {p["name"]: p for p in matched_ev.get("rikkyo_players", [])}
                    for bp in bbs_detail["players"]:
                        bname = bp.get("name", "").strip()
                        bres = bp.get("result")
                        if not bname or not bres:
                            continue
                        for ename, ep in existing.items():
                            if bname in ename or ename.split()[0] in bname:
                                # confidence=auto の場合は常に BBS で上書き
                                current = ep.get("best_result")
                                if current != bres:
                                    ep["best_result"] = bres
                                    logger.info("    rikkyo_players 更新: %s %s -> %s", ename, current, bres)
                                break
                        else:
                            matched_ev.setdefault("rikkyo_players", []).append({
                                "name": bname, "grade": None, "best_result": bres, "rank": None
                            })
                matched = True

        if not matched:
            # 同じ BBS URL が既に登録済みならスキップ(重複防止)
            bbs_url = bbs_detail.get("source_url", "")
            if any(e.get("bbs_detail", {}) and e["bbs_detail"].get("source_url") == bbs_url
                   for e in events):
                continue
            # 単独イベントとして追加
            event_name = post_data["subject"].split("|")[0].strip()
            new_event = {
                "level": "regional",
                "type": event_type,
                "name": event_name,
                "division": meta["division"],
                "season_half": season_half,
                "date": date,
                "venue": None,
                "source_url": post_data["url"],
                "source_type": "bbs",
                "rikkyo_present": True,
                "rikkyo_result": None,
                "rikkyo_players": [],
                "bbs_detail": bbs_detail,
                "confidence": "auto",
            }
            if event_type == "individual" and bbs_detail.get("players"):
                new_event["rikkyo_players"] = [
                    {"name": p["name"], "grade": None, "best_result": p.get("result"), "rank": None}
                    for p in bbs_detail["players"]
                ]
            events.append(new_event)
            logger.info("  新規追加: post[%s] %s", post_data["id"], event_name[:30])

    season_data["events"] = events
    return season_data


def run_bbs_integration(bbs_type: str = "active") -> None:
    """掲示板を巡回して候補を抽出し、各年度データに統合する。"""
    # 候補投稿を取得(キャッシュがあれば再利用)
    candidates_path = DATA_DIR / "auto" / f"bbs_{bbs_type}.json"
    if candidates_path.exists():
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        logger.info("掲示板候補読み込み: %d件", len(candidates))
    else:
        posts = crawl_bbs(bbs_type=bbs_type)
        save_candidates(posts, bbs_type)
        candidates = [p for p in posts if p.get("is_result_candidate")]

    # 年度ごとにグループ化して統合
    by_season: dict[str, list] = {}
    for post in candidates:
        meta = extract_meta(post.get("subject", ""), post.get("body", ""))
        # 投稿日(HTML から抽出)を優先し、なければ本文内の日付を使う
        date = post.get("post_date") or meta["date"]
        key = _guess_season_key(post.get("subject", ""), date)
        if not key:
            logger.warning("年度不明 post[%s]: %s", post.get("id"), post.get("subject", "")[:40])
            continue
        by_season.setdefault(key, []).append(post)

    for season_key, posts_raw in by_season.items():
        # 古い投稿(小さいID=早い日付)から処理する
        posts = sorted(posts_raw, key=lambda p: p.get("id", 0))
        season_data = load_auto(season_key)
        if not season_data:
            logger.warning("年度データなし: %s (post %d件)", season_key, len(posts))
            continue

        logger.info("=== %s: %d件の掲示板投稿を統合 ===", season_key, len(posts))
        season_data = integrate_bbs_into_season(season_data, posts)
        errors = validate_json(season_data)
        if errors:
            logger.error("スキーマエラー(%s): %s", season_key, errors[:3])
        else:
            save_auto(season_data, season_key)


if __name__ == "__main__":
    bbs_type = sys.argv[1] if len(sys.argv) > 1 else "active"
    run_bbs_integration(bbs_type=bbs_type)
