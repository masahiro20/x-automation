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
from requests_oauthlib import OAuth1Session

from common import ROOT, load_queue, now_jst, save_queue

X_ENV_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"


def upload_image(path: str) -> str:
    """画像を X にアップロードし、media id を返す（tweepy は v2 のアップロードに未対応）。"""
    session = OAuth1Session(
        os.environ["X_API_KEY"],
        client_secret=os.environ["X_API_SECRET"],
        resource_owner_key=os.environ["X_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    with open(ROOT / path, "rb") as f:
        response = session.post(
            MEDIA_UPLOAD_URL,
            files={"media": (os.path.basename(path), f, "image/png")},
            data={"media_category": "tweet_image"},
            timeout=60,
        )
    response.raise_for_status()
    return response.json()["data"]["id"]


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
    media_ids = None
    if target.get("image"):
        try:
            media_ids = [upload_image(target["image"])]
        except Exception as e:  # 画像が失敗しても本文だけは投稿する
            print(f"画像のアップロードに失敗したため、本文のみ投稿します: {e}", file=sys.stderr)

    try:
        response = client.create_tweet(text=target["text"], media_ids=media_ids)
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
