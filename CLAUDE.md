# x-automation

X（旧Twitter）アカウント「まさ｜AIのとりこ」（AIで作ったものの制作ログ）を運用するリポジトリ。概要は README.md。
**投稿されるのは、オーナーが GO した下書きだけ**（下書き = status `draft`、GO 済み = `queued`）。

- 下書きづくり（毎朝）: Claude Code のルーティンが `ROUTINE.md` の手順で行い、オーナーの GO を `src/approve.py` で反映する
- 投稿: GitHub Actions（`.github/workflows/post.yml`）が `queue/posts.json` から時間帯ごとに 1 本ずつ
- 運用方針: `config/strategy.md`（キャラクター・語り口・投稿の型・禁止事項）
- 作品のネタ帳: `config/works.md`（投稿に使ってよい事実はここにあるものだけ）
- API で投稿案を作る `src/generate.py` は手動実行だけの予備（作るのは下書き）

テスト: `python -m pytest -q tests`
