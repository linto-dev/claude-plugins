---
name: making-video
description: 原稿（Markdown の解説・学習ノート・技術記事・社内資料・書籍の要約など）から、図と字幕と VOICEVOX の読み上げで解説する動画を Remotion で作り、公開用の MP4（-15 LUFS）と YouTube の概要欄まで仕上げる入口。プロジェクトを雛形から作り、企画と台本・読み上げ・シーン・仕上げの各工程のスキルを順に呼ぶ。「この文書を動画にして」「解説動画を作りたい」「ノートを Remotion で動画化して」と頼まれたとき、作りかけの解説動画の続きをするときに使う。
argument-hint: <原稿のパス> [プロジェクトの場所]
---

# 解説動画を作る

引数: `$ARGUMENTS`（原稿のパス。プロジェクトの場所を続けて書いてもよい）

原稿を、図と字幕と読み上げで解説する動画にする。動画 1 本が Remotion のコンポジション 1 つで、字幕・読み上げ・図の部品・スクリプトは雛形のプロジェクトに入っている。このスキルは入口で、工程ごとのスキルを順に呼ぶ。

```txt
making-video（このスキル）     プロジェクトを用意し、工程を順に進める
  → planning-video             原稿を読み、形を利用者と決め、計画（plan.ts）と台本（script.ts）を書く
  → narrating-video            読み上げを作り、読みを点検して直す（点検は reviewing-readings）
  → building-scenes            シーンと図を書き、静止画を点検して直す（点検は reviewing-frames）
  → finishing-video            書き出し・音量の仕上げ・概要欄・最後の確かめ
```

利用者への質問と報告は日本語で書く。

## 守ること

- 利用者にしか決められないこと（動画の形・長さ・範囲・どこまで仕上げるか・見た目・話者・出典の扱い）は AskUserQuestion で聞き、不明点が無くなるまでやりとりする。推奨の選択肢を先頭に置き、label の末尾に「（推奨）」を付ける。原稿やコードを読めば分かることは聞かない
- 原稿にない事実（仕様・規格・数値・最新の状況）を足すときや、ライブラリの使い方は、必要に応じて Web Search や context7 で最新の情報を確かめる
- Remotion の書き方は、プロジェクトの DESIGN.md と Remotion 公式のスキル（`.claude/skills/remotion-*`）に従う。DESIGN.md の「Remotion 公式のスキルとの関係」の 2 点だけは公式と違う
- 原稿に第三者の著作物（書籍・試験問題・論文・他人の記事）が含まれるときは、使用条件を確かめ、出典と改変の有無を動画と概要欄に書く。本文を長く写して画面に出さず、要約・描き直しにする
- git のコミットや push は、利用者に頼まれたときだけ行う

## 手順

```txt
- [ ] 1. 状況を確かめる
- [ ] 2. プロジェクトを用意する
- [ ] 3. 企画と台本（planning-video）
- [ ] 4. 読み上げ（narrating-video）
- [ ] 5. シーン（building-scenes）
- [ ] 6. 仕上げ（finishing-video）
- [ ] 7. 報告する
```

### 1. 状況を確かめる

- 引数の原稿を読む。原稿が無ければ、何を動画にしたいかを AskUserQuestion で聞く
- プロジェクトがあるかを確かめる。引数にプロジェクトの場所があればそこ、無ければ今のフォルダと原稿の近くを探す。目印は、`package.json` に `remotion` があり、`scripts/voice.ts` と `DESIGN.md` と `src/videos/` があること
- 道具を確かめる: `node --version`（20.19 以上・22.13 以上・24 以上）、`docker --version`、`ffmpeg -version`。無いものがあれば、入れ方を示して利用者に頼む（Docker が無ければ読み上げを作れない）
- 作りかけの動画の続きなら、`src/videos/<slug>/` を見て、どこまで進んだかを決める。

  | 状態 | 次の工程 |
  | --- | --- |
  | `src/videos/<slug>/` が無い、または plan.ts が写した元（見本）のまま | 3 |
  | 台本はあるが voice.ts が空、または台本と食い違う（キーやステップの数が違う） | 4 |
  | scenes の `SCENES` に plan.ts のキーがそろっていない（足りないシーンは「作成中」の仮のシーンになる） | 5 |
  | シーンはそろったが `out/review/<slug>/findings.md` に未対応の「直す」がある | 5 の点検の続き |
  | シーンはそろったが `out/<slug>-master.mp4` が無い | 6 |

  plan.ts の冒頭のコメント「決めたこと」に、前の会話で利用者と決めたことがある。読んで、聞き直さない

### 2. プロジェクトを用意する

プロジェクトがあればこの手順は飛ばす。

- 置き場所を AskUserQuestion で聞く（推奨: 原稿のフォルダの隣に `動画/` を作る。シリーズの動画は 1 つのプロジェクトにまとめる）
- 雛形からプロジェクトを作る。依存関係と Remotion 公式のスキル（`.agents/skills/` に入り、`.claude/skills/` からリンクされる）も入る（数分かかる）

  ```bash
  node ${CLAUDE_SKILL_DIR}/scripts/create-project.mjs <プロジェクトの場所>
  ```

  公式のスキルを入れるときに「(project directory not found)」が何度も出るが、ほかのエージェント向けの場所が無いという知らせで、Claude Code 向けには入っている。最後に「Done!」が出ればよい

- 作ったプロジェクトの README.md・DESIGN.md・CLAUDE.md を読む。以後のコマンドはプロジェクトのルートで実行する
- プロジェクトが作業フォルダの外なら、ファイルを書くたびに許可を求められる。止まらずに続け、7 の報告で、次からはプロジェクトのフォルダで Claude Code を開くよう伝える
- Studio を開く（Remotion 公式の remotion-best-practices の「Open the preview」）。`npm run dev` を run_in_background で動かし、表示された URL を利用者に伝える。利用者は作業の途中の動画をいつでも見られる

### 3. 企画と台本

Skill ツールで `explainer-video:planning-video` を呼ぶ。引数は原稿のパスとプロジェクトの場所。動画の形・長さ・範囲・どこまで仕上げるかを利用者と決め、`src/videos/<slug>/` の plan.ts と script.ts を書き、利用者の了承を得るところまで進む。

原稿が長く、シリーズ（複数の動画）に分けると決まったときは、シリーズ全体の目次と約束（plan.ts の決めたこと）を先に決め、1 本ずつ 4〜6 を回す。2 本目からは 3 の聞き取りを短くする（決めたことを引き継ぐ）。

### 4. 読み上げ

Skill ツールで `explainer-video:narrating-video` を呼ぶ。引数は slug。

### 5. シーン

Skill ツールで `explainer-video:building-scenes` を呼ぶ。引数は slug。

### 6. 仕上げ

3 で「MP4 まで仕上げる」と決めたときだけ、Skill ツールで `explainer-video:finishing-video` を呼ぶ。引数は slug。決めていなければ、ここで AskUserQuestion で聞く（推奨: 公開用の MP4 と概要欄まで）。

### 7. 報告する

次を示して終える。

- できたもの: 公開用の MP4・概要欄のファイル・絵コンテのパス、コンポジションの名前、長さ（見積もりと違えば理由）
- 確かめたこと: lint、静止画の点検、読みの点検、音量。直したものと、直さずに残したもの（理由つき）
- 公開するときに要ること: 概要欄の「VOICEVOX:話者名」、出典の表記
- コミットしていないこと（頼まれていれば、したこと）
