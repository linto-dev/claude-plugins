// シーンの型。どれも frame（SceneFrame に渡す見出し・台本・音声。kit.frameOf(key) の戻り値）を受け取る。
// 型に収まらないシーンは、SceneFrame の中に図を直接書く（scenes.tsx の例を参照）。
import type React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Card } from "@/components/ui/card";
import { Item, ItemContent, ItemGroup, ItemMedia } from "@/components/ui/item";
import { ramp, type StepApi, useSteps } from "@/lib/anim";
import { stepFrames } from "@/lib/timing";
import { cn } from "@/lib/utils";
import { AnswerCard, PageTag, ThinkTimer } from "./cards";
import { CONTENT, Narration, SceneFrame, type SceneFrameProps } from "./frame";
import { Chip, NumTag } from "./graphics";
import { Rich } from "./rich";

export type Frame = Omit<SceneFrameProps, "children">;

// ───────── 表紙 ─────────
// 見出しと字幕の枠を使わない。題名が出そろってから読み上げる。
export const TitleScene: React.FC<{
  frame: Frame;
  kicker?: string;
  title: string;
  subtitle?: string;
  source?: string;
}> = ({ frame, kicker, title, subtitle, source }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const show = (at: number, dur = 0.6) => ramp(f, at * fps, dur * fps);
  const k = show(0.13);
  const t = show(0.33, 0.73);
  const s = show(0.8, 0.67);
  const src = show(1.33, 0.67);
  return (
    <div lang="ja" className="absolute inset-0 bg-background font-sans">
      <div className="absolute inset-0 flex flex-col items-center justify-center px-24 text-center">
        {kicker ? (
          <div
            className="text-2xl font-bold text-muted-foreground"
            style={{ opacity: k, translate: `0 ${(1 - k) * 12}px` }}
          >
            {kicker}
          </div>
        ) : null}
        <div
          className="mt-6 text-6xl leading-snug font-bold break-phrase"
          style={{ opacity: t, translate: `0 ${(1 - t) * 24}px` }}
        >
          <Rich text={title} />
        </div>
        {subtitle ? (
          <div
            className="mt-6 text-4xl leading-snug break-phrase text-muted-foreground"
            style={{ opacity: s, translate: `0 ${(1 - s) * 15}px` }}
          >
            <Rich text={subtitle} />
          </div>
        ) : null}
      </div>
      {source ? (
        <div
          className="absolute inset-x-0 text-center text-lg text-muted-foreground"
          style={{ bottom: 78, opacity: src }}
        >
          {source}
        </div>
      ) : null}
      {frame.voice ? (
        <Narration voice={frame.voice} steps={frame.steps} delay={0.6} />
      ) : null}
    </div>
  );
};

// ───────── 目次 ─────────
// items を上から並べ、current の章を強調する（current を省略すると全部を同じ濃さで出す）。
export const AgendaScene: React.FC<{
  frame: Frame;
  items: readonly { label: string; title: string }[];
  current?: number;
}> = ({ frame, items, current }) => {
  const { p } = useSteps(frame.steps);
  return (
    <SceneFrame {...frame}>
      <ItemGroup
        className="absolute gap-3"
        style={{ left: 240, right: 240, top: CONTENT.top + 12 }}
      >
        {items.map((it, i) => {
          const on = current === undefined || current === i;
          const show = p(0, 0.2 + i * 0.13, 0.47);
          return (
            <Item
              key={it.title}
              variant="outline"
              className={cn(
                "flex-nowrap gap-6 px-8 py-4",
                current === i && "border-3 border-primary",
                !on && "text-muted-foreground",
              )}
              style={{
                opacity: show,
                translate: `${(1 - show) * -15}px 0`,
              }}
            >
              <ItemMedia className="w-[4.5em] justify-start text-xl font-bold text-muted-foreground">
                {it.label}
              </ItemMedia>
              <ItemContent className="text-2xl font-bold break-phrase">
                <div>
                  <Rich text={it.title} />
                </div>
              </ItemContent>
            </Item>
          );
        })}
      </ItemGroup>
    </SceneFrame>
  );
};

// ───────── 要点を積む ─────────
// items をステップ（step）ごとに 1 つずつ積む。side に図を渡すと左右に分ける（左に要点、右に図）。
export type ListItem = { step: number; text: string; head?: string };

