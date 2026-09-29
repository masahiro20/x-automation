"""config/profile.json の内容で X のプロフィール（名前・自己紹介・アイコン・ヘッダー）を更新する。

X API v2 にはプロフィール更新がないため、v1.1 のエンドポイントを使う。
"""

from __future__ import annotations

import json
import os
import sys

import tweepy

from common import ROOT
from post import X_ENV_KEYS

PROFILE_PATH = ROOT / "config" / "profile.json"
MAX_NAME = 50
MAX_DESCRIPTION = 160


def main() -> int:
    missing = [k for k in X_ENV_KEYS if not os.environ.get(k)]
    if missing:
        print(f"X の API キーが未設定です: {', '.join(missing)}", file=sys.stderr)
        return 1

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if len(profile["name"]) > MAX_NAME or len(profile["description"]) > MAX_DESCRIPTION:
        print(f"名前は {MAX_NAME} 文字、自己紹介は {MAX_DESCRIPTION} 文字までです", file=sys.stderr)
        return 1

    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    api = tweepy.API(auth)

    steps = [
        ("名前・自己紹介", lambda: api.update_profile(name=profile["name"], description=profile["description"])),
    ]
    # 同じ画像を再アップロードすると X に拒否されるため、画像は指定したときだけ更新する
    if os.environ.get("PROFILE_TARGET") == "all":
        steps += [
            ("アイコン", lambda: api.update_profile_image(str(ROOT / profile["icon"]))),
            ("ヘッダー", lambda: api.update_profile_banner(str(ROOT / profile["banner"]))),
        ]
    ok = True
    for label, step in steps:
        try:
            step()
            print(f"OK {label}")
        except tweepy.TweepyException as e:
            print(f"NG {label}: {e}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
