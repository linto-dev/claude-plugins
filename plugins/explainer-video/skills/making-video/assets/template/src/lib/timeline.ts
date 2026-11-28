// 動画全体の並び（plan.ts）と台本（script.ts）と音声の長さ（voice.ts）から、シーンの位置と長さを出す。
// 動画本体（src/lib/video.tsx）と scripts/（絵コンテ・チャプター・静止画）が同じ計算を使う。
import type { Script, TimedStep } from "./step.ts";
import { stepStarts, TRANSITION, toFrames } from "./timing.ts";

/** 動画全体の情報（plan.ts の VIDEO） */
export type VideoMeta = {
  /** コンポジションの ID・音声のフォルダ名（英小文字・数字・ハイフン） */
  readonly slug: string;
  readonly title: string;
  readonly subtitle?: string;
  /** 出典の表記。表紙・参考資料のシーン・概要欄に出す */
  readonly source?: string;
  /** 元の原稿のパス（絵コンテに書く） */
  readonly origin?: string;
  /** 右上に出す段階の名前（問題の解説の型などで使う。使わない動画は省略） */
  readonly stages?: readonly string[];
  /** 概要欄に足す行（正答の出どころなど） */
  readonly notes?: readonly string[];
};

/** シーン 1 つぶんの計画（plan.ts の PLAN の 1 行） */
export type PlanEntry = {
  /** シーンのキー（英数字。台本・音声のファイル名・確認用のコンポジションの ID に使う） */
  readonly key: string;
  /** 左上の小見出し（章の名前） */
  readonly chapter: string;
  /** シーンの見出し */
  readonly title: string;
  /** YouTube のチャプター名。付けたシーンが章の頭になり、切り替えの動きも変わる */
  readonly mark?: string;
  /** 右上の段階表示の現在値（VIDEO.stages のどれか） */
  readonly stage?: string;
  /** シーンの最短の秒数（台本の長さより長く見せたいとき） */
  readonly minSeconds?: number;
  /** 絵コンテ: 使う部品 */
  readonly parts?: string;
  /** 絵コンテ: 画面の内容 */
  readonly visual?: string;
};

export type VoiceSeconds = Record<string, readonly (number | null)[]>;

/** 台本に読み上げの長さを足す */
export const withVoice = <K extends string>(
  script: Script<K>,
  voice: VoiceSeconds,
): Record<K, readonly TimedStep[]> =>
  Object.fromEntries(
    (Object.keys(script) as K[]).map((key) => [
      key,
      script[key].map(
        (s, i): TimedStep => ({ ...s, voice: voice[key]?.[i] ?? undefined }),
      ),
    ]),
  ) as unknown as Record<K, readonly TimedStep[]>;

export type TimelineScene<P extends PlanEntry = PlanEntry> = {
  readonly plan: P;
  readonly index: number;
  /** 動画の頭からの開始フレーム（前のシーンとの切り替えの頭） */
  readonly from: number;
  readonly frames: number;
};

export const sceneFrames = (
  plan: PlanEntry,
  steps: readonly TimedStep[],
  fps: number,
) =>
  Math.max(toFrames(plan.minSeconds ?? 0, fps), stepStarts(steps, fps).total);

/** シーンの位置と長さ。total は動画全体のフレーム数（切り替えの重なりを引いた値） */
export const buildTimeline = <P extends PlanEntry>(
  plan: readonly P[],
  steps: Record<string, readonly TimedStep[]>,
  fps: number,
) => {
  const transition = toFrames(TRANSITION, fps);
  let at = 0;
  const scenes: TimelineScene<P>[] = plan.map((p, index) => {
    const s = steps[p.key];
    if (!s) throw new Error(`script.ts に ${p.key} の台本がない`);
    if (index > 0) at -= transition;
    const scene = { plan: p, index, from: at, frames: sceneFrames(p, s, fps) };
    at += scene.frames;
    return scene;
  });
  return { scenes, total: at, transition };
};

/**
 * チャプター（YouTube の概要欄の目次）。最初のシーンと mark を付けたシーンで切る。
 * 最初のチャプターは 0:00 で、名前は最初のシーンの mark（無ければ「はじめに」）
 */
export const chapterMarks = <P extends PlanEntry>(
  timeline: ReturnType<typeof buildTimeline<P>>,
) =>
  timeline.scenes
    .filter((s) => s.index === 0 || s.plan.mark)
    .map((s) => ({
      // 切り替えの途中ではなく、シーンが出きった時点を指す
      frame: s.index === 0 ? 0 : s.from + timeline.transition,
      label: s.plan.mark ?? (s.index === 0 ? "はじめに" : ""),
    }));
