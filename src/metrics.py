"""投稿済みの投稿の数字（表示回数・いいね・返信・リポスト・保存）とフォロワー数を集めて記録する。

X API の料金: 自分の投稿の読み取り 1 件あたり $0.001 程度。
結果は logs/metrics.json（最新の値）と logs/followers.jsonl（フォロワー数の推移）に保存する。
"""

from __future__ import annotations

import json
import os
import sys

import tweepy

from common import ROOT, load_queue, now_jst
from post import X_ENV_KEYS

METRICS_PATH = ROOT / "logs" / "metrics.json"
FOLLOWERS_PATH = ROOT / "logs" / "followers.jsonl"


def main() -> int:
    missing = [k for k in X_ENV_KEYS if not os.environ.get(k)]
    if missing:
        print(f"X の API キーが未設定です: {', '.join(missing)}", file=sys.stderr)
        return 1
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    posted = [p for p in load_queue() if p.get("tweet_id")]
    try:
        me = client.get_me(user_auth=True, user_fields=["public_metrics"]).data
        rows = []
        # 1 回に 100 件まで
        for i in range(0, len(posted), 100):
            chunk = posted[i : i + 100]
            res = client.get_tweets(
                [p["tweet_id"] for p in chunk], tweet_fields=["public_metrics"], user_auth=True
            )
            metrics = {str(t.id): t.public_metrics for t in (res.data or [])}
            for p in chunk:
                m = metrics.get(str(p["tweet_id"]))
                if m is None:
                    continue
                rows.append(
                    {
                        "id": p["id"],
                        "tweet_id": p["tweet_id"],
                        "posted_at": p["posted_at"],
                        "category": p.get("category", ""),
                        "topic": p.get("topic", ""),
                        "author": p.get("author", "api"),
                        "has_image": bool(p.get("image")),
                        "head": p["text"].split("\n")[0][:40],
                        "impressions": m.get("impression_count", 0),
                        "likes": m.get("like_count", 0),
                        "replies": m.get("reply_count", 0),
                        "reposts": m.get("retweet_count", 0) + m.get("quote_count", 0),
                        "bookmarks": m.get("bookmark_count", 0),
                    }
                )
    except tweepy.TweepyException as e:
        print(f"取得に失敗しました: {e}", file=sys.stderr)
        return 1

    followers = me.public_metrics["followers_count"]
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(
        json.dumps({"at": now_jst(), "followers": followers, "posts": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with FOLLOWERS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now_jst(), "followers": followers}) + "\n")

    print(f"フォロワー {followers} 人 / 投稿 {len(rows)} 本")
    total = sum(r["impressions"] for r in rows)
    print(f"表示回数 合計 {total}（1 投稿あたり {total / max(len(rows), 1):.0f}）")
    for r in sorted(rows, key=lambda r: r["impressions"], reverse=True):
        print(
            f"{r['posted_at'][5:16]} 表示 {r['impressions']:>5} いいね {r['likes']:>3} 返信 {r['replies']:>2} "
            f"RP {r['reposts']:>2} 保存 {r['bookmarks']:>2} {'画像' if r['has_image'] else '文字'} "
            f"[{r['category']}] {r['head']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
