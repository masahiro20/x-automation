"""queue/posts.json の先頭の投稿案を X に 1 本投稿する。

GitHub Actions の定期実行は数時間遅れることがあるため、投稿時間帯の間は短い間隔で起動し、
「予定時刻を過ぎていて、その枠でまだ投稿していない」ときだけ投稿する。

環境変数:
    POSTING_ENABLED        "false" にすると一時停止（内容を表示するだけ）。未設定なら投稿する
    FORCE_POST             "true" なら時間帯に関係なく投稿する（手動実行で force を選んだとき）
    X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET
                           X Developer Portal で発行したキー（Read and Write 権限）
"""

from __future__ import annotations

import os
import sys
import time as clock
from datetime import datetime, time, timedelta

import tweepy
from requests_oauthlib import OAuth1Session

from common import JST, ROOT, load_queue, now_jst, save_queue

X_ENV_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
# 動画は分割アップロード（1 回 5MB まで）。initialize → append → finalize → 処理が終わるまで status を確認
VIDEO_CHUNK_BYTES = 4 * 1024 * 1024
VIDEO_WAIT_LIMIT_SECONDS = 300

# 投稿枠（日本時間）。各枠は次の枠が始まるまで有効（最後の枠は日付が変わるまで）。
# 定期実行が遅れても、次の枠までに 1 回でも動けば取りこぼさない
SLOTS = (time(7, 30), time(12, 15), time(21, 0))


def due_slot(now: datetime, queue: list[dict]) -> datetime | None:
    """今が投稿枠の中で、その枠でまだ投稿していなければ枠の開始時刻を返す。"""
    posted_times = [datetime.fromisoformat(p["posted_at"]) for p in queue if p.get("posted_at")]
    starts = [datetime.combine(now.date(), slot, tzinfo=JST) for slot in SLOTS]
    ends = starts[1:] + [datetime.combine(now.date() + timedelta(days=1), time(0, 0), tzinfo=JST)]
    for start, end in zip(starts, ends):
        if start <= now < end and not any(start <= t <= now for t in posted_times):
            return start
    return None


def x_session() -> OAuth1Session:
    return OAuth1Session(
        os.environ["X_API_KEY"],
        client_secret=os.environ["X_API_SECRET"],
        resource_owner_key=os.environ["X_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def chunks(data: bytes, size: int = VIDEO_CHUNK_BYTES) -> list[bytes]:
    return [data[i : i + size] for i in range(0, len(data), size)] or [b""]


def upload_video(path: str) -> str:
    """mp4 を分割アップロードし、X 側の処理が終わったら media id を返す。"""
    session = x_session()
    data = (ROOT / path).read_bytes()
    init = session.post(
        f"{MEDIA_UPLOAD_URL}/initialize",
        json={"media_type": "video/mp4", "total_bytes": len(data), "media_category": "tweet_video"},
        timeout=60,
    )
    init.raise_for_status()
    media_id = init.json()["data"]["id"]
    for index, chunk in enumerate(chunks(data)):
        r = session.post(
            f"{MEDIA_UPLOAD_URL}/{media_id}/append",
            files={"media": ("chunk", chunk, "application/octet-stream")},
            data={"segment_index": index},
            timeout=120,
        )
        r.raise_for_status()
    fin = session.post(f"{MEDIA_UPLOAD_URL}/{media_id}/finalize", timeout=60)
    fin.raise_for_status()
    info = fin.json().get("data", {}).get("processing_info")
    waited = 0
    while info and info.get("state") in ("pending", "in_progress"):
        wait = max(1, int(info.get("check_after_secs", 5)))
        if waited + wait > VIDEO_WAIT_LIMIT_SECONDS:
            raise RuntimeError("動画の処理が時間内に終わりませんでした")
        clock.sleep(wait)
        waited += wait
        st = session.get(MEDIA_UPLOAD_URL, params={"command": "STATUS", "media_id": media_id}, timeout=60)
        st.raise_for_status()
        info = st.json().get("data", {}).get("processing_info")
    if info and info.get("state") == "failed":
        raise RuntimeError(f"動画の処理に失敗しました: {info.get('error')}")
    return media_id


def upload_image(path: str) -> str:
    """画像を X にアップロードし、media id を返す（tweepy は v2 のアップロードに未対応）。"""
    session = x_session()
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
    if target.get("video"):
        # 動画が主役の投稿なので、動画が載らないときは投稿せず次の枠でやり直す
        try:
            media_ids = [upload_video(target["video"])]
        except Exception as e:
            print(f"動画のアップロードに失敗したため、この枠では投稿しません: {e}", file=sys.stderr)
            return 1
    elif target.get("image"):
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
