"""投稿キューの読み書きなど、生成・投稿スクリプトで共通の処理。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "queue" / "posts.json"
STRATEGY_PATH = ROOT / "config" / "strategy.md"

JST = timezone(timedelta(hours=9))

# X の文字数上限（重み付き）。日本語などの全角文字は 2、半角英数字は 1 として数える。
# 500 = 全角 250 文字。280 を超える投稿には X Premium が必要。
# タイムラインでは冒頭だけが表示され「さらに表示」で続きが開くので、長すぎない範囲に抑える。
MAX_WEIGHTED_LENGTH = 500


# 残っていたら AI っぽい文章とみなして除外する言い回し
BANNED_PHRASES = (
    "しましょう",
    "得策",
    "重要です",
    "と言えるでしょう",
    "が挙げられます",
    "に最適",
    "必見",
    "注目です",
    "ご存知",
    "知っていますか",
    "いかがでしたか",
    "解説します",
    "まとめると",
    "することで",
    "な方におすすめ",
    "取りこぼし",
    "選び分けられます",
    "用途で分かれます",
)


def now_jst() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def load_queue() -> list[dict]:
    if not QUEUE_PATH.exists():
        return []
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def save_queue(queue: list[dict]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _is_single_weight(ch: str) -> bool:
    # twitter-text の設定（v3）で重み 1 とされる範囲
    cp = ord(ch)
    return (
        0x0000 <= cp <= 0x10FF
        or 0x2000 <= cp <= 0x200D
        or 0x2010 <= cp <= 0x201F
        or 0x2032 <= cp <= 0x2037
    )


def weighted_length(text: str) -> int:
    """X の文字数カウントの近似値（URL の短縮は考慮しない）。"""
    return sum(1 if _is_single_weight(ch) else 2 for ch in text)
