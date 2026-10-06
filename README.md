# x-automation

X アカウント「まさ｜AIのとりこ」の運用を自動化するプロジェクトです。
26歳がAIと一緒に作ったものを記録していくアカウントで、**投稿はオーナーが毎回 GO したものだけ**が出ます。
（2026/10/6 まではガジェット情報の完全自動アカウント「ガジェットの選び方ノート」として運用していました）

## 仕組み

```
毎朝 4:52       Claude Code のルーティンが ROUTINE.md の手順で下書きを 2 本作る（月額プランの範囲内）
                 → config/works.md（作品のネタ帳）の事実だけで書き、図解を目で確認 → 下書きとして push
                 → オーナーのスマホに通知。オーナーはルーティンの会話で「GO」か直しを返すだけ
7:30 / 12:15 / 21:00 の時間帯   GitHub Actions が GO 済みの投稿を 1 本ずつ X に投稿（画像付きなら画像も）
```

- 下書き・投稿は `queue/posts.json` で確認できます（`draft` = GO 待ち、`queued` = GO 済み、`posted` = 投稿済み）
- 手で GO するときは `python src/approve.py go <id>`（一覧は `python src/approve.py list`）
- 投稿を止めたいときは、Variables に `POSTING_ENABLED` = `false` を登録します（削除すると再開）

## 最初にやること（オーナー作業）

| # | 作業 | 備考 |
|---|---|---|
| 1 | X アカウントを作る | Gmail は何でも可。電話番号認証あり |
| 2 | X Premium に加入 | 収益化の必須条件 |
| 3 | プロフィールに「自動化ラベル」を付ける | 設定 → アカウント情報 → 自動化 から、管理者アカウントを指定 |
| 4 | [X Developer Portal](https://developer.x.com/) でアプリを作り、キーを発行 | User authentication settings で **Read and Write** を選んでから Access Token を発行。支払い方法を登録してクレジットを購入（投稿 1 本 約 $0.015） |
| 5 | [Anthropic Console](https://platform.claude.com/) で API キーを発行 | Claude のサブスクとは別の従量課金。クレジットを購入 |
| 6 | キーを GitHub に登録 | 下記参照。**キーはチャットに貼らないこと** |

### キーの登録場所

GitHub のこのリポジトリ → Settings → Secrets and variables → Actions

**Secrets**（New repository secret）:

| 名前 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic の API キー |
| `X_API_KEY` | X の API Key（Consumer Key） |
| `X_API_SECRET` | X の API Key Secret |
| `X_ACCESS_TOKEN` | X の Access Token |
| `X_ACCESS_TOKEN_SECRET` | X の Access Token Secret |

**Variables**（Variables タブ → New repository variable）:

| 名前 | 値 |
|---|---|
| `POSTING_ENABLED` | `false` にすると投稿を一時停止 |
| `POSTS_PER_DAY` | 1 日の投稿数（省略時 3） |

## 構成

```
config/strategy.md          運用方針（ジャンル・口調・投稿の型・収益導線）
queue/posts.json            投稿案と投稿履歴
src/generate.py             投稿案の生成（手動実行だけの予備。作るのは下書き）
src/approve.py              下書きの GO・取り下げ・直し
config/works.md             作品のネタ帳（投稿に使ってよい事実）
src/post.py                 X への投稿
.github/workflows/          自動実行のスケジュール
```

## 運用ルール

X の自動化ルールに沿い、次のことはしません。

- 自動フォロー、自動いいね、自動リプライ
- 同じ内容の繰り返し投稿、複数アカウントの運用

## 今後の予定

1. 投稿ごとの表示回数などを集めて、伸びた型に寄せる仕組みを追加する
2. 収益導線（アフィリエイト、note など）を用意する
