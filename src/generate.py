"""config/strategy.md の方針に沿って投稿案を作り、queue/posts.json に追加する。

1. 調査: Claude が Web 検索で新製品・セール・話題を調べ、出典付きのメモにまとめる
2. 執筆: メモの事実だけを使って必要数の 2 倍の候補を書き、自己採点する
3. 編集: 「中の人」目線で、人が書いたように読める文章へ書き直して採点し直す
4. 校閲: 調査メモと照合し、根拠のない事実や誤解を招く表現がある下書きを除く
5. 選抜: AI っぽい言い回しが残るものを除き、点数の高い順に必要数だけ残して図解を描く

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
MAX_PER_TOPIC = 2
MAX_CONTINUATIONS = 5
IMAGES_DIR = QUEUE_PATH.parent / "images"


class ImageSpec(BaseModel):
    kind: Literal["none", "table", "checklist", "number"] = Field(
        description="none=画像なし, table=比較表, checklist=チェックリスト, number=大きな数字 1 つを見せるカード"
    )
    title: str = Field(description="画像の見出し。話し言葉で 18 文字以内（例: 結局どっち買えばいい？）。none のときは空文字")
    highlight: str = Field(description="見出しの中で黄色マーカーを引く語句（見出しに含まれる文字列）。なければ空文字")
    headers: list[str] = Field(description="table の列見出し（2〜4 列、左端は項目名の列）。それ以外は空")
    rows: list[list[str]] = Field(
        description="table の行（3〜5 行、1 セル 12 文字以内）。評価は ◎ ○ △ × の記号 1 文字だけのセルにすると見やすい。それ以外は空"
    )
    recommend_col: int = Field(description="table でおすすめの列の番号（0 始まり、左端の項目名列は 0）。なければ -1")
    items: list[str] = Field(description="checklist の項目（3〜5 個、1 項目 22 文字以内、話し言葉）。それ以外は空")
    big_text: str = Field(description="number の大きな数字（例: 90h → 135h、400万点、-4,000円）。それ以外は空文字")
    caption: str = Field(description="number の数字の下に添える一言（20 文字以内）。それ以外は空文字")
    conclusion: str = Field(description="画像の一番下に出す一言の結論（22 文字以内、話し言葉）。なければ空文字")
    note: str = Field(description="価格の時点など最小限の注記（例: 価格は9/29時点）。なければ空文字")


class Draft(BaseModel):
    text: str = Field(description="投稿本文。そのまま X に投稿される")
    category: str = Field(description="投稿の型（比較, 〇〇選, 速報, 買い時, 失敗あるある, 使いこなし, 問いかけ）")
    topic: str = Field(description="主に扱うメーカー名かイベント名を 1 語で（例: ロジクール, Anker, Apple, プライム感謝祭）。特定の対象がなければ 一般")
    score: int = Field(description="伸びそうか・役に立つか・正確かを厳しめに 1〜10 で自己採点")
    sources: list[str] = Field(description="本文の事実の根拠にした URL。調査メモにあるものだけ")
    image: ImageSpec


class Drafts(BaseModel):
    posts: list[Draft]


class FactCheck(BaseModel):
    index: int = Field(description="下書きの番号（0 始まり）")
    supported: bool = Field(description="本文と図解の事実がすべて調査メモで裏付けられ、誤解を招く表現もなければ true")
    problem: str = Field(description="false の理由（根拠のない事実や誤解を招く点）。true なら空文字")


class FactChecks(BaseModel):
    results: list[FactCheck]


RESEARCH_SYSTEM = """あなたはガジェット・便利グッズ専門の X アカウントのリサーチ担当です。
Web 検索で、今日投稿するネタになる最新情報を集め、執筆担当に渡すメモを作ります。

集めるもの:
- 最近発表・発売された製品（スマホ周辺機器、PC 周辺機器、デスク環境、生活家電、便利グッズ）
- 開催中・直近の大型セールと、その対象になりやすい定番製品
- 比較されがちな定番製品同士の違い（スペック、価格帯、向いている人）
- 今話題になっているガジェットの話題・トラブル・よくある失敗

ネタは散らすこと:
- カテゴリ（スマホ周辺機器 / PC・デスク環境 / 生活家電 / 便利グッズ / セール）から最低 4 つ
- 同じメーカーのネタは 2 個まで。同じ記事から拾うネタも 2 個まで

