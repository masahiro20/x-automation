"""config/strategy.md の方針に沿って投稿案を作り、queue/posts.json に追加する。

1. 調査: Claude が Web 検索で新製品・セール・話題を調べ、出典付きのメモにまとめる
2. 執筆: メモの事実だけを使って必要数の 2 倍の候補を書き、自己採点する
3. 選抜: 点数の高い順に必要数だけ残し、図解が指定されたものは画像を描く

環境変数:
    ANTHROPIC_API_KEY  Claude API のキー（必須）
    POSTS_PER_DAY      1 日の投稿数（既定 3）。キューに 2 日分たまるまで補充する
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from common import (
    JST,
    MAX_WEIGHTED_LENGTH,
    QUEUE_PATH,
    STRATEGY_PATH,
    load_queue,
    now_jst,
    save_queue,
    weighted_length,
)
from render import render

MODEL = "claude-opus-5"
BETAS = ["server-side-fallback-2026-07-01"]
UNSET_MARKER = "<!-- 未設定 -->"
RECENT_POSTS_FOR_CONTEXT = 40
MIN_SCORE = 7
MAX_CONTINUATIONS = 5
IMAGES_DIR = QUEUE_PATH.parent / "images"


class ImageSpec(BaseModel):
    kind: Literal["none", "table", "checklist"] = Field(
        description="none=画像なし, table=比較表, checklist=チェックリスト"
    )
    title: str = Field(description="画像の見出し（20 文字前後）。none のときは空文字")
    headers: list[str] = Field(description="table の列見出し（2〜4 列）。それ以外は空")
    rows: list[list[str]] = Field(description="table の行（3〜6 行、1 セル 15 文字以内）。それ以外は空")
    items: list[str] = Field(description="checklist の項目（3〜6 個、1 項目 25 文字以内）。それ以外は空")
    note: str = Field(description="画像下部の注記（価格の時点、出典名など）。不要なら空文字")


class Draft(BaseModel):
    text: str = Field(description="投稿本文。そのまま X に投稿される")
    category: str = Field(description="投稿の型（比較, 〇〇選, 速報, 買い時, 失敗あるある, 使いこなし, 問いかけ）")
    score: int = Field(description="伸びそうか・役に立つか・正確かを厳しめに 1〜10 で自己採点")
    sources: list[str] = Field(description="本文の事実の根拠にした URL。調査メモにあるものだけ")
    image: ImageSpec


class Drafts(BaseModel):
    posts: list[Draft]


RESEARCH_SYSTEM = """あなたはガジェット・便利グッズ専門の X アカウントのリサーチ担当です。
Web 検索で、今日投稿するネタになる最新情報を集め、執筆担当に渡すメモを作ります。

集めるもの:
- 最近発表・発売された製品（スマホ周辺機器、PC 周辺機器、デスク環境、生活家電、便利グッズ）
- 開催中・直近の大型セールと、その対象になりやすい定番製品
- 比較されがちな定番製品同士の違い（スペック、価格帯、向いている人）
- 今話題になっているガジェットの話題・トラブル・よくある失敗

ルール:
- メーカー公式サイト、大手ニュースサイト、大手販売サイトなど信頼できる情報源を優先する
- 製品名・型番・スペック・価格・日付は、見つけた情報源の記載どおりに書く。推測で補わない
- 価格は変動するので「〇月〇日時点」と確認日を添える
- 各項目に出典 URL を付ける
- 過去の投稿と同じ製品・同じ話題は避ける"""

WRITER_SYSTEM = f"""あなたはガジェット・便利グッズ専門の X アカウントの執筆担当です。
運用方針と調査メモをもとに、そのまま投稿できる日本語の投稿を書きます。

守ること:
- 製品名・スペック・価格などの事実は、調査メモに出典付きで書かれているものだけを使う
- 価格を書くときは「〇/〇時点」を添える
- 実際に使った体験談のような一人称の感想は書かない（「使ってみた」「買ってよかった」など）
- 1 投稿は半角換算 {MAX_WEIGHTED_LENGTH} 以内。冒頭 1〜2 行だけで読む価値が伝わるようにする
- 煽り、誇大表現、エンゲージメント稼ぎ（「いいねで〇〇」など）、ハッシュタグの乱用はしない
- リンクは本文に入れない
- 過去の投稿と内容や言い回しを重ねない

