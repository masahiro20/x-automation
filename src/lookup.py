"""フォロー候補のアカウントと、参加候補のコミュニティを X API で確かめる（研究用）。

使い方: python src/lookup.py "ユーザー名1,ユーザー名2,..." "コミュニティ検索語1,検索語2"
X API の料金: ユーザー情報・コミュニティ検索とも 1 件あたり数円以下。
"""

from __future__ import annotations

import os
import sys

import tweepy
from requests_oauthlib import OAuth1Session

from post import X_ENV_KEYS

COMMUNITY_SEARCH_URL = "https://api.x.com/2/communities/search"


def main() -> int:
    missing = [k for k in X_ENV_KEYS if not os.environ.get(k)]
    if missing:
        print(f"X の API キーが未設定です: {', '.join(missing)}", file=sys.stderr)
        return 1
    usernames = [u.strip().lstrip("@") for u in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if u.strip()]
    queries = [q.strip() for q in (sys.argv[2] if len(sys.argv) > 2 else "").split(",") if q.strip()]

    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    if usernames:
        print("# アカウント")
        for i in range(0, len(usernames), 100):
            try:
                res = client.get_users(
                    usernames=usernames[i : i + 100],
                    user_auth=True,
                    user_fields=["description", "public_metrics", "most_recent_tweet_id", "verified_type"],
                )
            except tweepy.TweepyException as e:
                print(f"取得に失敗: {e}")
                continue
            found = {u.username.lower(): u for u in (res.data or [])}
            for name in usernames[i : i + 100]:
                u = found.get(name.lower())
                if u is None:
                    print(f"NG @{name}（見つからない）")
                    continue
                m = u.public_metrics
                desc = (u.description or "").replace("\n", " ")[:60]
                print(f"OK @{u.username} | {u.name} | フォロワー {m['followers_count']} | 投稿 {m['tweet_count']} | {desc}")

    if queries:
        session = OAuth1Session(
            os.environ["X_API_KEY"],
            client_secret=os.environ["X_API_SECRET"],
            resource_owner_key=os.environ["X_ACCESS_TOKEN"],
            resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        print("\n# コミュニティ")
        for q in queries:
            r = session.get(
                COMMUNITY_SEARCH_URL,
                params={"query": q, "max_results": 10, "community.fields": "member_count,description,access"},
                timeout=30,
            )
            if r.status_code != 200:
                print(f"NG 「{q}」: {r.status_code} {r.text[:200]}")
                continue
            for c in r.json().get("data", []):
                desc = (c.get("description") or "").replace("\n", " ")[:60]
                print(
                    f"「{q}」 id={c['id']} | {c.get('name')} | メンバー {c.get('member_count')} | "
                    f"{c.get('access', '')} | {desc}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
