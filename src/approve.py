"""オーナーの返事に合わせて、下書きを投稿待ちにする（GO）・取り下げる・本文を直す。

使い方:
    python src/approve.py list                 下書きの一覧（id と冒頭 1 行）
    python src/approve.py go ID [ID ...]       その下書きを投稿待ち（queued）にする
    python src/approve.py go all               下書きを全部投稿待ちにする
    python src/approve.py drop ID [ID ...]     その下書きを取り下げる（rejected）
    python src/approve.py edit ID TEXT_FILE    本文を TEXT_FILE の中身に差し替える（下書きのまま）

投稿待ちになったものは、.github/workflows/post.yml が次の投稿枠で古い順に 1 本ずつ投稿する。
"""

from __future__ import annotations

import sys
from pathlib import Path

from add_posts import problems_of
from common import load_queue, now_jst, save_queue


def drafts_of(queue: list[dict]) -> list[dict]:
    return [p for p in queue if p.get("status") == "draft"]


def pick(queue: list[dict], ids: list[str]) -> list[dict]:
    drafts = drafts_of(queue)
    if ids == ["all"]:
        return drafts
    by_id = {p["id"]: p for p in drafts}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"下書きに見つからない id: {', '.join(missing)}")
    return [by_id[i] for i in ids]


def go(queue: list[dict], ids: list[str]) -> list[dict]:
    picked = pick(queue, ids)
    for p in picked:
        p["status"] = "queued"
        p["approved_at"] = now_jst()
    return picked


def drop(queue: list[dict], ids: list[str]) -> list[dict]:
    picked = pick(queue, ids)
    for p in picked:
        p["status"] = "rejected"
    return picked


def edit(queue: list[dict], post_id: str, text: str) -> dict:
    (target,) = pick(queue, [post_id])
    # 直すのは本文だけなので、本文と出典だけを確かめる（添付の画像・動画はそのまま）
    found = problems_of({"text": text, "category": target.get("category"), "sources": target.get("sources")})
    if found:
        raise SystemExit("直した本文に問題があります: " + " / ".join(found))
    target["text"] = text.strip()
    target["edited_at"] = now_jst()
    return target


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] not in ("list", "go", "drop", "edit"):
        print(__doc__)
        return 1
    queue = load_queue()
    command = args[0]

    if command == "list":
        for p in drafts_of(queue):
            print(f"{p['id']}: [{p.get('category', '')}] {p['text'].splitlines()[0][:40]}")
        return 0

    if command == "edit":
        if len(args) != 3:
            print(__doc__)
            return 1
        target = edit(queue, args[1], Path(args[2]).read_text(encoding="utf-8"))
        save_queue(queue)
        print(f"直しました: {target['id']}: {target['text'].splitlines()[0][:40]}")
        return 0

    if len(args) < 2:
        print(__doc__)
        return 1
    picked = (go if command == "go" else drop)(queue, args[1:])
    save_queue(queue)
    label = "投稿待ちにしました" if command == "go" else "取り下げました"
    for p in picked:
        print(f"{label}: {p['id']}: {p['text'].splitlines()[0][:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
