---
name: narrating-video
description: 解説動画の台本（script.ts）から VOICEVOX で読み上げ音声を作り、読みを書いた本人ではない立場で点検させて（reviewing-readings）、読み違いを置き換え表・ユーザー辞書・say で直し、音声と絵コンテを作り直す。making-video から呼ばれるほか、「読み上げを作って」「読みを直して」「台本を直したので音声を作り直して」と頼まれたときに使う。
argument-hint: <slug>
allowed-tools: Bash(npm run voice *), Bash(npm run storyboard *), Bash(docker ps *), Bash(curl -s http://127.0.0.1:50021/*)
---

# 読み上げを作る

引数: `$ARGUMENTS`（動画の slug）

台本の各ステップを VOICEVOX で音声にし（`public/voice/<slug>/<シーンのキー>-<ステップの番号>.wav`。番号は 0 から数える）、各音声の長さを `src/videos/<slug>/voice.ts` に書く。シーンの尺はこの長さで決まる。プロジェクトのルートで作業する。

## 守ること

- 読みの直しは、まず置き換え（`READINGS`・`READING_RULES`）で行う。`USER_DICT`（エンジンのユーザー辞書）を変えると全部の音声が作り直しになるので、辞書は最初に決め、後から足すのは置き換えで直せない語だけにする
- ユーザー辞書はエンジンの中で共有される。同じエンジンで作るほかの動画（同じプロジェクトのほかの slug、別の会話）と、同じ表記の読みとアクセントをそろえる。ほかの動画の `script.ts` の `USER_DICT` を読んでから足す
- エンジンのコンテナを止めるのは、この会話で起動したときだけにする（ほかの会話が使っていることがある）
- `voice.ts` は手で直さない

## 手順

```txt
- [ ] 1. エンジンを用意する
- [ ] 2. 読み違えやすい語を先に直す
- [ ] 3. 音声を作る
- [ ] 4. 読みを点検させる（reviewing-readings）
- [ ] 5. 直して作り直す
- [ ] 6. 絵コンテを作り直し、報告する
```

### 1. エンジンを用意する

```bash
docker ps --format '{{.Names}}' | grep -x voicevox-engine || docker run -d --rm --name voicevox-engine -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest
curl -s http://127.0.0.1:50021/version
```

- 版が返るまで数秒〜数十秒かかる。返らなければ数秒おいて確かめ直す
- 既に動いていたか、この会話で起動したかを控える（6 で止めるかどうかに使う）

### 2. 読み違えやすい語を先に直す

[references/reading-fixes.md](references/reading-fixes.md) を読み、台本（`script.ts`）に出てくる語のうち、崩れると分かっているものを先に直す。

- 崩れると分かっている英字の語（ハイフンを含む略語・辞書が要る略語）を `USER_DICT` か `READINGS` に足す
- IP アドレス・長い数字・記号のひらがなの並びは `say` で書き直す
- 迷う語は直さずに 3 に進み、4 の点検で崩れたものだけを直す

### 3. 音声を作る

```bash
npm run voice -- <slug>
```

- 1 件に 1〜3 秒かかる。ステップが 200 を超えるなど 10 分を超えそうなときは、Bash の run_in_background で動かし、終わりの通知を待つ
- 話者が見つからないと、使える話者とスタイルの一覧が出る。`script.ts` の `VOICE` を直す
- 終わると、読みの確認用のファイル `out/voice-kana-<slug>.txt` ができる

### 4. 読みを点検させる

Skill ツールで `explainer-video:reviewing-readings` を呼ぶ。引数は slug だけにし、自分の見立ては添えない（点検する人が先入観なしに読むため）。返ってくるのは、読み違えた語の表。

返ってきた表を `out/voice-review-<slug>.md` にそのまま書く。5 で直したら、各行の末尾に扱い（直した方法か、直さない理由）を書き足す。続きをする別の会話がこれを読む。

### 5. 直して作り直す

- 指摘を 1 つずつ、次のどれかで直す（直し方の選び方は reading-fixes.md）
  - その動画だけの語: `script.ts` の `READINGS`（表記 → 読み）・`READING_RULES`（正規表現）
  - 文ごとに違う読み: そのステップの `say`
  - どの動画にも効く書き方（記号・単位など）: `scripts/reading.ts`
  - 置き換えで直らない語: `USER_DICT`（全部の音声が作り直しになる）
- 作り直す（直した文の音声だけが作り直される）

  ```bash
  npm run voice -- <slug>
  ```

- 直した語だけを `out/voice-kana-<slug>.txt` で確かめる。点検を呼び直すのは、直した語が 20 を超えたときか、`USER_DICT` を変えたときだけ（1 回まで）
- 読みは正しいが句の切れ方が少し不自然な所（「始める側か」のような切れ目）は、直さずに報告に残してよい

### 6. 絵コンテを作り直し、報告する

```bash
npm run storyboard -- <slug>
```

- この会話でエンジンを起動したなら止める（`docker stop voicevox-engine`）。ほかの会話が使っていそうなら、止めずに報告で伝える
- 次を示して終える
  - 音声の件数と、読み上げの合計・動画の長さ（STORYBOARD.md）。企画のときの見積もりと比べる
  - 直した読み（語と直し方）と、直さずに残したもの
  - 足した `USER_DICT`（ほかの動画と共有されることを添える）
