# 毎朝のルーティン（Claude Code が投稿案を作る手順）

このリポジトリの持ち主から、次の作業を毎朝自動で行う許可をもらっている。
**このリポジトリの `main` に直接コミットして push してよい**（投稿は GitHub Actions が `main` の
`queue/posts.json` から出すため）。X への投稿そのものはしない（投稿は `.github/workflows/post.yml` の仕事）。

## 0. 準備
```bash
pip install -q -r requirements.txt
sudo apt-get install -y -qq fonts-noto-cjk >/dev/null 2>&1 || apt-get install -y -qq fonts-noto-cjk >/dev/null 2>&1
git pull --ff-only origin main
```

## 1. 今日作る本数を決める
- `queue/posts.json` の `status == "queued"` を数える。**目標は 6 本**（1 日 3 本 × 2 日分）
- 6 本以上あれば、何もせず終了してよい（終了時の報告だけする）
- 足りない本数を `needed` とする

## 2. 読むもの
- `config/strategy.md`（運用方針。キャラクター・語り口・投稿の型・禁止事項。**必ず全部読む**）
- `queue/posts.json` の直近 40 本（同じネタ・言い回しを避けるため）
- `logs/` にある分析結果があれば、それも（伸びた型を増やす）

## 3. 調べる
- WebSearch で、今日のネタを探す。優先順位:
  1. 今買える定番品の比較・予算別の選び方に使える事実（メーカー公式の仕様・価格）
  2. 近いセール（プライム感謝祭など）の日程・条件
  3. 新製品・話題（「で、それ買いなの？」まで言えるもの）
- 使う事実は **WebFetch で元のページを開いて確かめる**。製品名・数字・価格・日付は出典どおりに
- 同じメーカー・同じイベントは、投稿待ち全体で 2 本まで

## 4. 書く
- `needed` の 1.5 倍くらいの候補を、スクラッチパッドの `drafts.json` に書く（形は `src/add_posts.py` の説明を参照）
- 運用方針の「語り口」「キャラクター」「書き直しの例」を守る。書いたら声に出して読んで、
  ニュース記事や AI の文章に聞こえないかを確かめる
- 図解（image）を付けるなら `verdict`（買い / 待ち / 見送り）もなるべく付ける
- 画像の spec の項目: `kind`（table / checklist / number）, `title`, `highlight`, `verdict`,
  `headers`, `rows`, `recommend_col`, `items`, `big_text`, `caption`, `conclusion`, `note`

## 5. 見直す（ここを手を抜かない）
- 各候補の事実を出典ともう一度照らし合わせる。確かめられないものは削るか、その候補を捨てる
- 体験談の作り話（「使ってみた」「うちの〜」）がないか
- 「最大」「約」「想定」などの条件を、本文でも画像でも省いていないか
- 違う種類の製品を同じ表で比べていないか

## 6. 画像を確かめる
```bash
python src/add_posts.py drafts.json --preview <スクラッチパッド>/preview
```
- 出てきた画像を **1 枚ずつ Read で開いて目で見る**。文字のはみ出し、重なり、読みにくさ、中身の間違いを直す
- NG と出た候補は直すか外す

## 7. 追加して push
- 良いものから `needed` 本だけを残した `drafts.json` で:
```bash
python src/add_posts.py drafts.json
git add queue/ && git commit -m "投稿案を追加（Claude Code）" && git push origin main
```
- push が弾かれたら `git pull --rebase origin main` してからもう一度 push

## 8. 終わりに
- 追加した投稿の冒頭 1 行と判定を、短く報告する
- うまくいかなかったこと（調べられなかった、push できなかった等）があれば、それも書く

## やってはいけないこと
- X に直接投稿する、X の API を呼ぶ
- `config/strategy.md` やコード、ワークフローを勝手に変える（気づいた改善点は報告に書く）
- シークレット（API キー）を表示・変更する
