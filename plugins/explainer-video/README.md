# explainer-video

原稿（Markdown の解説・学習ノート・技術記事・社内資料・書籍の要約など）から、図と字幕と読み上げで解説する動画を、Claude Code と [Remotion](https://www.remotion.dev/) で作るプラグインです。企画と台本、VOICEVOX の読み上げ、シーンと図、書いた本人ではない点検、書き出しと音量の仕上げ、YouTube の概要欄までを、工程ごとのスキルで進めます。動画は日本語です。

雛形のプロジェクトが付いています。字幕と読み上げの長さから各場面の尺を決める仕組み、全シーン共通の枠（見出し・字幕・読み上げ）、シーンの型（表紙・目次・要点・問い・考え方・まとめ・参考資料）、静止画の一覧・絵コンテ・チャプター・音量の仕上げのスクリプトが入っています。見た目は shadcn/ui の Vega（Base UI）・Neutral、アイコンは Hugeicons、Tailwind CSS v4 です。

## 流れ

```txt
/explainer-video:making-video <原稿のパス>    入口。プロジェクトを雛形から作り、次の工程を順に呼ぶ
  planning-video       原稿を読み、動画の形・長さ・範囲を利用者と決め、計画（plan.ts）と台本（script.ts）を書く
  narrating-video      VOICEVOX で読み上げを作り、読みを点検して直す
    reviewing-readings   読みの点検（会話を引き継がないフォーク）
  building-scenes      シーンと図を書き、静止画を点検して直す（長い動画は章ごとに並行）
    reviewing-frames     静止画の点検（会話を引き継がないフォーク）
  finishing-video      書き出し → 公開用の MP4（-15 LUFS）→ 概要欄（チャプターとクレジット）
```

| スキル | 呼び方 | 役目 |
| --- | --- | --- |
| `making-video` | `/explainer-video:making-video <原稿>` | 全体の入口。作りかけの動画の続きもここから |
| `planning-video` | 入口が呼ぶ・`/explainer-video:planning-video <原稿>` | 企画と台本 |
| `narrating-video` | 入口が呼ぶ・`/explainer-video:narrating-video <slug>` | 読み上げと読みの直し |
| `reviewing-readings` | 読み上げのスキルが呼ぶ | 読みの点検 |
| `building-scenes` | 入口が呼ぶ・`/explainer-video:building-scenes <slug>` | シーンと図 |
| `reviewing-frames` | シーンのスキルが呼ぶ | 静止画の点検 |
| `finishing-video` | 入口が呼ぶ・`/explainer-video:finishing-video <slug>` | 書き出しと仕上げ |

動画の形（1 本かシリーズか、網羅か要点か、どこまで仕上げるか、話者）は、企画の工程で AskUserQuestion で聞いて決め、`plan.ts` の冒頭に「決めたこと」として残します。別の会話で続きをするときも、それを読んで聞き直しません。

## Remotion 公式のスキルとの関係

雛形から作ったプロジェクトには、Remotion 公式の Agent Skills（[remotion-dev/skills](https://github.com/remotion-dev/skills)。`npx remotion skills add`）も入れます。Remotion の書き方は公式に従い（1920×1080、`calculateMetadata`、`TransitionSeries`、`interpolate` と `Easing`、`@remotion/media`、`@remotion/google-fonts`）、次の 2 点だけを変えています（プロジェクトの `DESIGN.md` に理由と一緒に書いてあります）。

1. 台本と読み上げから尺や中身を作る部分は、Studio で手で編集するための構造（`Interactive`・`Track`）にしない（公式の「外部のデータから作る部分はプログラムのままでよい」に当たる）
2. 文字の大きさは、ラベルの多い図解に合わせた解説動画向けの段階にする

## 要るもの

- Claude Code（スキルの `context: fork` を使う）
- Node.js 20.19 以上・22.13 以上・24 以上のどれか
- Docker（VOICEVOX エンジン `voicevox/voicevox_engine` を動かす）
- ffmpeg
- 書き出しのときのネットワーク（字体を Google Fonts から読む）

## 入れ方

Claude Code の会話で次を打ちます。

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install explainer-video@linto-dev
```

## 使い方

1. 原稿のあるフォルダ（か、動画のプロジェクトを置きたいフォルダ）で Claude Code を開く
2. `/explainer-video:making-video <原稿のパス>` を打つ。プロジェクトが無ければ、置き場所を聞かれ、雛形から作られる（`npm install` と公式のスキルの導入で数分かかる）
3. 動画の形を聞かれるので答える。台本ができたら、絵コンテ（`src/videos/<slug>/STORYBOARD.md`）を読んで了承する
4. 読み上げ・シーン・点検・書き出しが進む。途中の動画は Remotion Studio（`npm run dev`）でいつでも見られる
5. 公開用の `out/<slug>-master.mp4` と、概要欄に貼る `out/<slug>-description.txt` ができる

雛形だけが欲しいときは、プラグインの場所で `node skills/making-video/scripts/create-project.mjs <作る場所>` を実行します。

## 権利

- 読み上げの音声を公開するときは、概要欄に「VOICEVOX:話者名」を書きます（概要欄のファイルに入ります）。[VOICEVOX の利用規約](https://voicevox.hiroshiba.jp/term/)と、話者ごとの規約に従ってください
- 原稿に第三者の著作物を使うときは、その使用条件に従い、出典と図の改変を動画と概要欄に書きます（企画の工程で `plan.ts` に書きます）
- Remotion は個人や 3 人までのチームは無料です。会社での利用は [Remotion のライセンス](https://www.remotion.dev/docs/license) を確かめてください
- 雛形の部品は shadcn/ui（MIT）、アイコンは Hugeicons の無料版（MIT）、日本語の文節の区切りは BudouX（Apache-2.0）、字体は Noto Sans JP・Noto Sans Mono（SIL Open Font License）です

## English

A Claude Code plugin that turns a Japanese source document (notes, articles, study guides, internal docs) into a narrated explainer video with Remotion: planning and script, VOICEVOX narration with a reading check, scenes and redrawn diagrams with an independent still-frame review, and rendering with loudness normalization (-15 LUFS) and YouTube chapters. It ships a project template (shadcn/ui Vega on Base UI, Neutral theme, Hugeicons, Tailwind CSS v4) and follows Remotion's official Agent Skills, except that script-driven timing is kept programmatic and the type scale is tuned for dense diagrams. Start with `/explainer-video:making-video <source>`.
