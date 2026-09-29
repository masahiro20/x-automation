"""queue/posts.json の先頭の投稿案を X に 1 本投稿する。

GitHub Actions の定期実行は数時間遅れることがあるため、投稿時間帯の間は短い間隔で起動し、
「予定時刻を過ぎていて、その枠でまだ投稿していない」ときだけ投稿する。

環境変数:
    POSTING_ENABLED        "false" にすると一時停止（内容を表示するだけ）。未設定なら投稿する
    FORCE_POST             "true" なら時間帯に関係なく投稿する（手動実行用）
    X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET
                           X Developer Portal で発行したキー（Read and Write 権限）
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, time, timedelta

import tweepy
from requests_oauthlib import OAuth1Session

from common import JST, ROOT, load_queue, now_jst, save_queue

X_ENV_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"

# 投稿枠（日本時間）。post.yml の cron はこの枠の開始から WINDOW の間をカバーする
SLOTS = (time(7, 30), time(12, 15), time(21, 0))
WINDOW = timedelta(minutes=150)


def due_slot(now: datetime, queue: list[dict]) -> datetime | None:
    """今が投稿枠の中で、その枠でまだ投稿していなければ枠の開始時刻を返す。"""
    posted_times = [datetime.fromisoformat(p["posted_at"]) for p in queue if p.get("posted_at")]
    for slot in SLOTS:
        start = datetime.combine(now.date(), slot, tzinfo=JST)
        if start <= now < start + WINDOW and not any(start <= t <= now for t in posted_times):
            return start
    return None


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
    if os.environ.get("FORCE_POST") != "true":
        slot = due_slot(datetime.now(JST), queue)
        if slot is None:
            print("投稿枠の時間外か、この枠は投稿済みです。")
            return 0
        print(f"{slot:%H:%M} の枠で投稿します。")

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