ルール:
- メーカー公式サイト、大手ニュースサイト、大手販売サイトなど信頼できる情報源を優先する
- 製品名・型番・スペック・価格・日付は、見つけた情報源の記載どおりに書く。推測で補わない
- 情報源に書いていないこと（無料かどうか、対象機種、色名など）は「不明」と書く
- 価格は変動するので「〇月〇日時点」と確認日を添える
- 各項目に出典 URL を付ける
- 過去の投稿と同じ製品・同じ話題は避ける"""

WRITER_SYSTEM = f"""あなたはガジェット・便利グッズ専門の X アカウントの執筆担当です。
運用方針と調査メモをもとに、そのまま投稿できる日本語の投稿を書きます。
運用方針の「語り口」を必ず守ってください。ニュース記事や AI の回答文のような文章は不合格です。

守ること:
- 製品名・スペック・価格などの事実は、調査メモに出典付きで書かれているものだけを使う
- 実際に使った体験談のような一人称の使用感は書かない（「使ってみた」「買ってよかった」など）
- 1 投稿は半角換算 {MAX_WEIGHTED_LENGTH} 以内。冒頭 1 行だけで読む理由が伝わるようにする
- 煽り、誇大表現、エンゲージメント稼ぎ（「いいねで〇〇」など）、ハッシュタグの乱用はしない
- リンクは本文に入れない
- 過去の投稿と内容や言い回しを重ねない
- 同じメーカー・同じイベント（セールなど）を扱う候補は最大 2 本まで。ネタを散らす
- 調査メモに書かれていないこと（無料・無償、対象機種、色名など）を推測で足さない
- 「価格は各自確認を」のような、読者に役立たない一文は書かない

図解（image）:
- 比較・〇〇選は table、失敗あるある・チェックポイントは checklist、
  「90時間→135時間」「400万点」のように数字 1 つが主役のネタは number
- 本文だけで伝わる投稿、短い投稿、問いかけは none（全体の 3〜4 割は none でよい）
- 見出し・結論・項目も話し言葉で。カタログのような文言にしない。絵文字は使わない
- number は「90h → 135h」「倍の400万点」のように変化や驚きがある数字にだけ使う。ただの価格 1 つには使わない
- conclusion は事実の繰り返しではなく「だからどうする」の一言（例: 音量いじらないなら下位でOK）
- table は同じ種類の製品同士だけを並べる（マウスとキーボードを同じ表で比べない）
- 図解の中身も調査メモの事実だけで作る

採点（score）:
- 10 = 思わず保存・共有したくなる、具体的で新しく、人が書いたように読める投稿
- 5 = どこかで見た一般論、またはニュース記事・AI っぽい文章
- 事実の裏付けが弱いもの、ありきたりなものは厳しく低く付ける"""

EDITOR_SYSTEM = f"""あなたはフォロワー 10 万人のガジェット系 X アカウントの「中の人」で、投稿の最終チェック担当です。
執筆担当が書いた下書きを、人が書いたように読める投稿に書き直します。

やること:
- 運用方針の「語り口」に合わせて本文を書き直す。報道調・説明書調・AI っぽい言い回しを全部なくす
- 読者が「へえ」「それ知りたかった」と思う一点を冒頭に出す。情報を詰め込みすぎていたら削る
- 投稿ごとに形と長さを変える。全部が「冒頭 → 箇条書き → 締め」になっていたら崩す
- 図解の見出し・項目・結論も話し言葉に直す（事実の中身は変えない）
- 書き直した結果で score を付け直す。AI っぽさが消えないものは 6 以下にする

変えてはいけないもの:
- 製品名・数字・日付・価格などの事実（言い方は変えてよい）。事実を足すこともしない
- sources と topic
- 使用体験の作り話を足さない
- 半角換算 {MAX_WEIGHTED_LENGTH} 以内"""

FACTCHECK_SYSTEM = """あなたはガジェット系 X アカウントの校閲担当です。
各下書きの本文と図解（見出し・表・項目・数字・結論・注記）を調査メモと照合します。

