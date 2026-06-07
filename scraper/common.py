"""共通ユーティリティ: HTTP取得・キャッシュ・Shift-JISデコード・立教判定・JSON検証"""

import hashlib
import json
import logging
import re
import time
from pathlib import Path

import chardet
import jsonschema
import requests

CACHE_DIR = Path(__file__).parent.parent / "cache"
SCHEMA_PATH = Path(__file__).parent.parent / "data" / "schema.json"
RIKKYO_PATTERN = re.compile(r"立教大学|立教大|立教|[（(]立教\d*[）)]")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "RikkyoShogiBot/1.0 (research use)"})


def _cache_path(url: str, subdir: str = "") -> Path:
    digest = hashlib.md5(url.encode()).hexdigest()
    base = CACHE_DIR / subdir if subdir else CACHE_DIR
    base.mkdir(parents=True, exist_ok=True)
    suffix = Path(url.split("?")[0]).suffix or ".html"
    return base / f"{digest}{suffix}"


def fetch(url: str, encoding: str = "shift_jis", subdir: str = "", retries: int = 3, sleep: float = 1.0) -> bytes | None:
    """URLを取得してキャッシュに保存し、バイト列を返す。失敗時はNone。"""
    path = _cache_path(url, subdir)
    if path.exists():
        logger.info("cache hit: %s", url)
        return path.read_bytes()

    for attempt in range(1, retries + 1):
        try:
            resp = SESSION.get(url, timeout=20)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            logger.info("fetched: %s -> %s", url, path.name)
            time.sleep(sleep)
            return resp.content
        except requests.HTTPError as e:
            logger.warning("HTTP %s: %s", e.response.status_code, url)
            return None
        except requests.RequestException as e:
            logger.warning("attempt %d/%d failed: %s (%s)", attempt, retries, url, e)
            if attempt < retries:
                time.sleep(sleep * attempt)

    logger.error("all retries failed: %s", url)
    return None


def decode_html(content: bytes, hint: str = "shift_jis") -> str:
    """バイト列をShift-JIS優先でデコードし、UTF-8文字列を返す。"""
    for enc in (hint, "shift_jis", "cp932", "utf-8"):
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass
    detected = chardet.detect(content).get("encoding") or "utf-8"
    return content.decode(detected, errors="replace")


def fetch_html(url: str, encoding: str = "shift_jis", subdir: str = "") -> str | None:
    """URLを取得してデコード済み文字列を返す。失敗時はNone。"""
    raw = fetch(url, subdir=subdir)
    if raw is None:
        return None
    return decode_html(raw, hint=encoding)


def is_rikkyo(text: str) -> bool:
    """テキストに立教大学関連の表記が含まれるか判定する。"""
    return bool(RIKKYO_PATTERN.search(text))


def normalize_rikkyo(text: str) -> str:
    """立教の表記揺れを「立教」に正規化する。"""
    text = re.sub(r"立教大学|立教大", "立教", text)
    # 全角カッコ・学年表記を半角に正規化
    text = text.replace("（", "(").replace("）", ")")
    return text


def validate_json(data: dict, schema_path: Path = SCHEMA_PATH) -> list[str]:
    """JSON SchemaでデータをバリデーションしてエラーリストURLを返す。空=OK。"""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = [e.message for e in validator.iter_errors(data)]
    return errors


def save_auto(data: dict, season: str) -> Path:
    """data/auto/<season>.json に書き出す。"""
    out_dir = Path(__file__).parent.parent / "data" / "auto"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{season}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("saved: %s", out_path)
    return out_path
