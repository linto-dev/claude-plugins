# 解説動画

原稿（文書・ノート・資料）から、図と字幕と読み上げで解説する動画を Remotion で作るプロジェクト。動画 1 本が 1 つのコンポジションで、字幕・読み上げ・図の部品・スクリプトはすべての動画で共通に使う。

Claude Code の explainer-video プラグイン（`/explainer-video:making-video`）の雛形から作った。見た目の決まりは [DESIGN.md](DESIGN.md)、Claude Code への指示は [CLAUDE.md](CLAUDE.md) にある。

| 動画 | コンポジション | 原稿 | 長さ |
| --- | --- | --- | --- |
| 見本（ハッシュ値で改ざんに気付く） | `sample` | （なし） | 約 1 分 43 秒 |

絵コンテと台本の一覧は `src/videos/<slug>/STORYBOARD.md`。以下のコマンドの `<slug>` は、動画のコンポジション名に置き換える。

## 要るもの

- Node.js（20.19 以上・22.13 以上・24 以上のどれか）
- Docker（読み上げの VOICEVOX エンジンを動かす）
- ffmpeg（静止画の一覧と音量の仕上げ）
- 書き出しのときのネットワーク（字体を Google Fonts から読む）

## コマンド

```console
npm i --loglevel=error                  # 依存関係
npm run dev                             # Remotion Studio でプレビュー
npm run new-video -- <slug>             # 新しい動画のフォルダを作り、Root.tsx に登録する（見本を写す）
npm run voice -- <slug>                 # 読み上げ（public/voice/<slug>/ と src/videos/<slug>/voice.ts）
npm run storyboard -- <slug>            # 絵コンテ（STORYBOARD.md）を作り直す
npm run review -- <slug> [scene...]     # シーンごとの静止画と一覧（out/review/<slug>/）
npm run render -- <slug>                # 書き出し → 音量の仕上げ → 概要欄（out/）
npm run chapters -- <slug>              # 概要欄のチャプターとクレジットだけを作り直す
npm run check                           # Biome で整形し、直せる lint の指摘を直す
npm run lint                            # Biome・型（tsc）・knip を検査
```

- Studio の `<slug>-scenes` フォルダに、シーンを 1 つずつ確かめるコンポジション（`<slug>-03-what` など）がある
- `npm run render` は `out/<slug>.mp4`（書き出したまま）・`out/<slug>-master.mp4`（公開用。統合ラウドネス -15 LUFS・トゥルーピーク -1.5 dBTP）・`out/<slug>-description.txt`（概要欄）を作る

## 読み上げ（VOICEVOX）

```console
docker run -d --rm --name voicevox-engine -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest
npm run voice -- <slug>
docker stop voicevox-engine
```

- 台本の `say`（省略時は `caption`）を読む。文と設定が前回と同じ音声は作り直さない。台本から消したステップの音声は消える
- 話者・スタイル・話速は `script.ts` の `VOICE`（既定は青山龍星・喜び）。使える話者は、存在しない名前を入れて実行すると一覧が出る
- 読み間違いは `out/voice-kana-<slug>.txt` で確かめ、`script.ts` の `READINGS`（表記 → 読み）・`READING_RULES`（正規表現）か、台本の `say` で直す。どの動画にも効く直しは `scripts/reading.ts`
- `USER_DICT`（エンジンのユーザー辞書）はエンジンの中で共有される。同じエンジンで作るほかの動画と、同じ表記の読みをそろえる。1 語でも変えると全部の音声が作り直しになるので、辞書は最初に決める
- 公開するときは、概要欄に「VOICEVOX:話者名」と書く（`npm run chapters` が入れる）。ソフトの規約（[VOICEVOX 利用規約](https://voicevox.hiroshiba.jp/term/)）に加え、話者ごとの規約（各キャラクターのページ。例: [青山龍星](https://voicevox.hiroshiba.jp/product/aoyama_ryusei/)）も守る

## どこを直すか

| 直したいもの | ファイル |
| --- | --- |
| 字幕と読み上げの文。文の長さと音声から各ステップの長さが決まる | `src/videos/<slug>/script.ts` |
| シーンの並び・章・チャプター・絵コンテの説明 | `src/videos/<slug>/plan.ts` |
| 図の動き・配置 | `src/videos/<slug>/scenes.tsx`（長い動画は `scenes/` に章ごとに分ける） |
| 見出し・字幕・読み上げの枠 | `src/parts/frame.tsx` |
| シーンの型（表紙・目次・要点・問い・考え方・一覧・参考資料） | `src/parts/templates.tsx` |
| 囲み・表・図の部品 | `src/parts/` |
| 読む速さ・余白・切り替えの長さ | `src/lib/timing.ts` |
| 配色（トークン）・文字の段階 | `src/styles/globals.css`（規則は `DESIGN.md`） |

台本を直したら、`voice` → `storyboard` → `review` の順に作り直す。字幕（`caption`）だけを直したときは、`say` があるステップの音声は変わらない。

## 出典と権利

- 原稿に第三者の著作物（書籍・試験問題・論文など）を使うときは、その使用条件に従い、出典と、図を改変したことを動画の冒頭・参考資料のシーン・概要欄に書く（`plan.ts` の `VIDEO.source`）
- 字体は Noto Sans JP と Noto Sans Mono（Google Fonts、SIL Open Font License）
- 部品は shadcn/ui（MIT）、アイコンは Hugeicons の無料版（MIT）、日本語の文節の区切りは BudouX（Apache-2.0）
- Remotion は個人や 3 人までのチームは無料。会社での利用は [Remotion のライセンス](https://www.remotion.dev/docs/license) を確かめる
