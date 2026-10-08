# ルーティン（Claude Code の定期作業の手順）

このセッションには 2 種類のルーティンからメッセージが届き、そのあとオーナー（まさ）から返事が届く。
どれも、このリポジトリの持ち主から **`main` に直接コミットして push する許可**をもらっている
（作業用ブランチやプルリクエストは作らない）。

| メッセージ | やること |
|---|---|
| 「投稿案づくり」「下書きづくり」（毎朝 4:52） | 下の「毎朝の投稿案づくり（下書きづくり）」 |
| 「投稿の起動」（7:35 / 12:35 / 21:35） | 下の「投稿の起動」だけ。すぐ終わらせる |
| オーナーからの返事（「GO」「1だけGO」「2はこう直して」など） | 下の「オーナーの返事」 |

**投稿されるのは、オーナーが GO した下書きだけ。** 下書きは status `draft`、GO したものは `queued`。

## 投稿の起動
GitHub の定期実行があてにならないので、main に小さなコミットを push して投稿ワークフローを起動する。
二重投稿は `src/post.py` の枠チェックが防ぐので、気にせず push してよい。GO 済みが無ければ何も投稿されない。
```bash
git pull --ff-only origin main
date "+%Y-%m-%dT%H:%M:%S%z" > logs/heartbeat.txt
git add logs/heartbeat.txt && git commit -m "投稿の起動" && git push origin main
```
push が弾かれたら `git pull --rebase origin main` してからもう一度。報告は 1 行でよい。

---

# 毎朝の投稿案づくり（下書きづくり）

### 会話を短く保つ（使用量の上限対策）
- 大きなファイル（queue/posts.json など）は全部を読まず、必要な部分だけ python で取り出して表示する
- 途中経過の説明は書かず、最後の報告だけ短く書く

## 0. 準備
```bash
pip install -q -r requirements.txt
sudo apt-get install -y -qq fonts-noto-cjk >/dev/null 2>&1 || apt-get install -y -qq fonts-noto-cjk >/dev/null 2>&1
git pull --ff-only origin main
```

## 1. 今日作る本数を決める
- `python src/approve.py list` で、まだ GO されていない下書きを見る
- **目標は GO 待ちの下書き 2 本**。すでに 2 本以上あれば新しく作らず、その下書きを 5 の形でもう一度オーナーに見せる
- 足りない本数を `needed` とする

## 2. 読むもの
- `config/strategy.md`（運用方針。**必ず全部読む**）
- `config/works.md`（作品のネタ帳。**投稿に使ってよい事実はここにあるものだけ**）
- `queue/posts.json` の直近 20 本の本文と category・topic（同じ作品・同じ角度・同じ言い回しを避けるため）
- `logs/metrics.json`（投稿ごとの表示回数など）。伸びた型・作品を少し増やす。数字が小さいうちは参考程度

## 3. 書く
- `needed` 本の下書きを、スクラッチパッドの `drafts.json` に書く（形は `src/add_posts.py` の説明を参照）
  - `category` は運用方針の型（作品紹介 / 作り方の裏側 / 失敗・ハマりどころ / 数字 / つぶやき / 問いかけ）
  - `topic` は作品名（作品に関係ないものは「一般」）
  - `sources` は作品の URL かリポジトリの URL（つぶやき・問いかけは不要）
- **ネタは works.md の「投稿の角度リスト」から選ぶ**（まだ「済」が付いていない角度を上から）。2 本は違う作品にし、昨日と同じ作品は避ける。
  使った角度には works.md で「済 M/D」を付けて、下書きと一緒にコミットする
- 運用方針の「インプが伸びやすい書き方」を守る（動画最優先・冒頭 1 行・短く・本文にリンクを入れない）
- works.md の「エピソード」が空の作品は、体験や気持ちを作らず、事実（できること・仕組み・数字）で書く
- **角度リストに動画の指定があれば、その動画を `"video": "assets/demos/〇〇.mp4"` で付ける**（同じ動画は 1 週間に 1 回まで）
- **図解カード（`image`）は付けない**。動画が無いときは文字だけにする
- 運用方針の「絶対のルール」を守る（つないでいるツールや契約書などの中身は、文章にも動画にも出さない）
- 書いたら声に出して読んで、宣伝文や AI の文章に聞こえないかを確かめる

## 4. 確かめて、下書きとして追加
```bash
python src/add_posts.py drafts.json --preview <スクラッチパッド>/preview
```
- NG と出た候補は直すか外す
```bash
python src/add_posts.py drafts.json
git add queue/ && git commit -m "下書きを追加（Claude Code）" && git push origin main
```

## 5. オーナーに見せる
- ToolSearch で PushNotification を読み込み、オーナーのスマホに通知する（200 字以内）:
  「今日の投稿案 {N} 本できたよ。①{冒頭1行} ②{冒頭1行}｜GO なら『GO』、直すなら番号と直し方を返信してね」
- この会話に、下書きを番号付きで**全文**書く（番号・id・型・作品・本文・画像の有無）。
  works.md に無くて確かめたいことがあれば、下書きの下に「確認したいこと」として書く
- オーナーの返事を待つ

---

# オーナーの返事

オーナーが返事をしたら、その内容どおりに下書きを動かして push する。
```bash
git pull --ff-only origin main
python src/approve.py go ID [ID ...]     # 「GO」「全部GO」→ 見せた下書き全部。「1だけGO」→ その番号の id だけ
python src/approve.py drop ID            # 「2はなし」→ 取り下げ
python src/approve.py edit ID new.txt    # 「2はこう直して」→ 直した本文を new.txt に書いて差し替え（下書きのまま）
git add queue/ && git commit -m "オーナーの返事を反映" && git push origin main
```
- 直したものは、直した全文をもう一度見せて GO を待つ（勝手に GO にしない）
- オーナーが話したエピソードや事実は `config/works.md` の該当作品の「エピソード」に追記して一緒にコミットする
- 新しい作品の話が出たら、works.md に項目を追加する（公開してよいかも確認する）
- 返事の最後に「次の投稿は {時刻} の枠です」と 1 行添える（枠: 7:30 / 12:15 / 21:00。GO 済みの古い順に 1 本ずつ）

## やってはいけないこと
- X に直接投稿する、X の API を呼ぶ
- オーナーの GO なしに下書きを `queued` にする
- `config/strategy.md` やコード、ワークフローを勝手に変える（気づいた改善点は報告に書く）
- シークレット（API キー）を表示・変更する
