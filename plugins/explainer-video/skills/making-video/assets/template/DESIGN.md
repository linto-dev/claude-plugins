# 動画のデザインの規則

動画の見た目の決まり。部品は shadcn/ui（Vega・Base UI）、配色は Neutral のトークン、アイコンは Hugeicons を使う。シーンや部品を足すときは、先にこの文書を読む。

## 目次

- [Remotion 公式のスキルとの関係](#remotion-公式のスキルとの関係)
- [画面の区画](#画面の区画)
- [className と style の分担](#classname-と-style-の分担)
- [部品](#部品)
- [色](#色)
- [文字](#文字)
- [余白・角丸・影](#余白角丸影)
- [図](#図)
- [動き](#動き)
- [見た目を差し替える](#見た目を差し替える)
- [つまずきやすい所](#つまずきやすい所)

## Remotion 公式のスキルとの関係

Remotion の書き方は、公式の Agent Skills（`npx remotion skills add` で `.claude/skills/` に入る `remotion-*`）に従う。公式から外れるのは次の 2 つだけ。

1. 台本と読み上げから尺や中身を作る部分（シーンの並び・ステップの尺・字幕・読み上げ）は、Studio で手で編集するための構造（`Interactive`・`Track`・JSX に直に書いた尺）にしない。公式の remotion-interactivity の「外部のデータから作る部分はプログラムのままでよい」に当たる。尺を Studio で動かしても、台本を直して音声を作り直すと消えるので、直すときは台本（`script.ts`）を直す。
2. 文字の大きさは、この文書の「文字」の段階に従う。公式の目安（幅 1080px の画面で見出し 84px・本文 44px）は短い紹介動画向けで、ラベルの多い図解には入らない。

ほかは公式どおりにする。主なもの:

- コンポジションは 1920×1080・30fps。尺は `calculateMetadata` で返す（`src/lib/video.tsx`）
- シーンは `TransitionSeries` でつなぐ。切り替えの重なりは尺の計算に入っている
- 動きは `useCurrentFrame()` と `interpolate()`（`extrapolateLeft`・`extrapolateRight` を `clamp`）で付け、`Easing.bezier()` で緩急を付ける。CSS の `transition`・`animation`、Tailwind の `animate-*`・`transition-*` は使わない
- 秒からフレームへの換算は `useVideoConfig()` の `fps` で行う（`useSteps()` の `p(i, 秒, 秒)` が換算する）
- `transform` より `scale`・`translate`・`rotate` のプロパティを使う
- 音声は `@remotion/media` の `<Audio>`、画像は `<Img>`、`public/` のファイルは `staticFile()` で参照する（先頭に `/` を付けない）
- 乱数は `Math.random()` ではなく `random(seed)` を使う
- 背景画像（`background-image: url(...)`）で画像を読まない（書き出しで読み込みを待てない）。マーカーの `linear-gradient` は画像ではないのでよい
- 字体は `@remotion/google-fonts` で読む（`src/lib/fonts.ts`）

公式のスキルに無い表現（地図・3D・動画の素材・キャプションの文字起こしなど）を足すときは、公式のスキルを読んでから書く。

## 画面の区画

座標は 1920×1080 の px で書く。

| 区画 | 位置 | 中身 |
| --- | --- | --- |
| 見出し | 上 54・左右 96 | 章の名前（`text-lg`）とシーンの見出し（`text-3xl`）。段階があれば右上 |
| 図（`CONTENT`） | 上 177・下 807・左右 96 | 図・カード・表 |
| 字幕 | 上 840・左右 108 | 字幕（`text-3xl`、長いときは `text-2xl`）。2 行に収める |

- 左右 96px・上下 54px は、テレビのタイトルセーフ（画面の 5%）。大事な文字はこの内側に置く
- 図は `CONTENT` からはみ出さない。字幕の区画に図を置かない

## className と style の分担

| 書く場所 | 書くもの |
| --- | --- |
| `className`（Tailwind） | 色・文字（大きさ・太さ・字体・行の高さ）・枠線・角丸・余白・並べ方（flex・grid・gap）・`absolute` など、見た目の決まりごと |
| `style` | 画面の座標と寸法（`left`・`top`・`width`・`height`）と、フレームで変わる値（`opacity`・`translate`・`scale`・進み具合で伸びる幅・色の混ぜ具合） |

- トークンの代わりに Tailwind の任意値（`text-[19px]`・`bg-[#2563EB]`・`left-[130px]`）を使わない。任意値を使ってよいのは、周りの文字に比例する寸法（`min-w-[3.2em]` など `em` の値）だけ。使うときは `biome.json` の `allowedClasses` に足す
- 同じ見た目を 2 か所以上で使うなら、`src/parts/` の部品にする。見た目の違いは `cva` の variant か、完全なクラス名を並べた表（`src/lib/palette.ts`）で表す
- クラス名を文字列の連結で作らない（`` `bg-${tone}` `` は Tailwind が拾えない）
- クラスの結合は `cn()`（`src/lib/utils.ts`）を使う
- 任意値・Tailwind の既定の色（`bg-red-500` など）・連結で作ったクラス名・クラスの並び順は、`npm run lint`（Biome）が検査する。並び順は `npm run check` で直る

## 部品

画面の部品は、まず `src/components/ui/`（shadcn/ui）を使う。`src/parts/` の部品は、それを組み合わせて作っている。

| 部品 | 場所 | 使うところ |
| --- | --- | --- |
| `SceneFrame`・`CONTENT` | `parts/frame.tsx` | すべてのシーンの枠（見出し・字幕・読み上げ） |
| `TitleScene`・`AgendaScene`・`PointsScene`・`QuestionScene`・`ThinkScene`・`ListScene`・`SourcesScene` | `parts/templates.tsx` | シーンの型 |
| `Rich`・`Mark`・`Blank` | `parts/rich.tsx` | 本文の記法（マーカー・下線・注意の語・等幅・空欄） |
| `QuoteCard`・`PageTag`・`CodePanel`・`Point`・`Note`・`AnswerCard`・`ThinkTimer` | `parts/cards.tsx` | 引用・コード・要点・説明・正答・考える時間 |
| `DataTable` | `parts/table.tsx` | 原稿の表の描き直し |
| `Box`・`Arrow`・`LabeledArrow`・`Place`・`Chip`・`NumTag`・`ToneCard`・`Verdict`・`Glyph` | `parts/graphics.tsx` | 図の箱・矢印・位置指定・チップ・判定・アイコン |

新しい見た目が要るときは、`npx shadcn add <name>` で部品を足し、`src/components/ui/` の各ファイルの頭に書いた「動画向けに変えた点」を同じように当てる（`transition`・`hover:`・`focus-visible:` を外す、`font-medium` を `font-bold` にする）。アイコンは Hugeicons（`@hugeicons/core-free-icons` を `<Glyph icon={…} />` で使う）。

## 色

### トークン

| 役割 | トークン | クラスの例 |
| --- | --- | --- |
| 本文・見出し | `--foreground` / `--background` | `text-foreground`・`bg-background` |
| 章の名前・補足・注記・頁番号 | `--muted-foreground` | `text-muted-foreground` |
| 段階・考える時間・一覧の枠・手順の今の行 | `--primary` | `bg-primary text-primary-foreground`・`border-primary` |
| マーカー（蛍光ペン）・解説の要点（emphasis） | `--marker`（動画用に足した淡い黄色） | `bg-marker text-marker-foreground` |
| 淡い地（表の見出し行） | `--muted` | `bg-muted` |
| 装飾の線（区切り・カードの枠） | `--border`・`ring-foreground/10` | `border-border` |

- `--border` は装飾の線だけに使い、情報を担う線（矢印・図の枠）には使わない
- 文字は大きさに関係なく、背景とのコントラスト比を 4.5:1 以上にする（`--muted-foreground` は Neutral の既定より濃くしてある）
- 済んだ項目や強調していない行を薄く見せるときは、`opacity` ではなく文字の色を `text-muted-foreground` にする（フレームで変えるなら `mixColor("var(--muted-foreground)", 割合, "var(--foreground)")`）。`opacity` で薄くした文字は 4.5:1 を下回る。出てくる途中（0→1）の `opacity` は構わない

### 図の色（Okabe-Ito）

図の中で区別するものにだけ色を付け、1 色に 1 つの意味を持たせる。既定の意味は次のとおり。動画ごとに変えるなら、絵コンテ（plan.ts の冒頭のコメント）に書き、その動画の中では変えない。

| 色 | 既定の意味 |
| --- | --- |
| `blue`（青） | 注目させる要素・ふつうの流れ・取り出した値 |
| `vermillion`（朱） | 注意・危険・誤り・攻撃者・改ざん |
| `green`（緑） | 正答・正しい・安全・うまくいく状態 |
| `gray`・`ink` | 補足・前提・軸・原稿の図の線 |

各色に 4 つの値がある（`src/styles/globals.css`）。

| 値 | 使うところ | クラスの例 |
| --- | --- | --- |
| 線（`--figure-blue`） | 矢印・枠線（白地に 3:1 以上） | `border-figure-blue`・`stroke-figure-blue` |
| 文字（`--figure-blue-text`） | 淡色の上の文字（4.5:1 以上） | `text-figure-blue-text` |
| 淡色（`--figure-blue-tint`） | 区別の地 | `bg-figure-blue-tint` |
| 濃色（`--figure-blue-solid`） | その図で一番言いたい 1 か所の地。文字は白 | `bg-figure-blue-solid text-white` |

- 基本は青と朱の 2 色。緑は「正答・正しい」の意味で使うときだけ足す。正答の緑は、答えを明かす前のステップで出さない
- 朱の線の色は白文字に 4.5:1 届かないので、文字を載せる地には `--figure-vermillion-solid` を使う
- 色だけで意味を伝えない。色で分けたものには、ラベルやアイコン（`Verdict` の ✓ ✗）も添える
- フレームの進み具合で色を混ぜるときは `mixColor()`（`src/lib/palette.ts`）を使う

## 文字

- 字体は Noto Sans JP（`font-sans`）。コード・URL・16 進数は Noto Sans Mono（`font-mono`）
- 太さは 400（`font-normal`）と 700（`font-bold`）だけ
- 大きさは次の段階から選ぶ（`src/styles/globals.css` の `@theme` で、Tailwind の段階を 1920×1080 の動画向けに置き換えてある）。`text-sm` より小さくしない

  | クラス | 大きさ | 主な使いどころ |
  | --- | --- | --- |
  | `text-sm` | 21px | 頁番号・図の注記（補足に限る） |
  | `text-base` | 24px | 図のラベル・図の題・コード・表の注 |
  | `text-lg` | 27px | 章の名前・表・小さい図の本文 |
  | `text-xl` | 30px | 図の本文・手順・要点 |
  | `text-2xl` | 36px | 引用・問いの文・長い字幕・一覧 |
  | `text-3xl` | 45px | シーンの見出し・字幕 |
  | `text-4xl` | 54px | 正答 |
  | `text-5xl`・`text-6xl` | 72px・90px | 表紙の題 |

- 行の高さは、日本語の本文が `leading-relaxed`、見出しが `leading-snug`
- 日本語は文節の境目で折り返す。BudouX で境目に `<wbr>` を入れ、`break-phrase` で `<wbr>`・空白・句読点の後でだけ改行させる（`src/lib/phrase.tsx` の `Phrase`。`Rich` は自動で使う）。CSS の `word-break: auto-phrase` は使わない（Chrome の版で区切り方が変わる）
- 半角の語と和文の間の空白は改行しない空白にする（`keepTogether()`。「SHA-256 なら」を泣き別れにしない）

## 余白・角丸・影

- 余白は Tailwind の段階（1 段 = 6px）。偶数の段階（`gap-2`・`p-4`）を基本にし、部品の内側の細かい調整だけ奇数（`gap-1`・`py-3`）を使う
- 角丸は、表・コード・小さな箱が `rounded-md`、囲み・カードが `rounded-xl`（`Card` の既定）、チップが `rounded-4xl`（`Badge` の既定）
- 影は付けない。囲みは `Card` の淡い枠か、意味のある色の枠線（`ring-3`・`border-3`）で区切る
- 片側だけに色の線を付ける装飾（左だけ太い線）は使わない

## 図

- 起点は左上。左→右、上→下に読ませる
- 矢印は一方向にし、何をする関係かを動詞で書く（「送信する」「計算する」）
- 線の種類の意味を固定する: 実線 = ふつうの流れ、破線 = 例外・任意の流れ・応答、破線の囲み = 範囲・前提
- 線どうしを交差させない。線や部品を、ほかの部品やラベルの上に通さない
- 同じ種類の要素は同じ大きさ・同じ間隔にそろえる。対比では、対応する要素を同じ行・同じ列に置く
- 入れ子の囲みは 2 重まで
- シーケンス図は、時間を上から下に流し、応答を破線にする
- 原稿の図表を描き直したときは、出典に「一部改変」と書く（表紙・参考資料のシーン・概要欄）

### 図の中の文字

図のラベル・矢印・注記・チップに当てる。字幕・読み上げと、原稿からの引用（`QuoteCard`・`CodePanel` の本文、原稿の図表の再現）は原文のまま変えない。

- 読点で前後に分けた二段構え、対比（〜ではなく〜）、決め台詞（〜だけ・〜こそ）、疑問・感嘆・コロン・ダッシュを使わない。列挙は「・」で書く
- 図の題は「対象＋観点」の名詞句にする（「送信先のホスト名」）。結論や評価は図に書かず、字幕に任せる
- ラベルは原稿と字幕の語をそのまま使う

## 動き

- 出てくる動きは、不透明度と小さな移動（12〜24px）の組み合わせにする。大きく飛び込む動きや回転は使わない
- 1 つのステップで動かすのは、字幕が指しているものだけにする。前のステップの要素は、そのまま残すか、文字の色を muted に寄せる（「色」の薄く見せるとき）。消すときは `between()`・`only()` で消しきる
- 字幕が先に出て、図はそれに少し遅れて（0.1〜0.3 秒）動く
- 章の頭は `slide`、ほかのシーンの切り替えは `fade`（`src/lib/video.tsx`）

## 見た目を差し替える

- 配色だけを変えるとき: `src/styles/globals.css` の `:root` の値を変える。ブランドの色は `--primary` に入れ、白文字とのコントラスト比 4.5:1 以上を確かめる。マーカーの色は `--marker`
- shadcn/ui のスタイル（Vega・Nova・Maia など）を変えるとき: `components.json` の `style` を変え、`npx shadcn add <部品> --overwrite` で部品を取り込み直し、「動画向けに変えた点」を当て直す
- 字体を変えるとき: `src/lib/fonts.ts` の読み込みと、`globals.css` の `--font-sans`・`--font-mono` を変える
- 図の色（`--figure-*`）は、色覚の多様性を考えた Okabe-Ito のまま使う。変えるなら、線・文字・淡色・濃色のコントラストを測り直す

## つまずきやすい所

- `ItemGroup` は `w-full` を持つので、`absolute` で `left`・`right` を指定しても幅が画面の外まで伸びる。`width` を指定する
- `Table` は `border-collapse` なので、行を `opacity` で消しても罫線が残る。行を出し入れする表は `DataTable`（`border-separate`）を使う
- `Card` は `overflow-hidden` を持つ。枠の外にはみ出す子（チップ・番号）があるときは `overflow-visible` を足す
- Tailwind の preflight で `box-sizing: border-box` になる。幅に余白と枠線が含まれるので、文字が収まらないときは幅を広げる
- `Rich` の `__…__`（下線）の中に `{{…}}`（マーカー）は書けない。下線を分けて書く
