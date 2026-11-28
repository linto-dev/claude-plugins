// 全シーンに共通の枠: 背景・左上の見出し・右上の段階・下の字幕・読み上げ。
// 座標は 1920×1080。図は CONTENT の中に置く（下は字幕の区画）。
import { Audio } from "@remotion/media";
import type React from "react";
import { useMemo } from "react";
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { EASE_OUT, ramp, useSteps } from "@/lib/anim";
import { Phrase } from "@/lib/phrase";
import type { TimedStep } from "@/lib/step";
import { stepStarts, toFrames, VOICE_DELAY } from "@/lib/timing";
import { cn } from "@/lib/utils";

/** 図を置く区画（左右 96px・上は見出しの下、下は字幕の上） */
export const CONTENT = {
  top: 177,
  bottom: 807,
  left: 96,
  right: 1824,
} as const;
const CAPTION_TOP = 840;

export type SceneFrameProps = {
  chapter: string;
  title: string;
  steps: readonly TimedStep[];
  /** 読み上げ音声の接頭辞（public/<voice>-<n>.wav） */
  voice?: string;
  /** 段階（右上に出す）。list は VIDEO.stages */
  stage?: { list: readonly string[]; current: string };
  children: React.ReactNode;
};

export const SceneFrame: React.FC<SceneFrameProps> = ({
  chapter,
  title,
  steps,
  voice,
  stage,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const head = ramp(frame, 0, 0.6 * fps);
  return (
    <AbsoluteFill lang="ja" className="bg-background font-sans text-foreground">
      <div
        className="absolute"
        style={{
          left: CONTENT.left,
          top: 54,
          right: stage?.list.length ? 630 : CONTENT.left,
          opacity: head,
          translate: `0 ${(1 - head) * 15}px`,
        }}
      >
        <div className="text-lg font-bold text-muted-foreground">{chapter}</div>
        <div className="text-3xl font-bold whitespace-nowrap">{title}</div>
      </div>
      {stage?.list.length ? (
        <StageBar list={stage.list} current={stage.current} opacity={head} />
      ) : null}
      <AbsoluteFill>{children}</AbsoluteFill>
      <Caption steps={steps} />
      {voice ? <Narration voice={voice} steps={steps} /> : null}
    </AbsoluteFill>
  );
};

/** 右上: 段階のどこにいるか（今の段階だけ名前を出す） */
const StageBar: React.FC<{
  list: readonly string[];
  current: string;
  opacity: number;
}> = ({ list, current, opacity }) => {
  const idx = list.indexOf(current);
  return (
    <div
      className="absolute flex gap-3"
      style={{ right: CONTENT.left, top: 60, opacity }}
    >
      {list.map((s, i) => {
        const on = i === idx;
        const done = i < idx;
        return (
          <Badge
            key={s}
            size="sm"
            variant={on ? "default" : done ? "secondary" : "outline"}
            className={cn(!on && !done && "text-muted-foreground")}
          >
            <span className="tabular-nums">{i + 1}</span>
            {on ? s : null}
          </Badge>
        );
      })}
    </div>
  );
};

/** ステップごとの読み上げ。ステップの頭から VOICE_DELAY 秒後（＋ delay 秒）に鳴らす */
export const Narration: React.FC<{
  voice: string;
  steps: readonly TimedStep[];
  /** 全体を遅らせる秒数（表紙で題名が出そろってから読むときなど） */
  delay?: number;
}> = ({ voice, steps, delay = 0 }) => {
  const { fps } = useVideoConfig();
  const { starts } = useMemo(() => stepStarts(steps, fps), [steps, fps]);
  return (
    <>
      {steps.map((s, i) =>
        s.voice ? (
          <Sequence
            key={i}
            name={`読み上げ ${i + 1}`}
            from={starts[i] + toFrames(VOICE_DELAY + delay, fps)}
            durationInFrames={Math.ceil(s.voice * fps) + 2}
            layout="none"
          >
            <Audio src={staticFile(`${voice}-${i}.wav`)} />
          </Sequence>
        ) : null,
      )}
    </>
  );
};

// 字幕の本文。URL は途中で折り返さない。
const URL_RE = /(https?:\/\/[A-Za-z0-9.\-_/~%?=#:…]+)/;
const CaptionText: React.FC<{ text: string }> = ({ text }) => (
  <>
    {text.split(URL_RE).map((part, i) =>
      i % 2 === 1 ? (
        <span key={i} className="whitespace-nowrap">
          {part}
        </span>
      ) : (
        <Phrase key={i} text={part} />
      ),
    )}
  </>
);

/** 長い字幕は 1 段小さくする（2〜3 行に収める） */
const captionSize = (t: string) =>
  Array.from(t).length > 80 ? "text-2xl" : "text-3xl";

/** 下部の字幕。ステップが変わると前の文が消え、次の文が少し遅れて出る */
const Caption: React.FC<{ steps: readonly TimedStep[] }> = ({ steps }) => {
  const { frame, fps, index, starts } = useSteps(steps);
  const start = starts[index];
  const prev = index > 0 ? steps[index - 1].caption : "";
  const now = steps[index].caption;
  const outP = interpolate(frame, [start, start + 0.23 * fps], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const inP = ramp(
    frame,
    start + (index === 0 ? 0.2 : 0.17) * fps,
    0.33 * fps,
    EASE_OUT,
  );
  const box = "absolute break-phrase leading-normal";
  const place = { left: 108, right: 108, top: CAPTION_TOP };
  return (
    <>
      <Separator
        className="absolute"
        style={{ left: 108, right: 108, top: CAPTION_TOP - 21, width: "auto" }}
      />
      {prev && outP > 0 ? (
        <div
          className={cn(box, captionSize(prev))}
          style={{ ...place, opacity: outP }}
        >
          <CaptionText text={prev} />
        </div>
      ) : null}
      {now ? (
        <div
          className={cn(box, captionSize(now))}
          style={{ ...place, opacity: inP, translate: `0 ${(1 - inP) * 12}px` }}
        >
          <CaptionText text={now} />
        </div>
      ) : null}
    </>
  );
};