export const PointsScene: React.FC<{
  frame: Frame;
  items: readonly ListItem[];
  side?: (api: StepApi) => React.ReactNode;
  listWidth?: number;
}> = ({ frame, items, side, listWidth = side ? 780 : 1440 }) => {
  const api = useSteps(frame.steps);
  const { p, index } = api;
  return (
    <SceneFrame {...frame}>
      <ItemGroup
        className="absolute gap-4"
        style={{
          left: side ? CONTENT.left : (1920 - listWidth) / 2,
          top: CONTENT.top + 12,
          width: listWidth,
        }}
      >
        {items.map((it, i) => {
          const show = p(it.step, 0.13, 0.47);
          const current =
            index >= it.step &&
            (items[i + 1]?.step ?? Number.POSITIVE_INFINITY) > index;
          return (
            <Item
              key={i}
              variant="outline"
              className={cn(
                "flex-nowrap items-start gap-4 px-6 py-4",
                current && "border-3 border-primary",
                !current && "text-muted-foreground",
              )}
              style={{
                opacity: show,
                translate: `0 ${(1 - show) * 15}px`,
              }}
            >
              <ItemMedia className="mt-1">
                <NumTag size="base">{i + 1}</NumTag>
              </ItemMedia>
              <ItemContent className="gap-1">
                {it.head ? (
                  <div className="text-base font-bold text-muted-foreground">
                    {it.head}
                  </div>
                ) : null}
                <div className="text-2xl leading-normal font-bold break-phrase">
                  <Rich text={it.text} />
                </div>
              </ItemContent>
            </Item>
          );
        })}
      </ItemGroup>
      {side ? side(api) : null}
    </SceneFrame>
  );
};

// ───────── 問い ─────────
// 問いの文 → 補足（context。原稿の該当箇所など）→ 問いの種類（kind）→ 考える時間（最後のステップの hold 秒）。
export const QuestionScene: React.FC<{
  frame: Frame;
  tag: string;
  question: string;
  kind?: string;
  kindLabel?: string;
  kindStep?: number;
  context?: (api: StepApi) => React.ReactNode;
}> = ({
  frame,
  tag,
  question,
  kind,
  kindLabel = "問いの種類",
  kindStep = 0,
  context,
}) => {
  const api = useSteps(frame.steps);
  const { p, at, fps } = api;
  const last = frame.steps.length - 1;
  const hold = Math.round((frame.steps[last].hold ?? 0) * fps);
  const timerFrom = at(last) + stepFrames(frame.steps[last], fps, true) - hold;
  return (
    <SceneFrame {...frame}>
      <div
        className="absolute"
        style={{
          left: CONTENT.left,
          right: CONTENT.left,
          top: CONTENT.top + 3,
          opacity: p(0, 0.13, 0.53),
        }}
      >
        <Card className="flex-row items-start gap-6 px-9 py-6">
          <NumTag size="xl">{tag}</NumTag>
          <div className="text-2xl leading-normal font-bold break-phrase">
            <Rich text={question} />
          </div>
        </Card>
      </div>
      {context ? context(api) : null}
      {kind ? (
        <div
          className="absolute inline-flex items-center gap-3 text-xl font-bold whitespace-nowrap"
          style={{
            left: CONTENT.left,
            bottom: 1080 - CONTENT.bottom + 3,
            opacity: p(kindStep, 0.2, 0.47),
          }}
        >
          <span className="text-muted-foreground">{kindLabel}</span>
          <Chip tone="emphasis">{kind}</Chip>
        </div>
      ) : null}
      {hold > 0 ? (
        <div
          className="absolute"
          style={{ right: CONTENT.left + 15, top: 450 }}
        >
          <ThinkTimer frame={api.frame} fps={fps} from={timerFrom} dur={hold} />
        </div>
      ) : null}
    </SceneFrame>
  );
};

// ───────── 考え方の順番 ─────────
// 左に手順を 1 つずつ積み、右に図（side）。answerStep で正答・結論のカードを出す。
export type ThinkItem = {
  step: number;
  label: string;
  /** step: ふつうの手順、pitfall: 落とし穴（朱）、note: 補足 */
  kind?: "step" | "pitfall" | "note";
};

