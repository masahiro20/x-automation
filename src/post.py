"""queue/posts.json の先頭の投稿案を X に 1 本投稿する。

環境変数:
    POSTING_ENABLED        "false" にすると一時停止（内容を表示するだけ）。未設定なら投稿する
    X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET
                           X Developer Portal で発行したキー（Read and Write 権限）
"""

from __future__ import annotations

import os
import sys

import tweepy

from common import load_queue, now_jst, save_queue

X_ENV_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")


def main() -> int:
    queue = load_queue()
    target = next((p for p in queue if p["status"] == "queued"), None)
    if target is None:
        print("投稿待ちの投稿案がありません。")
        return 0

    if os.environ.get("POSTING_ENABLED") == "false":
        print("[一時停止中] 次の内容は投稿されていません:\n" + target["text"])
        return 0

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
    try:
        response = client.create_tweet(text=target["text"])
    except tweepy.Forbidden as e:
        # 重複投稿や権限不足。同じ案で再試行し続けないよう skipped にする
        target["status"] = "skipped"
        target["error"] = str(e)
        save_queue(queue)
        print(f"投稿が拒否されたためスキップしました: {e}", file=sys.stderr)
        return 1
    except tweepy.TweepyException as e:
        print(f"投稿に失敗しました: {e}", file=sys.stderr)
        return 1

    target["status"] = "posted"
    target["posted_at"] = now_jst()
    target["tweet_id"] = response.data["id"]
    save_queue(queue)
    print(f"投稿しました: https://x.com/i/web/status/{target['tweet_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
