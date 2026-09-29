# x-automation

X（旧Twitter）のガジェット系アカウントを自動運用するリポジトリ。概要は README.md。

- 投稿案づくり（毎朝）: Claude Code のルーティンが `ROUTINE.md` の手順で行う
- 投稿: GitHub Actions（`.github/workflows/post.yml`）が `queue/posts.json` から時間帯ごとに 1 本ずつ
- 運用方針: `config/strategy.md`（キャラクター・語り口・投稿の型・禁止事項）
- API で投稿案を作る `src/generate.py` は、ルーティンが失敗して投稿待ちが尽きかけたときの予備

テスト: `python -m pytest -q tests`
