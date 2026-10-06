"""Claude Code（毎朝のルーティン）が書いた投稿案をチェックして、下書き（status "draft"）として追加する。

下書きは投稿されない。オーナーが GO したものだけを src/approve.py で投稿待ち（"queued"）にする。

使い方:
    python src/add_posts.py drafts.json             チェック → 画像を描く → queue/posts.json に下書きとして追加
    python src/add_posts.py drafts.json --preview D  チェックして画像を D に描くだけ（キューは変えない）

drafts.json の形:
    {"posts": [{"text": "...", "category": "作品紹介", "topic": "マドリ3D",
                "sources": ["https://..."], "image": {...} または null}]}
image の中身は src/render.py の render() に渡す spec（kind は table / checklist / number）。
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from common import (
    BANNED_PHRASES,
    MAX_WEIGHTED_LENGTH,
    QUEUE_PATH,
    ROOT,
    load_queue,
    now_jst,
    save_queue,
    weighted_length,
)
from render import render

IMAGES_DIR = QUEUE_PATH.parent / "images"
MAX_PER_TOPIC = 2
IMAGE_KINDS = ("table", "checklist", "number")
# 出典がなくてよい型（本人の考え・問いかけ）
NO_SOURCE_CATEGORIES = ("問いかけ", "つぶやき")
# まだ投稿されていない状態（同じ話題の本数を数えるときに使う）
PENDING = ("draft", "queued")


def problems_of(post: dict) -> list[str]:
    text = post.get("text", "").strip()
    found = []
    if not text:
        found.append("本文が空")
    elif weighted_length(text) > MAX_WEIGHTED_LENGTH:
        found.append(f"長すぎる（{weighted_length(text)} / {MAX_WEIGHTED_LENGTH}）")
    banned = [w for w in BANNED_PHRASES if w in text]
    if banned:
        found.append(f"AI っぽい言い回し: {'、'.join(banned)}")
    if post.get("category") not in NO_SOURCE_CATEGORIES and not post.get("sources"):
        found.append("出典（sources）がない")
    image = post.get("image")
    if image and image.get("kind") not in IMAGE_KINDS:
        found.append(f"画像の種類が不明: {image.get('kind')}")
    return found


def order_by_topic(posts: list[dict], last_topic: str) -> list[dict]:
    """同じ topic の投稿が続かないように並べる。"""
    ordered, pool = [], list(posts)
    while pool:
        pick = next((p for p in pool if p.get("topic") != last_topic), pool[0])
        pool.remove(pick)
        ordered.append(pick)
        last_topic = pick.get("topic", "")
    return ordered


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    drafts = json.loads(Path(args[0]).read_text(encoding="utf-8"))["posts"]
    preview_dir = Path(args[args.index("--preview") + 1]) if "--preview" in args else None

    queue = load_queue()
    queued = [p for p in queue if p["status"] in PENDING]
    per_topic: dict[str, int] = {}
    for p in queued:
        key = p.get("topic", "").lower()
        per_topic[key] = per_topic.get(key, 0) + 1

    accepted = []
    for i, post in enumerate(drafts):
        found = problems_of(post)
        key = post.get("topic", "一般").strip().lower()
        if key != "一般" and per_topic.get(key, 0) >= MAX_PER_TOPIC:
            found.append(f"「{post.get('topic')}」の未投稿がすでに {MAX_PER_TOPIC} 本ある")
        if found:
            print(f"NG {i}: {post.get('text', '')[:30]}… → {' / '.join(found)}")
            continue
        per_topic[key] = per_topic.get(key, 0) + 1
        accepted.append(post)
        print(f"OK {i}: {post['text'][:30]}…（{weighted_length(post['text'])} / {MAX_WEIGHTED_LENGTH}）")

    if preview_dir:
        for i, post in enumerate(accepted):
            if post.get("image"):
                path = render(post["image"], preview_dir / f"preview_{i}.png", tag=post.get("category", ""))
                print(f"画像: {path}")
        return 0

    last_topic = queued[-1].get("topic", "") if queued else ""
    for post in order_by_topic(accepted, last_topic):
        post_id = uuid.uuid4().hex[:12]
        entry = {
            "id": post_id,
            "text": post["text"].strip(),
            "category": post.get("category", ""),
            "topic": post.get("topic", "一般"),
            "sources": post.get("sources", []),
            "status": "draft",
            "created_at": now_jst(),
            "author": "claude-code",
        }
        if post.get("image"):
            path = render(post["image"], IMAGES_DIR / f"{post_id}.png", tag=entry["category"])
            entry["image"] = str(path.relative_to(ROOT))
            entry["image_spec"] = post["image"]
            print(f"画像: {entry['image']}")
        queue.append(entry)
    save_queue(queue)
    print(f"{len(accepted)} 本を下書きに追加しました（未投稿 合計 {len(queued) + len(accepted)} 本）。")
    for entry in queue[-len(accepted):] if accepted else []:
        print(f"  {entry['id']}: {entry['text'].splitlines()[0][:40]}")
    return 0 if len(accepted) == len(drafts) else 2


if __name__ == "__main__":
    sys.exit(main())
