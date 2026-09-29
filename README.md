# x-automation

X（旧Twitter）アカウントの投稿を自動化し、収益化を目指すプロジェクトです。

## 仕組み

```
毎朝 5:00ごろ   Claude Code のルーティンが ROUTINE.md の手順で投稿案を作る（月額プランの範囲内）
                 → ネタを調べ、出典で確かめ、書いて、図解を目で確認 → queue/ に追加して push
7:30 / 12:15 / 21:00 の時間帯   GitHub Actions が投稿案を 1 本ずつ X に投稿（画像付きなら画像も）
10:00（予備）    投稿待ちが 2 本未満のときだけ、API（src/generate.py）で補充
```

- 投稿案は `queue/posts.json` で確認できます。各投稿の出典 URL（`sources`）も記録されています
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
src/generate.py             投稿案の生成
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
