"""config/strategy.md の方針に沿って投稿案を Claude で作り、queue/posts.json に追加する。

環境変数:
    ANTHROPIC_API_KEY  Claude API のキー（必須）
    POSTS_PER_DAY      1 日の投稿数（既定 3）。キューに 2 日分たまるまで補充する
"""

from __future__ import annotations

import os
import sys
import uuid

import anthropic
from pydantic import BaseModel, Field

from common import (
    MAX_WEIGHTED_LENGTH,
    STRATEGY_PATH,
    load_queue,
    now_jst,
    save_queue,
    weighted_length,
)

MODEL = "claude-opus-5"
UNSET_MARKER = "<!-- 未設定 -->"
RECENT_POSTS_FOR_CONTEXT = 40


class Draft(BaseModel):
    text: str = Field(description="投稿本文。そのまま X に投稿される")
    category: str = Field(description="投稿の型（例: ノウハウ, 体験談, 問いかけ）")


class Drafts(BaseModel):
    posts: list[Draft]


SYSTEM_PROMPT = f"""あなたは X（旧Twitter）アカウントの運用担当です。
与えられた運用方針に沿って、そのまま投稿できる日本語の投稿文を作ります。

守ること:
- 1 投稿は全角 140 文字（半角換算 {MAX_WEIGHTED_LENGTH}）以内。改行で読みやすくする
- 冒頭 1 行で読む理由が伝わるようにする
- 事実として書くことは正確に。数字や固有名詞を作り話にしない
- 煽り、誇大表現、「いいねで〇〇」のようなエンゲージメント稼ぎ、ハッシュタグの乱用はしない
- リンクは入れない（リンク付き投稿は表示が伸びにくく、API 料金も高い）
- 過去の投稿と内容や言い回しが重ならないようにする"""


def build_prompt(strategy: str, recent: list[str], count: int) -> str:
    recent_block = "\n".join(f"- {t}" for t in recent) or "（まだありません）"
    return f"""# 運用方針
{strategy}

# 最近の投稿（重複を避けること）
{recent_block}

# 依頼
運用方針に沿った投稿案を {count} 本作ってください。型が偏らないようにしてください。"""


def main() -> int:
    strategy = STRATEGY_PATH.read_text(encoding="utf-8")
    if UNSET_MARKER in strategy:
        print("config/strategy.md が未設定のため、投稿案の生成をスキップします。")
        return 0

    posts_per_day = int(os.environ.get("POSTS_PER_DAY", "3"))
    queue = load_queue()
    queued = [p for p in queue if p["status"] == "queued"]
    needed = posts_per_day * 2 - len(queued)
    if needed <= 0:
        print(f"キューに {len(queued)} 本あるため、生成は不要です。")
        return 0

    recent = [p["text"] for p in queue[-RECENT_POSTS_FOR_CONTEXT:]]
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(strategy, recent, needed)}],
            output_format=Drafts,
        )
    except anthropic.AuthenticationError:
        print("ANTHROPIC_API_KEY が無効です。", file=sys.stderr)
        return 1
    except anthropic.RateLimitError:
        print("Claude API のレート制限に達しました。次回の実行で再試行します。", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as e:
        print(f"Claude API エラー ({e.status_code}): {e.message}", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("Claude API に接続できませんでした。", file=sys.stderr)
        return 1

    if response.stop_reason == "refusal":
        print("Claude が生成を断りました。運用方針の内容を見直してください。", file=sys.stderr)
        return 1
    if response.parsed_output is None:
        print(f"投稿案を読み取れませんでした（stop_reason={response.stop_reason}）。", file=sys.stderr)
        return 1

    added = 0
    for draft in response.parsed_output.posts:
        text = draft.text.strip()
        if not text or weighted_length(text) > MAX_WEIGHTED_LENGTH:
            print(f"長さが条件外のため除外: {text[:30]}…")
            continue
        queue.append(
            {
                "id": uuid.uuid4().hex[:12],
                "text": text,
                "category": draft.category,
                "status": "queued",
                "created_at": now_jst(),
            }
        )
        added += 1

    save_queue(queue)
    print(f"{added} 本の投稿案を追加しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
