"""登録したキーが使えるかを、投稿せずに確かめる。

X: 自分のアカウント情報を取得する（1 回あたり $0.001 程度）
Claude: モデル情報を取得する（無料）
"""

from __future__ import annotations

import os
import sys

import anthropic
import tweepy

from generate import MODEL
from post import X_ENV_KEYS


def check_x() -> bool:
    missing = [k for k in X_ENV_KEYS if not os.environ.get(k)]
    if missing:
        print(f"NG X: 未登録のキーがあります: {', '.join(missing)}")
        return False
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    try:
        me = client.get_me(user_auth=True)
    except tweepy.Unauthorized:
        print("NG X: キーが正しくありません。4 つの値と、登録した名前を確認してください")
        return False
    except tweepy.TooManyRequests:
        print("NG X: 回数制限に達しました。しばらくして再実行してください")
        return False
    except tweepy.TweepyException as e:
        print(f"NG X: {e}（クレジット未購入の場合もこのエラーになります）")
        return False
    print(f"OK X: @{me.data.username} として接続できました")
    return True


def check_claude() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("NG Claude: ANTHROPIC_API_KEY が未登録です")
        return False
    try:
        anthropic.Anthropic().models.retrieve(MODEL)
    except anthropic.AuthenticationError:
        print("NG Claude: ANTHROPIC_API_KEY が正しくありません")
        return False
    except anthropic.APIStatusError as e:
        print(f"NG Claude: {e.status_code} {e.message}")
        return False
    except anthropic.APIConnectionError:
        print("NG Claude: 接続できませんでした")
        return False
    print(f"OK Claude: {MODEL} を使えます")
    return True


def main() -> int:
    results = [check_x(), check_claude()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
