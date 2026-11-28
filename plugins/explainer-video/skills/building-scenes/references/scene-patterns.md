# シーンの書き方

## 目次

- [シーンの形](#シーンの形)
- [型を使う](#型を使う)
- [図を自作する](#図を自作する)
- [原稿の図表を描き直す](#原稿の図表を描き直す)
- [ステップに合わせて動かす](#ステップに合わせて動かす)
- [よくある不具合](#よくある不具合)
- [並行で書く](#並行で書く)

## シーンの形

```tsx
// src/videos/<slug>/scenes.tsx
import type React from "react";
import { useSteps } from "@/lib/anim";
import { CONTENT, SceneFrame } from "@/parts/frame";
import { kit } from "./kit";
import type { SceneKey } from "./plan";

const Addr: React.FC = () => {
  const f = kit.frameOf("addr");          // 見出し・台本・音声・段階
  const { p, between, only } = useSteps(f.steps);
  return (
    <SceneFrame {...f}>
      {/* 図は CONTENT（上 177・下 807・左右 96）の中に、1920×1080 の px で置く */}
    </SceneFrame>
  );
};

export const SCENES: Partial<Record<SceneKey, React.FC>> = { addr: Addr };
```

- シーンのコンポーネントは props を取らない。必要な値は `kit.frameOf()` と `figures/` から読む
- 長い動画は `scenes/` に章ごとのファイル（`scenes/ch1.tsx` が `CH1_SCENES` を export）を置き、`scenes/index.ts` でまとめて `SCENES` にする

## 型を使う

| 型 | 使うところ | 主な props |
| --- | --- | --- |
| `TitleScene` | 表紙 | `kicker`・`title`・`subtitle`・`source` |
| `AgendaScene` | 目次 | `items`（`label`・`title`）・`current` |
| `PointsScene` | 要点を積む | `items`（`step`・`text`・`head`）・`side`（右の図） |
| `QuestionScene` | 問い・考える時間 | `tag`・`question`・`kind`・`kindStep`・`context` |
| `ThinkScene` | 考え方の順番と正答 | `items`（`step`・`label`・`kind`）・`answer`・`answerStep`・`side`・`answerAt` |
| `ListScene` | 汎用ルール・まとめ | `items`（i 行目はステップ i で出る）・`heading`・`tag` |
| `SourcesScene` | 参考資料 | `entries`（`label`・`title`・`meta`）・`footer` |

- 文の props（`question`・`text`・`label`・`items`）は `Rich` の記法で書ける: `{{マーカー}}`・`__下線__`・`!!注意!!`・` ``等幅`` `・`[[a]]`（空欄）
- `side`・`context` は `(api) => ReactNode`。`api` は `useSteps()` の戻り値で、型の中のステップの進みに合わせて図を動かせる

## 図を自作する

使う部品（`@/parts/graphics`・`@/parts/cards`・`@/parts/table`）:

- 箱と矢印: `Box`（`hi` で色の枠と地）・`Arrow`（`progress` で伸びる。`dashed` は例外・応答）・`LabeledArrow`（動詞のラベル）
- 位置: `Place`（`anchor` の点を `x`・`y` に合わせる）
- 文字のかたまり: `Chip`（tone の色のチップ）・`NumTag`（番号）・`ToneCard`（色の枠の囲み）・`Point`・`Note`
- 判定: `Verdict`（✓ ✗ ？）。アイコンは `Glyph`（`@hugeicons/core-free-icons` から読んだアイコンを渡す）
- 原稿: `QuoteCard`（引用。`page` に頁・節）・`CodePanel`（行番号つき。`focus` で行を強調）・`DataTable`（表。`focus`・`show`・`strike`）

組み立て方:

1. 図の中の要素と、その位置（左上起点、左→右・上→下）を決める。対比は同じ行・同じ列にそろえる
2. 座標は定数にまとめる（`const ROW1 = 300`）。同じ種類の要素は同じ大きさ・同じ間隔にする
3. 色は DESIGN.md の「図の色」の意味に合わせる。plan.ts の「決めたこと」に、その動画の色の意味があればそれに従う
4. 図の中の文字は DESIGN.md の「図の中の文字」に従う（名詞句・動詞のラベル・二段構えにしない）

小さい場所（`side` や右半分）に大きな図を置くときは、縮めない（文字が `text-sm` より小さくなる）。要素を減らした配置を、図の部品の props（`variant="compact"` など）で切り替えるか、別の図を描く。

複雑な図（ネットワーク構成図・シーケンス図・状態遷移図）は、`figures/` に部品として書き、表示する要素・強調・経路を props で切り替えられるようにする。シーンごとに図を書き直さず、同じ部品の props を変えて使う。

```tsx
// figures/net.tsx の形の例
<NetworkFig
  show={{ router: 1, fw: p(0), web: p(1) }}       // 要素ごとの出現（0→1）
  hi={{ web: between(1, 3) }}                     // 強調
  flows={[{ path: ["internet", "fw", "web"], p: p(2, 0.2, 1.2), tone: "blue" }]}
/>
```

## 原稿の図表を描き直す

- 原稿の図表は画像を貼らず、React で描き直す（文字がつぶれず、ステップに合わせて動かせる）
- 原稿の図の文字（項目名・値）は原文のまま写す。見た目（配置・線・色）は DESIGN.md に合わせて変えてよい
- 描き直したら、出典に「図は動画用に描き直し（一部改変）」と書く（`VIDEO.source`）
- 表は `DataTable`、行番号のあるコードや設定は `CodePanel`、文の引用は `QuoteCard` を使う
- 原稿の画面に収まらない大きな表は、行を絞る（`show`）か、シーンを分ける。文字を `text-sm` より小さくしない

## ステップに合わせて動かす

`useSteps(f.steps)` の戻り値:

- `p(i, delay, dur)`: ステップ i の頭から `delay` 秒後に、`dur` 秒かけて 0→1（既定は 0.5 秒）
- `between(i, j)`: ステップ i で出て、ステップ j で消える（`j` が `null` なら消えない）
- `only(i)`: ステップ i の間だけ 1
- `at(i, delay)`: ステップ i の頭のフレーム（ほかの部品にフレームで渡すとき）
- `index`: 今のステップの番号

決まり:

- ステップ i の字幕が指すものを、ステップ i で動かす。前のステップの要素は残すか薄くし、消すときは `between` で消す
- 図の動きは字幕より少し遅らせる（`delay` 0.1〜0.3 秒）
- 動きは不透明度と小さな移動（12〜24px）にする。`scale` は 0.94→1 程度まで
- 1 つのシーンの中で、同じ場所に別の要素を重ねて入れ替えるときは、前の要素を消しきってから次を出す（半透明の重なりを見せない）

## よくある不具合

静止画の点検で多い指摘。書くときから避ける。

- 薄くした（`dim`）箱が半透明になり、後ろの線が透けて見える → 箱の地は不透明のまま、枠と文字の色だけを薄くする（`mixColor(色, 割合, "var(--card)")`）
- 済んだ項目を `opacity` で薄くして、文字が 4.5:1 を下回る → 文字の色を `text-muted-foreground` に寄せる（DESIGN.md の「色」）
- アイコンやバッジ（✓ ✗）が、ラベルや矢印の先に重なる → 置き場所を要素の外側の角に決め、矢印の終点から 24px 以上離す
- 矢印やラベルが交差する、線が箱の上を通る → 経路を折れ線にするか、要素の並びを変える
- 正答の緑が、答えを明かす前のステップで見える → 緑の要素は正答のステップで出す
- 「拒否」「誤り」を表す要素に、正しさの緑を使う（色の意味の取り違え）→ DESIGN.md の色の意味を見直す
- 長いラベルが箱からはみ出す、字幕の区画に図がはみ出す → 幅を広げるか、文を短くする。`CONTENT.bottom`（807）より下に置かない
- 表の行を消しても罫線が残る → `DataTable` を使う（`border-separate`）
- 見出しの行と段階の表示が重なる → 見出しを短くする（全角 24 字まで）
- `Rich` の下線の中のマーカーが出ない → 下線を分けて書く

## 並行で書く

シーンが多い動画は、章ごとにサブエージェント（Agent ツール）に任せる。

1. 先に自分で書くもの: `figures/data.ts`、共通の図の部品（`figures/*.tsx`）、`scenes/index.ts`（章ごとのファイルを読み込む形）、章ごとの空のファイル（`export const CH1_SCENES = {}`）
2. 章ごとに 1 つのサブエージェントを起動し、同じメッセージの中でまとめて起動する（並行で動く）。渡すもの:
   - 受け持つファイル（`src/videos/<slug>/scenes/ch1.tsx`）と、受け持つシーンのキー
   - 読むもの: DESIGN.md、`plan.ts`・`script.ts`（受け持つシーン）、`figures/`、この scene-patterns.md（`${CLAUDE_SKILL_DIR}/references/scene-patterns.md`）、原稿の該当箇所
   - 変えてはいけないもの: 受け持つファイル以外のすべて（共通の部品・台本・plan.ts）。部品に足りないものがあれば、変えずに報告させる
   - 終わりの条件: `npx tsc --noEmit` と `npx biome check src/videos/<slug>/scenes/ch1.tsx` が通り、受け持つシーンの静止画（`npm run review -- <slug> <キー...>`）を自分で見て、よくある不具合が無いこと
   - 返すもの: 書いたシーン、部品に足りなかったもの、台本を直したい箇所
3. 全部が返ったら、部品に足りなかったものを共通の部品に足し、`npm run lint` を通す