export const ThinkScene: React.FC<{
  frame: Frame;
  items: readonly ThinkItem[];
  answer: React.ReactNode;
  answerStep: number;
  answerLabel?: string;
  answerSize?: React.ComponentProps<typeof AnswerCard>["size"];
  side?: (api: StepApi) => React.ReactNode;
  /** 正答カードの中心。省略で右下 */
  answerAt?: { x: number; y: number };
  listWidth?: number;
  /** 左の手順を最大いくつまで並べるか。超えたら古いものから畳む */
  maxVisible?: number;
}> = ({
  frame,
  items,
  answer,
  answerStep,
  answerLabel,
  answerSize = "3xl",
  side,
  answerAt = { x: 1350, y: 705 },
  listWidth = 705,
  maxVisible = 7,
}) => {
  const api = useSteps(frame.steps);
  const { p, index } = api;
  const started = items.filter((it) => it.step <= index).length;
  const firstShown = Math.max(0, started - maxVisible);
  let n = 0;
  return (
    <SceneFrame {...frame}>
      <ItemGroup
        className="absolute gap-4"
        style={{ left: CONTENT.left, top: CONTENT.top, width: listWidth }}
      >
        {items.map((it, i) => {
          const show = p(it.step, 0.13, 0.47);
          const current =
            index >= it.step &&
            (items[i + 1]?.step ?? Number.POSITIVE_INFINITY) > index;
          const kind = it.kind ?? "step";
          if (kind === "step") n++;
          if (i < firstShown) return null;
          const mark =
            kind === "pitfall" ? "!" : kind === "note" ? "＋" : String(n);
          const pitfall = kind === "pitfall";
          return (
            <Item
              key={i}
              size="xs"
              className="flex-nowrap items-start gap-3 p-0"
              style={{
                opacity: show,
                translate: `${(1 - show) * -15}px 0`,
              }}
            >
              <ItemMedia
                className={cn(
                  "mt-0.5 size-11 rounded-full border-3 text-sm font-bold",
                  current
                    ? pitfall
                      ? "border-figure-vermillion-solid bg-figure-vermillion-solid text-white"
                      : "border-primary bg-primary text-primary-foreground"
                    : "border-figure-gray bg-card text-muted-foreground",
                )}
              >
                {mark}
              </ItemMedia>
              <ItemContent
                className={cn(
                  "text-xl leading-snug break-phrase",
                  current ? "font-bold" : "font-normal text-muted-foreground",
                  pitfall && current && "text-figure-vermillion-text",
                )}
              >
                <div>
                  <Rich text={it.label} />
                </div>
              </ItemContent>
            </Item>
          );
        })}
      </ItemGroup>
      {side ? side(api) : null}
      <div
        className="absolute w-max"
        style={{ left: answerAt.x, top: answerAt.y, translate: "-50% -50%" }}
      >
        <AnswerCard
          p={p(answerStep, 0.2, 0.53)}
          size={answerSize}
          label={answerLabel}
        >
          {answer}
        </AnswerCard>
      </div>
    </SceneFrame>
  );
};

// ───────── 一覧（汎用ルール・まとめ） ─────────
// 枠の付いた行を、ステップごとに 1 行ずつ出す（i 行目はステップ i で出る）。
export const ListScene: React.FC<{
  frame: Frame;
  heading?: string;
  tag?: string;
  items: readonly string[];
}> = ({ frame, heading, tag, items }) => {
  const { p } = useSteps(frame.steps);
  return (
    <SceneFrame {...frame}>
      <div
        className="absolute flex flex-col gap-6"
        style={{ left: 210, right: 210, top: CONTENT.top + 48 }}
      >
        {heading || tag ? (
          <div
            className="flex items-center gap-6"
            style={{ opacity: p(0, 0, 0.47) }}
          >
            {tag ? <NumTag size="lg">{tag}</NumTag> : null}
            {heading ? (
              <div className="text-2xl font-bold">{heading}</div>
            ) : null}
          </div>
        ) : null}
        <ItemGroup className="gap-6">
          {items.map((r, i) => {
            const s = p(Math.min(i, frame.steps.length - 1), 0.2, 0.53);
            return (
              <Item
                key={i}
                variant="outline"
                className="flex-nowrap border-3 border-primary bg-card px-9 py-6"
                style={{ opacity: s, translate: `0 ${(1 - s) * 18}px` }}
              >
                <ItemContent className="text-2xl leading-normal font-bold break-phrase">
                  <div>
                    <Rich text={r} />
                  </div>
                </ItemContent>
              </Item>
            );
          })}
        </ItemGroup>
      </div>
    </SceneFrame>
  );
};

// ───────── 出典と参考資料 ─────────
export const SourcesScene: React.FC<{
  frame: Frame;
  entries: readonly { label: string; title: string; meta?: string }[];
  footer?: readonly string[];
}> = ({ frame, entries, footer = [] }) => {
  const { p } = useSteps(frame.steps);
  return (
    <SceneFrame {...frame}>
      <div
        className="absolute"
        style={{ left: CONTENT.left, right: CONTENT.left, top: CONTENT.top }}
      >
        {entries.map((r, i) => (
          <div
            key={`${r.label}-${r.title}`}
            className={cn(
              "flex items-baseline gap-6 py-2",
              i > 0 && "border-t border-border",
            )}
            style={{ opacity: p(0, 0.2 + i * 0.13, 0.47) }}
          >
            <div className="w-[7em] shrink-0 text-base font-bold text-muted-foreground">
              {r.label}
            </div>
            <div className="flex-1 text-xl font-bold break-phrase">
              {r.title}
            </div>
            {r.meta ? <PageTag>{r.meta}</PageTag> : null}
          </div>
        ))}
        <div
          className="mt-9 flex flex-col gap-1 text-base text-muted-foreground"
          style={{ opacity: p(0, 0.3 + entries.length * 0.13, 0.53) }}
        >
          {footer.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      </div>
    </SceneFrame>
  );
};

/** まだ書いていないシーン（作業中の仮） */
export const PlaceholderScene: React.FC<{ frame: Frame; sceneKey: string }> = ({
  frame,
  sceneKey,
}) => (
  <SceneFrame {...frame}>
    <div
      className="absolute text-3xl text-muted-foreground"
      style={{ left: CONTENT.left, top: 300 }}
    >
      （{sceneKey} は作成中）
    </div>
  </SceneFrame>
);