supported を false にするもの:
- 調査メモに書かれていない事実（製品名、数値、価格、日付、色、無料かどうか、対象機種、機能など）が 1 つでもある
- 数字や日付が調査メモと食い違う
- 種類の違う製品を同列に比べるなど、読者に誤解を与える
- 実際に使ったかのような体験談がある

意見・感想（「地味にうれしい」「迷ったらこっちでいい」など）は照合の対象外です。"""

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
    return _drafts_request(client, WRITER_SYSTEM, user_msg, "執筆")


def edit_drafts(client: anthropic.Anthropic, strategy: str, drafts: list[Draft]) -> list[Draft]:
    user_msg = f"""# 運用方針
{strategy}

# 下書き（JSON）
{Drafts(posts=drafts).model_dump_json(indent=2)}

# 依頼
すべての下書きを書き直し、同じ本数・同じ順番で返してください。"""
    return _drafts_request(client, EDITOR_SYSTEM, user_msg, "編集")


def check_facts(client: anthropic.Anthropic, memo: str, drafts: list[Draft]) -> dict[int, str]:
    """根拠のない事実や誤解を招く表現がある下書きの {番号: 理由} を返す。"""
    numbered = "\n\n".join(f"## 下書き {i}\n{d.model_dump_json(indent=2)}" for i, d in enumerate(drafts))
    user_msg = f"""# 調査メモ
{memo}

# 下書き
{numbered}

# 依頼
すべての下書きを照合し、番号ごとに結果を返してください。"""
    response = _request(
        client,
        system=FACTCHECK_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        output_format=FactChecks,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"校閲結果を読み取れませんでした（stop_reason={response.stop_reason}）")
    checked = {r.index: r for r in response.parsed_output.results}
    # 結果が返ってこなかった下書きも、確認できなかったものとして除外する
    return {
        i: (checked[i].problem if i in checked else "校閲結果なし")
        for i in range(len(drafts))
        if i not in checked or not checked[i].supported
    }


def _drafts_request(client: anthropic.Anthropic, system: str, user_msg: str, label: str) -> list[Draft]:
    response = _request(
        client,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        output_format=Drafts,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"{label}が断られました")
    if response.parsed_output is None:
        raise RuntimeError(f"{label}結果を読み取れませんでした（stop_reason={response.stop_reason}）")
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
        drafts = edit_drafts(client, strategy, drafts)
        rejected = check_facts(client, memo, drafts)
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
    for i, d in enumerate(drafts):
        text = d.text.strip()
        if i in rejected:
            print(f"校閲で除外（{rejected[i]}）: {text[:30]}…")
            continue
        banned = [w for w in BANNED_PHRASES if w in text]
        if not text or weighted_length(text) > MAX_WEIGHTED_LENGTH:
            print(f"長さが条件外のため除外: {text[:30]}…")
        elif banned:
            print(f"AI っぽい言い回し（{'、'.join(banned)}）のため除外: {text[:30]}…")
        elif d.score < MIN_SCORE:
            print(f"点数 {d.score} のため除外: {text[:30]}…")
        else:
            candidates.append(d)
    candidates.sort(key=lambda d: d.score, reverse=True)

    # 同じメーカー・イベントばかりにならないよう、topic ごとの本数を抑える
    selected: list[Draft] = []
    per_topic: dict[str, int] = {}
    for d in candidates:
        key = d.topic.strip().lower()
        if key != "一般" and per_topic.get(key, 0) >= MAX_PER_TOPIC:
            print(f"「{d.topic}」が多いため除外: {d.text[:30]}…")
            continue
        per_topic[key] = per_topic.get(key, 0) + 1
        selected.append(d)

    added = 0
    for d in selected[:needed]:
        post_id = uuid.uuid4().hex[:12]
        entry = {
            "id": post_id,
            "text": d.text.strip(),
            "category": d.category,
            "topic": d.topic,
            "score": d.score,
            "sources": d.sources,
            "status": "queued",
            "created_at": now_jst(),
        }
        if d.image.kind != "none":
            path = render(d.image.model_dump(), IMAGES_DIR / f"{post_id}.png", tag=d.category)
            entry["image"] = str(path.relative_to(QUEUE_PATH.parent.parent))
        queue.append(entry)
        added += 1

    save_queue(queue)
    print(f"{added} 本の投稿案を追加しました（候補 {len(drafts)} 本中）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
