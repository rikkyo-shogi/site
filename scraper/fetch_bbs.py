"""掲示板クローラー: 全ページを巡回し、大会結果を含む投稿を候補抽出してキャッシュする。"""

import json
import math
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from common import fetch_html, logger

BBS_BASES = {
    "active": "https://d35s62fmhuthp2.cloudfront.net/rikkyo_shogi/rikkyoshogiclub/bbs",
    "ob": "https://d35s62fmhuthp2.cloudfront.net/rikkyo_shogi_ob/poemfactory/bbs",
}

RESULT_KEYWORDS = re.compile(
    r"団体戦|個人戦|新人戦|女流戦|古新戦|交流戦|練習試合"
    r"|結果|勝ち|負け|勝利|敗北|優勝|順位|昇級|降級"
    r"|[0-9０-９][-ー－][0-9０-９]"  # スコア表記
    r"|回戦|不戦勝|不戦敗|勝[0-9]|[0-9]敗"
)

DATA_DIR = Path(__file__).parent.parent / "data" / "auto"


def _extract_post_body(html: str) -> tuple[str, str, str, str | None]:
    """投稿 HTML から件名・投稿者・本文・投稿日を抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    subject = ""
    author = ""
    post_date = None
    body_lines = []
    in_body = False

    skip_words = {"Reload", "TOP", "記事一覧表示", "前のページ", "次のページ",
                  "通報", "返信・引用", "編集済", "新着順"}

    for i, line in enumerate(lines):
        if not subject and "立教大学将棋部" in line and i > 0:
            subject = lines[i - 1] if lines[i - 1] not in skip_words else ""
        if "投稿者" in line and i + 1 < len(lines):
            author = lines[i + 1]
        if "投稿日" in line:
            # 投稿日行から日付を抽出: 「2017年 9月10日(日)08時...」
            m = re.search(r"(\d{4})年\s*(\d{1,2})月", line)
            if not m and i + 1 < len(lines):
                m = re.search(r"(\d{4})年\s*(\d{1,2})月", lines[i + 1])
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                post_date = f"{year}-{month:02d}"
            in_body = True
            continue
        if in_body:
            if any(sw in line for sw in skip_words):
                if body_lines:
                    break
                continue
            if line:
                body_lines.append(line)

    return subject, author, "\n".join(body_lines), post_date


def _get_total_pages(base_url: str, bbs_type: str) -> int:
    """トップページから総件数を取得してページ数を算出する。"""
    html = fetch_html(f"{base_url}.html", subdir=f"bbs/{bbs_type}")
    if not html:
        return 1
    m = re.search(r"全\s*(\d+)\s*件", html)
    if m:
        total = int(m.group(1))
        pages = math.ceil(total / 10)
        logger.info("掲示板(%s): 総件数=%d, ページ数=%d", bbs_type, total, pages)
        return pages
    return 1


def _get_post_ids_from_page(base_url: str, page: int, bbs_type: str) -> list[int]:
    """一覧ページから投稿 ID を収集する。"""
    if page == 1:
        url = f"{base_url}.html"
    else:
        url = f"{base_url}@page={page}&.html"
    html = fetch_html(url, subdir=f"bbs/{bbs_type}")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    for a in soup.find_all("a", href=True):
        m = re.search(r"bbs/(\d+)\.html", a["href"])
        if m:
            ids.append(int(m.group(1)))
    return sorted(set(ids), reverse=True)


def crawl_bbs(bbs_type: str = "active", dry_run: bool = False) -> list[dict]:
    """
    掲示板を全ページ巡回して大会結果候補投稿を返す。
    [{id, subject, author, body, url, is_result_candidate}, ...]
    """
    base_url = BBS_BASES[bbs_type]
    total_pages = _get_total_pages(base_url, bbs_type)

    all_ids: set[int] = set()
    for page in range(1, total_pages + 1):
        ids = _get_post_ids_from_page(base_url, page, bbs_type)
        all_ids.update(ids)
        logger.info("page %d/%d: %d 件", page, total_pages, len(ids))

    logger.info("総投稿ID数: %d", len(all_ids))

    posts = []
    for post_id in sorted(all_ids, reverse=True):
        url = f"{base_url}/{post_id}.html"
        subdir = f"bbs/{bbs_type}/posts"
        if dry_run:
            posts.append({"id": post_id, "url": url, "is_result_candidate": None})
            continue

        html = fetch_html(url, subdir=subdir)
        if not html:
            continue

        subject, author, body, post_date = _extract_post_body(html)
        combined = subject + "\n" + body
        is_candidate = bool(RESULT_KEYWORDS.search(combined))

        post = {
            "id": post_id,
            "url": url,
            "subject": subject,
            "author": author,
            "body": body,
            "post_date": post_date,
            "is_result_candidate": is_candidate,
        }
        posts.append(post)

        if is_candidate:
            logger.info("  候補: [%d] %s", post_id, subject[:50])

    return posts


def save_candidates(posts: list[dict], bbs_type: str) -> Path:
    """候補投稿を data/auto/bbs_<type>.json に保存する。"""
    candidates = [p for p in posts if p.get("is_result_candidate")]
    out_path = DATA_DIR / f"bbs_{bbs_type}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("候補保存: %s (%d件)", out_path, len(candidates))
    return out_path


def main(bbs_type: str = "active", dry_run: bool = False) -> None:
    posts = crawl_bbs(bbs_type=bbs_type, dry_run=dry_run)
    if not dry_run:
        save_candidates(posts, bbs_type)
        logger.info("完了: 全%d投稿中 %d件が大会結果候補",
                    len(posts), sum(1 for p in posts if p.get("is_result_candidate")))


if __name__ == "__main__":
    bbs_type = "active"
    dry_run = "--dry-run" in sys.argv
    if len(sys.argv) >= 2 and sys.argv[1] in ("active", "ob"):
        bbs_type = sys.argv[1]
    main(bbs_type=bbs_type, dry_run=dry_run)
