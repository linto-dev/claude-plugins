// ステップとシーンの長さの計算。動画本体（src/lib/video.tsx）と scripts/（絵コンテ・チャプター・静止画）が同じ式を使う。
import type { TimedStep } from "./step.ts";

// 字幕を読む速さ: 日本語 1 文字 = 1 単位、半角 = 0.5 単位。1 単位あたり 0.133 秒（約 7.5 文字/秒）。
// 読み上げがあるステップは声の長さを主に使い、字幕を読む時間は少し短く見積もる。
const SEC_PER_UNIT = 0.133;
const SEC_PER_UNIT_WITH_VOICE = 0.107;
/** 字幕が出るまでの間と、読み終えてからの余白 */
const LEAD = 0.47;
const TAIL = 0.73;
/** 1 ステップの最短。これより短いと図の動きを目で追えない */
const MIN_STEP = 3;
/** ステップの頭から話し始めるまでの間（字幕が出きってから話す） */
export const VOICE_DELAY = 0.27;
/** 話し終えてから次のステップまでの間 */
const VOICE_TAIL = 0.47;
/** シーンの切り替えで前後のシーンが重なる秒数 */
export const TRANSITION = 0.6;
/** シーンの最後のステップに足す間。切り替え（TRANSITION）で声が次のシーンに重ならないようにする */
const SCENE_END_PAD = 0.47;

export const readingUnits = (text: string) =>
  Array.from(text).reduce(
    (sum, ch) => sum + ((ch.codePointAt(0) ?? 0) < 0x2000 ? 0.5 : 1),
    0,
  );

/** ステップの秒数。last はシーンの最後のステップ */
export const stepSeconds = (step: TimedStep, last = false) => {
  const per = step.voice ? SEC_PER_UNIT_WITH_VOICE : SEC_PER_UNIT;
  const reading =
    LEAD + readingUnits(step.caption) * per + TAIL + (step.extra ?? 0);
  const voice = step.voice
    ? VOICE_DELAY + step.voice + VOICE_TAIL + (last ? SCENE_END_PAD : 0)
    : 0;
  return Math.max(MIN_STEP, reading, voice) + (step.hold ?? 0);
};

export const stepFrames = (step: TimedStep, fps: number, last = false) =>
  Math.ceil(stepSeconds(step, last) * fps);

/** 各ステップの開始フレーム（シーンの頭から）と、シーン全体のフレーム数 */
export const stepStarts = (steps: readonly TimedStep[], fps: number) => {
  const starts: number[] = [];
  let at = 0;
  steps.forEach((step, i) => {
    starts.push(at);
    at += stepFrames(step, fps, i === steps.length - 1);
  });
  return { starts, total: at };
};

export const toFrames = (seconds: number, fps: number) =>
  Math.round(seconds * fps);
