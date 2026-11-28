// 動画全体の情報と、シーンの並び。シーンのキーは英数字だけで書く（音声のファイル名・確認用のコンポジションの ID に使う）。
// node からも読むので、"@/" の別名と JSX を使わず、相対パスに .ts を付けて読む。
import type { PlanEntry, VideoMeta } from "../../lib/timeline.ts";

export const VIDEO = {
  slug: "sample",
  title: "ハッシュ値で改ざんに気付く",
  subtitle: "ダウンロードしたファイルを確かめる仕組み",
  source: "解説：explainer-video の見本（原稿なし）",
  origin: "（見本のため原稿なし）",
  stages: ["問い", "考え方", "まとめ"],
} as const satisfies VideoMeta;

export const PLAN = [
  {
    key: "title",
    chapter: "",
    title: "表紙",
    parts: "TitleScene",
    visual: "題名・副題・出典",
  },
  {
    key: "agenda",
    chapter: "はじめに",
    title: "この動画の流れ",
    parts: "AgendaScene",
    visual: "3 つの章を上から並べる",
  },
  {
    key: "what",
    chapter: "1｜ハッシュ値とは",
    title: "ファイルから短い値を作る",
    mark: "ハッシュ値とは",
    parts: "Box・LabeledArrow・Chip（自作の図）",
    visual:
      "ファイル → ハッシュ関数 → ハッシュ値。1 文字変えると値が丸ごと変わる",
  },
  {
    key: "traits",
    chapter: "1｜ハッシュ値とは",
    title: "3 つの性質",
    parts: "PointsScene",
    visual: "性質を 1 つずつ積む",
  },
  {
    key: "q1",
    chapter: "2｜考えてみよう",
    title: "問い",
    mark: "考えてみよう",
    stage: "問い",
    parts: "QuestionScene",
    visual: "問いの文 → 問いの種類 → 5 秒のカウントダウン",
  },
  {
    key: "q1think",
    chapter: "2｜考えてみよう",
    title: "考え方の順番",
    stage: "考え方",
    parts: "ThinkScene",
    visual: "手順を積み、落とし穴を朱で示し、答えを緑のカードで出す",
  },
  {
    key: "summary",
    chapter: "まとめ",
    title: "まとめ",
    mark: "まとめ",
    stage: "まとめ",
    parts: "ListScene",
    visual: "要点を 3 行",
  },
  {
    key: "sources",
    chapter: "まとめ",
    title: "参考資料",
    parts: "SourcesScene",
    visual: "参考資料と音声のクレジット",
  },
] as const satisfies readonly PlanEntry[];

export type SceneKey = (typeof PLAN)[number]["key"];
