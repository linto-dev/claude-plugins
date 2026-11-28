// 動画を組み立てる。各動画の kit.ts が createKit で台本と音声を束ね、index.tsx が buildVideo でシーンを並べる。
// 尺は台本と読み上げの長さから計算する（Studio で手で動かす構造にはしない。DESIGN.md の「Remotion 公式のスキルとの関係」）。
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import type React from "react";
import { Fragment } from "react";
import {
  AbsoluteFill,
  type CalculateMetadataFunction,
  Composition,
  Folder,
} from "remotion";
import { type Frame, PlaceholderScene } from "@/parts/templates";
import { FPS, HEIGHT, WIDTH } from "./config";
import type { Script, TimedStep } from "./step";
import {
  buildTimeline,
  type PlanEntry,
  type VideoMeta,
  type VoiceSeconds,
  withVoice,
} from "./timeline";

/** 台本・音声・計画を束ね、シーンの枠に渡す値（frameOf）を作る */
export const createKit = <const P extends readonly PlanEntry[]>(o: {
  meta: VideoMeta;
  plan: P;
  script: Script<P[number]["key"]>;
  voiceSeconds: VoiceSeconds;
}) => {
  type K = P[number]["key"];
  const steps = withVoice(o.script, o.voiceSeconds);
  /** SceneFrame やシーンの型に渡す値（見出し・台本・音声・段階） */
  const frameOf = (key: K): Frame => {
    const p = o.plan.find((x) => x.key === key);
    if (!p) throw new Error(`plan.ts に ${key} がない`);
    return {
      chapter: p.chapter,
      title: p.title,
      steps: steps[key],
      voice: `voice/${o.meta.slug}/${key}`,
      stage:
        o.meta.stages && p.stage
          ? { list: o.meta.stages, current: p.stage }
          : undefined,
    };
  };
  return { ...o, steps, frameOf };
};

/** buildVideo が使う kit の部分 */
type KitLike<K extends string> = {
  meta: VideoMeta;
  plan: readonly (PlanEntry & { key: K })[];
  steps: Record<K, readonly TimedStep[]>;
  frameOf: (key: K) => Frame;
};

export type SceneEntry = {
  key: string;
  name: string;
  frames: number;
  Component: React.FC;
};

/** シーンを TransitionSeries で並べた動画と、その長さを返す calculateMetadata */
export const buildVideo = <K extends string>(
  kit: KitLike<K>,
  scenes: Partial<Record<K, React.FC>>,
) => {
  const timeline = buildTimeline(
    kit.plan,
    kit.steps as Record<string, readonly TimedStep[]>,
    FPS,
  );
  const list: (SceneEntry & { chapterStart: boolean })[] = timeline.scenes.map(
    (s) => {
      const key = s.plan.key as K;
      return {
        key,
        name: `${String(s.index + 1).padStart(2, "0")} ${s.plan.title}`,
        frames: s.frames,
        chapterStart: Boolean(s.plan.mark),
        Component:
          scenes[key] ??
          (() => <PlaceholderScene frame={kit.frameOf(key)} sceneKey={key} />),
      };
    },
  );

  // biome-ignore lint/correctness/noComponentHookFactories: buildVideo は各動画の index.tsx の読み込み時に 1 回だけ呼ぶ（描画のたびには作らない）
  const Video: React.FC = () => (
    <AbsoluteFill className="bg-background">
      <TransitionSeries>
        {list.map((s, i) => (
          <Fragment key={s.key}>
            {i > 0 ? (
              <TransitionSeries.Transition
                presentation={
                  s.chapterStart ? slide({ direction: "from-right" }) : fade()
                }
                timing={linearTiming({ durationInFrames: timeline.transition })}
              />
            ) : null}
            <TransitionSeries.Sequence
              name={s.name}
              durationInFrames={s.frames}
            >
              <s.Component />
            </TransitionSeries.Sequence>
          </Fragment>
        ))}
      </TransitionSeries>
    </AbsoluteFill>
  );

  // 尺は台本と音声から決まる（静的な値ではないので calculateMetadata で返す）
  const calculateMetadata: CalculateMetadataFunction<
    Record<string, unknown>
  > = () => ({
    durationInFrames: timeline.total,
    fps: FPS,
    width: WIDTH,
    height: HEIGHT,
  });

  return { id: kit.meta.slug, Video, calculateMetadata, scenes: list };
};

type BuiltVideo = ReturnType<typeof buildVideo>;

/** シーンを 1 つずつ確かめるコンポジション（ID は <slug>-<番号>-<キー>）を Folder にまとめる */
export const sceneFolder = (video: Pick<BuiltVideo, "id" | "scenes">) => (
  <Folder name={`${video.id}-scenes`}>
    {video.scenes.map((s, i) => (
      <Composition
        key={s.key}
        id={`${video.id}-${String(i + 1).padStart(2, "0")}-${s.key}`}
        component={s.Component}
        durationInFrames={s.frames}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    ))}
  </Folder>
);
