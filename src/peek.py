"""参考にしたい X アカウントのプロフィールと最近の投稿をログに出す（研究用）。

X API の料金: ユーザー情報 1 件 + 投稿の読み取り 1 件ずつ（1 件 $0.005 程度）。

使い方: python src/peek.py <ユーザー名> [件数]
"""

from __future__ import annotations

import os
import sys

import tweepy

from post import X_ENV_KEYS


def main() -> int:
    if len(sys.argv) < 2:
        print("使い方: python src/peek.py <ユーザー名> [件数]", file=sys.stderr)
        return 1
    username = sys.argv[1].lstrip("@").split("?")[0].split("/")[-1]
    count = min(max(int(sys.argv[2]) if len(sys.argv) > 2 else 10, 5), 30)

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
        user = client.get_user(
            username=username, user_auth=True, user_fields=["description", "public_metrics", "created_at"]
        ).data
        if user is None:
            print(f"@{username} が見つかりません")
            return 1
        m = user.public_metrics
        print(f"# {user.name} (@{user.username})")
        print(f"フォロワー {m['followers_count']} / フォロー {m['following_count']} / 投稿 {m['tweet_count']}")
        print(f"開始 {user.created_at:%Y-%m-%d}")
        print(f"自己紹介:\n{user.description}\n")

        tweets = client.get_users_tweets(
            user.id,
            max_results=count,
            exclude=["retweets", "replies"],
            tweet_fields=["created_at", "public_metrics", "attachments"],
            user_auth=True,
        ).data or []
    except tweepy.TweepyException as e:
        print(f"取得に失敗しました: {e}", file=sys.stderr)
        return 1

    for t in tweets:
        pm = t.public_metrics
        media = "［画像/動画あり］" if t.attachments else ""
        print(f"---- {t.created_at:%m/%d %H:%M}  いいね {pm['like_count']} / RP {pm['retweet_count']} / 返信 {pm['reply_count']} {media}")
        print(t.text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
