---
name: building-scenes
description: 解説動画のシーンと図を Remotion（React・Tailwind CSS v4・shadcn/ui・Hugeicons）で書く。計画（plan.ts）と台本（script.ts）に沿って、雛形のシーンの型と部品を使い、原稿の図表を描き直し、字幕のステップに合わせて動かす。長い動画は章ごとにサブエージェントへ並行で任せる。書いた後に静止画を書き出し、書いた本人ではない立場で点検させて（reviewing-frames）直す。making-video から呼ばれるほか、「シーンを書いて」「図を描き直して」「この場面の見た目を直して」と頼まれたときに使う。
argument-hint: <slug> [シーンのキー...]
allowed-tools: Bash(npm run review *), Bash(npm run lint), Bash(npx tsc --noEmit), Bash(npx biome check *), Bash(npm run storyboard *)
---

# シーンと図を書く

引数: `$ARGUMENTS`（動画の slug。続けてシーンのキーを書くと、そのシーンだけを書く・直す）

`src/videos/<slug>/scenes.tsx`（長い動画は `scenes/` に章ごとのファイル）に、plan.ts の各シーンを書く。プロジェクトのルートで作業する。

## 守ること

- 書く前に、プロジェクトの DESIGN.md を読む。配色・文字の段階・区画・図の規則・動きはそれに従う
- Remotion の API と書き方は、公式のスキル（`remotion-markup`・`remotion-docs` など、`.claude/skills/remotion-*`）で確かめる。公式と違うのは DESIGN.md の「Remotion 公式のスキルとの関係」の 2 点だけ（台本から作る部分を Studio の編集用の構造にしない、文字は解説動画向けの段階）
- 尺は台本と音声から決まる。シーンの中で尺を数字で決めない（動きの位置は `useSteps()` の `p(i, 秒, 秒)` などでステップに合わせる）
- 字幕・読み上げ・原稿の引用は変えない。シーンを書いていて台本を直したくなったら、直す箇所と理由を控え、5 の報告で伝える（台本を直すと音声の作り直しが要る）
- `src/parts/`・`src/lib/`・`src/components/ui/` は全動画の共通の部品。変えるときは、ほかの動画の見た目が変わらないかを確かめる

## 手順

```txt
- [ ] 1. 計画と台本を読む
- [ ] 2. 共通の土台を書く
- [ ] 3. シーンを書く（長い動画は章ごとに並行）
- [ ] 4. 静止画を点検させて直す（reviewing-frames）
- [ ] 5. 報告する
```

### 1. 計画と台本を読む

- `src/videos/<slug>/plan.ts`（冒頭の「決めたこと」・各シーンの `parts`・`visual`）、`script.ts`、`STORYBOARD.md` を読む
- 原稿の図表を描き直すシーンは、原稿の該当箇所を読む（画像だけの原稿は、画像を見て内容を書き起こす）
- `voice.ts` が空なら、まだ音声が無い。シーンは書けるが、尺は字幕の長さだけの見積もりになる（音声を作った後に静止画を撮り直す）
- [references/scene-patterns.md](references/scene-patterns.md) を読む（型の使い方・図の組み立て方・並行で書くときの分け方）

### 2. 共通の土台を書く

複数のシーンで使うものを、シーンより先に書く。

- 原稿の図表のデータ（本文・表の行・図の要素）: `src/videos/<slug>/figures/data.ts`
- その動画の図の部品（構成図・シーケンス図・表の描き直し）: `src/videos/<slug>/figures/*.tsx`
- 書いたら `npx tsc --noEmit` を通し、1 つのシーンで使って静止画で見た目を確かめる（`npm run review -- <slug> <キー>`）

### 3. シーンを書く

- 型（`@/parts/templates`）に収まるシーンは型を使い、収まらないシーンは `SceneFrame` の中に図を書く（見本の `src/videos/sample/scenes.tsx`）
- 各シーンは `kit.frameOf("<キー>")` を枠に渡す。動きは `useSteps(frame.steps)` の `p`・`between`・`only` でステップに合わせる
- まだ書いていないシーンは `SCENES` に入れなければ、仮のシーン（「作成中」）が出る。書けた順に足してよい
- シーンが 20 を超える動画は、章ごとにサブエージェント（Agent ツール）に任せて並行で書く。分け方と渡すものは scene-patterns.md の「並行で書く」
- 書いたら検査する。指摘が出なくなるまで直す

  ```bash
  npx biome check --write src/videos/<slug>
  npm run lint
  ```

### 4. 静止画を点検させて直す

- 静止画を書き出す（全シーン。シーンが多いと数分かかる）。3 で直した後や音声を作り直した後は、必ず撮り直してから点検を呼ぶ

  ```bash
  npm run review -- <slug>
  ```

- Skill ツールで `explainer-video:reviewing-frames` を呼ぶ。引数は slug だけにし、自分の見立ては添えない
- 返ってきた指摘を `out/review/<slug>/findings.md` にそのまま書き、直したら各行の末尾に扱い（直した・直さない理由）を書き足す。仕上げ（finishing-video）と、続きをする別の会話がこれを読む
- 返ってきた指摘を、「直す」から順に直す。共通の部品の不具合は部品で直し、シーンの配置の不具合はシーンで直す。直したシーンだけ静止画を撮り直して自分で確かめる（`npm run review -- <slug> <キー...>`）
- 点検を呼び直すのは、「直す」の指摘が 10 を超えたときだけ（1 回まで）。呼ぶ前に、直したシーンを撮り直しておく（点検は `out/review/` の静止画を見る）。2 回目は直したシーンのキーを引数に足す
- 「できれば」の指摘は、直すか、直さない理由を控える

### 5. 報告する

- 書いたシーンの数と、共通の部品に足したもの・変えたもの
- 点検の指摘と、それぞれの扱い（直した・直さない理由）
- 台本を直したくなった箇所（あれば。直すなら narrating-video で音声を作り直す）
- `npm run lint` の結果
