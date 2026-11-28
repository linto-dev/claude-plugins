// 動きの補助。シーンはステップ（字幕 1 つぶん）の進行に合わせて動く。
// 秒で書き、フレームへの換算は useVideoConfig() の fps で行う（Remotion の約束）。
import { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { TimedStep } from "./step";
import { stepStarts } from "./timing";

export const EASE_OUT = Easing.bezier(0.22, 1, 0.36, 1);
export const EASE_IN_OUT = Easing.bezier(0.65, 0, 0.35, 1);

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** 0→1 の進み具合。from フレームから dur フレームかけて進む */
export const ramp = (
  frame: number,
  from: number,
  dur: number,
  easing = EASE_OUT,
) =>
  interpolate(frame, [from, from + Math.max(1, dur)], [0, 1], {
    ...CLAMP,
    easing,
  });

export const mix = (a: number, b: number, t: number) => a + (b - a) * t;

export type StepApi = ReturnType<typeof useSteps>;

/**
 * シーン内のステップの進行を扱う。秒の引数はすべてステップの頭からの秒数。
 * - p(i, delay, dur): ステップ i の頭から delay 秒後に、dur 秒かけて 0→1
 * - between(i, j): ステップ i で出て、ステップ j で消える（j が null なら消えない）
 * - only(i): ステップ i の間だけ 1
 * - at(i, delay): ステップ i の頭（から delay 秒後）のフレーム
 */
export const useSteps = (steps: readonly TimedStep[]) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { starts, total } = useMemo(() => stepStarts(steps, fps), [steps, fps]);
  let index = 0;
  for (let i = 0; i < starts.length; i++) if (frame >= starts[i]) index = i;
  const at = (i: number, delay = 0) =>
    (starts[i] ?? total) + Math.round(delay * fps);
  const p = (i: number, delay = 0, dur = 0.5, easing = EASE_OUT) =>
    ramp(frame, at(i, delay), dur * fps, easing);
  const between = (i: number, j: number | null, delay = 0) =>
    p(i, delay, 0.47) * (j === null ? 1 : 1 - p(j, 0, 0.4));
  const only = (i: number, delay = 0) => between(i, i + 1, delay);
  return { frame, fps, index, starts, total, p, at, between, only };
};
