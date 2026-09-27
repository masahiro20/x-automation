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
# 280 = 全角 140 文字。Premium なら長文も投稿できるが、タイムラインで読まれやすい長さに抑える。
MAX_WEIGHTED_LENGTH = 280


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