図解（image）:
- 比較や〇〇選は table、失敗あるある・チェックポイントは checklist にすると効果的
- 本文だけで伝わる投稿や問いかけは none
- 図解の中身も調査メモの事実だけで作る

採点（score）:
- 10 = 思わず保存・共有したくなる具体的で新しい情報。5 = どこかで見た一般論。
- 事実の裏付けが弱いもの、ありきたりなものは厳しく低く付ける"""


def _request(client: anthropic.Anthropic, **kwargs):
    # 出力上限が大きいリクエストは、SDK の仕様でストリーミングが必須
    with client.beta.messages.stream(
        model=MODEL,
        betas=BETAS,
        fallbacks="default",
        thinking={"type": "adaptive"},
        max_tokens=32000,
        **kwargs,
    ) as stream:
        return stream.get_final_message()


def research(client: anthropic.Anthropic, strategy: str, recent: list[str]) -> str:
    today = datetime.now(JST).strftime("%Y年%m月%d日")
    recent_block = "\n".join(f"- {t[:60]}" for t in recent) or "（まだありません）"
    user_msg = f"""今日は {today} です。

# 運用方針
{strategy}

# 最近の投稿（同じネタは避ける）
{recent_block}

# 依頼
今日の投稿ネタになる情報を調べ、ネタ候補を 8〜10 個、出典 URL 付きのメモにまとめてください。"""
    messages = [{"role": "user", "content": user_msg}]
    tools = [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": 8,
            "user_location": {"type": "approximate", "country": "JP", "timezone": "Asia/Tokyo"},
        }
    ]
    for _ in range(MAX_CONTINUATIONS):
        response = _request(client, system=RESEARCH_SYSTEM, tools=tools, messages=messages)
        if response.stop_reason != "pause_turn":
            break
        # サーバー側の検索ループが上限に達しただけなので、そのまま続きを依頼する
        messages = [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": response.content},
        ]
    if response.stop_reason == "refusal":
        raise RuntimeError("調査が断られました")
    memo = "\n".join(b.text for b in response.content if b.type == "text").strip()
    if not memo:
        raise RuntimeError(f"調査メモが空です（stop_reason={response.stop_reason}）")
    return memo


def write_drafts(
    client: anthropic.Anthropic, strategy: str, memo: str, recent: list[str], count: int
) -> list[Draft]:
    recent_block = "\n".join(f"- {t}" for t in recent) or "（まだありません）"
    user_msg = f"""# 運用方針
{strategy}

# 調査メモ
{memo}

# 最近の投稿（重複を避けること）
{recent_block}

# 依頼
投稿の候補を {count} 本書いてください。型が偏らないようにし、各候補を厳しめに採点してください。"""
    response = _request(
        client,
        system=WRITER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        output_format=Drafts,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("執筆が断られました")
    if response.parsed_output is None:
        raise RuntimeError(f"投稿案を読み取れませんでした（stop_reason={response.stop_reason}）")
    return response.parsed_output.posts


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
        memo = research(client, strategy, recent)
        print("---- 調査メモ ----\n" + memo + "\n------------------")
        drafts = write_drafts(client, strategy, memo, recent, needed * 2)
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
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    candidates = []
    for d in drafts:
        text = d.text.strip()
        if not text or weighted_length(text) > MAX_WEIGHTED_LENGTH:
            print(f"長さが条件外のため除外: {text[:30]}…")
        elif d.score < MIN_SCORE:
            print(f"点数 {d.score} のため除外: {text[:30]}…")
        else:
            candidates.append(d)
    candidates.sort(key=lambda d: d.score, reverse=True)

    added = 0
    for d in candidates[:needed]:
        post_id = uuid.uuid4().hex[:12]
        entry = {
            "id": post_id,
            "text": d.text.strip(),
            "category": d.category,
            "score": d.score,
            "sources": d.sources,
            "status": "queued",
            "created_at": now_jst(),
        }
        if d.image.kind != "none":
            path = render(d.image.model_dump(), IMAGES_DIR / f"{post_id}.png")
            entry["image"] = str(path.relative_to(QUEUE_PATH.parent.parent))
        queue.append(entry)
        added += 1

    save_queue(queue)
    print(f"{added} 本の投稿案を追加しました（候補 {len(drafts)} 本中）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
