---
name: finishing-video
description: できあがった解説動画を仕上げる。lint・音声と台本の食い違い・仮のシーンの残りを確かめてから、Remotion で 1920×1080 の MP4 を書き出し、音量を YouTube 向け（-15 LUFS・-1.5 dBTP）にそろえた公開用の MP4 と、チャプターとクレジットの入った概要欄のファイルを作り、書き出したものを確かめる。making-video から呼ばれるほか、「書き出して」「MP4 にして」「公開用に仕上げて」と頼まれたときに使う。
argument-hint: <slug>
allowed-tools: Bash(npm run lint), Bash(npm run storyboard *), Bash(npm run chapters *), Bash(npm run render *), Bash(ffprobe *)
---

# 動画を仕上げる

引数: `$ARGUMENTS`（動画の slug）

プロジェクトのルートで作業する。書き出しは長い（動画 1 分あたり 30 秒〜1 分）ので、確かめてから 1 回で通す。

Remotion 公式のスキルは「利用者がはっきり頼んだときだけ書き出す」としている。このスキルを呼ぶのは、企画のときに「MP4 まで仕上げる」と決めたか、利用者が書き出しを頼んだときだけにする。

## 手順

```txt
- [ ] 1. 書き出す前に確かめる
- [ ] 2. 書き出す
- [ ] 3. 書き出したものを確かめる
- [ ] 4. 記録を更新し、報告する
```

### 1. 書き出す前に確かめる

次がすべて通るまで直す。直せないものがあれば、書き出さずに報告する。

- `npm run lint` が通る
- 仮のシーンが残っていない: `src/videos/<slug>/` の `SCENES` に plan.ts の全キーがある（無いキーは「作成中」の画面で書き出される）
- 音声が台本と合っている: `voice.ts` の `VOICE_SECONDS` のキーとステップの数が、`script.ts` の `SCRIPT` と同じ。違えば `npm run voice -- <slug>` で作り直す（台本を直した後に作り直していない）
- 静止画の点検の記録（`out/review/<slug>/findings.md`）の「直す」の指摘に、すべて扱いが書いてある。記録が無ければ、building-scenes の 4（静止画の点検）を先に行う
- 読みの点検の記録（`out/voice-review-<slug>.md`）があり、指摘に扱いが書いてある
- 絵コンテを作り直し、長さを確かめる（`npm run storyboard -- <slug>`）
- 書き出しのときに字体を Google Fonts から読むので、ネットワークにつながっている

### 2. 書き出す

```bash
mkdir -p out && npm run render -- <slug> > out/render-<slug>.log 2>&1
```

- Bash の run_in_background で動かし、終わりの通知を待つ（10 分を超えることが多い）。待つ間に同じプロジェクトで重い処理を動かさない
- `npm run render` は、書き出し（`out/<slug>.mp4`）→ 音量の仕上げ（`out/<slug>-master.mp4`）→ 概要欄（`out/<slug>-description.txt`）を順に行う
- 失敗したら `out/render-<slug>.log` の最後を読み、原因（読み込めない音声・字体・メモリ）を直してから、もう一度書き出す。並列数を変えるなど細かい指定が要るときは、公式の remotion-render スキルを読み、`npx remotion render` を直接使う

### 3. 書き出したものを確かめる

- 長さと大きさ: `ffprobe -v error -show_entries format=duration:stream=width,height -of default=nw=1 out/<slug>-master.mp4`。1920×1080 で、長さが STORYBOARD.md の長さと 1 秒以内で合う
- 音量: ログの最後の `I:`（統合ラウドネス）が -15.0 LUFS 前後、`Peak:` が -1.5 dBFS 以下
- 画: 動画の途中の 2〜3 か所（章の頭のあたり）をフレームで書き出して見る。字体が化けていない・仮のシーンが無い

  ```bash
  ffmpeg -v error -ss 00:05:00 -i out/<slug>-master.mp4 -frames:v 1 -y out/check-<slug>-1.png
  ```

- 音声の頭: 最初の無音が終わる時刻（`silence_end`）が 0.5〜1.5 秒あたりにある（表紙で題が出そろってから話し始める）。0 秒なら頭が切れている

  ```bash
  ffmpeg -hide_banner -i out/<slug>-master.mp4 -af silencedetect=n=-40dB:d=0.3 -f null - 2>&1 | grep -m1 silence_end
  ```

- 概要欄: `out/<slug>-description.txt` のチャプターが 0:00 から始まり、3 つ以上ある。出典と「VOICEVOX:話者名」が入っている

### 4. 記録を更新し、報告する

- プロジェクトの README.md の動画の表に、この動画の行（題・コンポジション・原稿・長さ）を足す。ほかの会話も同じ表を触ることがあるので、直前に読み直して自分の行だけを足す
- 次を示して終える
  - 公開用の MP4（`out/<slug>-master.mp4`）と概要欄のファイルのパス、長さ、音量
  - チャプターの一覧
  - 公開するときに要ること: 概要欄の「VOICEVOX:話者名」と出典の表記（ファイルに入っている）、話者ごとの利用規約、第三者の著作物の使用条件
