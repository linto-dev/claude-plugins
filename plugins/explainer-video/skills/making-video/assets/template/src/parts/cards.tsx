// 囲みの部品: 原稿の引用・頁番号・行番号つきのコード・要点カード・説明カード・正答のカード・考える時間のカウントダウン。
import type React from "react";
import { interpolate } from "remotion";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  type EmphasisTone,
  type FigureTone,
  mixColor,
  TONE_VAR,
  type Tone,
} from "@/lib/palette";
import { TEXT_SIZE, type TextSize } from "@/lib/text";
import { cn } from "@/lib/utils";
import { TONE_RING } from "./graphics";
import { Rich, type RichOpts } from "./rich";

const body = (b: React.ReactNode) =>
  typeof b === "string" ? <Rich text={b} /> : b;

/** 引用カードの色。neutral は色を付けない */
const QUOTE_TONE: Record<Tone, string> = {
  neutral: "",
  blue: "bg-figure-blue-tint ring-3 ring-figure-blue",
  vermillion: "bg-figure-vermillion-tint ring-3 ring-figure-vermillion",
  green: "bg-figure-green-tint ring-3 ring-figure-green",
  gray: "bg-figure-gray-tint ring-3 ring-figure-gray",
};

/** 原稿の引用（話者・出どころ・頁つき）。text は Rich の記法で書ける */
export const QuoteCard: React.FC<
  {
    who?: string;
    page?: string;
    text: string;
    width?: number;
    size?: TextSize;
    tone?: Tone;
    className?: string;
    style?: React.CSSProperties;
  } & RichOpts
> = ({
  who,
  page,
  text,
  width,
  size = "2xl",
  tone = "neutral",
  className,
  style,
  ...rich
}) => (
  <Card
    className={cn("gap-1 px-6 py-5", QUOTE_TONE[tone], className)}
    style={{ width, ...style }}
  >
    {who || page ? (
      <div className="flex items-center gap-3">
        {who ? (
          <div className="text-base font-bold text-muted-foreground">{who}</div>
        ) : null}
        {page ? <PageTag>{page}</PageTag> : null}
      </div>
    ) : null}
    <div className={cn("leading-relaxed break-phrase", TEXT_SIZE[size])}>
      <Rich text={text} {...rich} />
    </div>
  </Card>
);

/** 頁番号・節番号（p.5・5.2.3 など） */
export const PageTag: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <Badge
    variant="outline"
    size="sm"
    className="bg-muted font-mono text-muted-foreground"
  >
    {children}
  </Badge>
);

type FocusTone = "mark" | FigureTone;
const FOCUS_VAR: Record<FocusTone, string> = {
  mark: "var(--marker)",
  blue: TONE_VAR.blue.tint,
  vermillion: TONE_VAR.vermillion.tint,
  green: TONE_VAR.green.tint,
  gray: TONE_VAR.gray.tint,
};

/** 行番号つきのコード・設定・ログ。focus で行を強調し、dim で強調していない行を薄くする */
export const CodePanel: React.FC<
  {
    caption?: string;
    lines: string[];
    /** 1 始まりの行番号ごとの強調（0→1） */
    focus?: Record<number, number>;
    focusTone?: FocusTone;
    dim?: number;
    size?: TextSize;
    width?: number;
    /** 表示する行（1 始まり）。省略で全部 */
    only?: number[];
    note?: string;
    className?: string;
    style?: React.CSSProperties;
  } & RichOpts
> = ({
  caption,
  lines,
  focus = {},
  focusTone = "mark",
  dim = 0,
  size = "base",
  width,
  only,
  note,
  className,
  style,
  ...rich
}) => {
  const rows = lines
    .map((t, i) => ({ n: i + 1, t }))
    .filter((r) => !only || only.includes(r.n));
  return (
    <div className={className} style={{ width, ...style }}>
      <Card
        className={cn(
          "gap-0 rounded-md py-3 font-mono leading-relaxed ring-3 ring-figure-ink",
          TEXT_SIZE[size],
        )}
      >
        {rows.map(({ n, t }) => {
          const f = focus[n] ?? 0;
          return (
            <div
              key={n}
              className="flex gap-4 pr-6 pl-3"
              style={{
                background: mixColor(FOCUS_VAR[focusTone], f),
                // 薄くするのは文字の色だけ（opacity で薄くすると 4.5:1 を下回る）
                color: mixColor(
                  "var(--muted-foreground)",
                  dim * (1 - f),
                  "var(--foreground)",
                ),
              }}
            >
              <span className="w-[1.6em] shrink-0 text-right text-muted-foreground">
                {n}
              </span>
              <span className="wrap-anywhere whitespace-pre-wrap">
                <Rich text={t} phrase={false} {...rich} />
              </span>
            </div>
          );
        })}
      </Card>
      {note ? (
        <div className="mt-1 text-sm text-muted-foreground">{note}</div>
      ) : null}
      {caption ? (
        <div className="mt-2 text-center text-base font-bold">{caption}</div>
      ) : null}
    </div>
  );
};

const HEAD_TEXT: Record<EmphasisTone, string> = {
  neutral: "text-muted-foreground",
  emphasis: "text-marker-foreground",
  blue: "text-figure-blue-text",
  vermillion: "text-figure-vermillion-text",
  green: "text-figure-green-text",
  gray: "text-muted-foreground",
};

/** 要点カード（右側に積み上げる。見出しは小さく、本文は 1〜2 行の短い文）。p で出てくる */
export const Point: React.FC<{
  head: string;
  body: React.ReactNode;
  p: number;
  tone?: EmphasisTone;
  size?: TextSize;
}> = ({ head, body: b, p, tone = "emphasis", size = "xl" }) => (
  <Card
    className={cn("gap-1 px-6 py-3", TONE_RING[tone])}
    style={{ opacity: p, translate: `${(1 - p) * 18}px 0` }}
  >
    <div className={cn("text-sm font-bold", HEAD_TEXT[tone])}>{head}</div>
    <div
      className={cn("leading-normal font-bold break-phrase", TEXT_SIZE[size])}
    >
      {body(b)}
    </div>
  </Card>
);

/** 見出しと本文の説明カード（x を渡すと absolute で置く）。p で出てくる */
export const Note: React.FC<{
  head: string;
  body: React.ReactNode;
  p: number;
  tone?: EmphasisTone;
  x?: number;
  y?: number;
  width?: number;
  size?: TextSize;
}> = ({ head, body: b, p, tone = "neutral", x, y, width, size = "xl" }) => (
  <Card
    className={cn(
      "gap-1 px-6 py-4",
      x !== undefined && "absolute",
      TONE_RING[tone],
    )}
    style={{
      ...(x !== undefined ? { left: x, top: y } : {}),
      width,
      opacity: p,
      translate: `${(1 - p) * 18}px 0`,
    }}
  >
    <div
      className={cn(
        "font-bold",
        TEXT_SIZE[size],
        tone === "neutral" ? "text-foreground" : HEAD_TEXT[tone],
      )}
    >
      {head}
    </div>
    <div
      className={cn("leading-normal font-bold break-phrase", TEXT_SIZE[size])}
    >
      {body(b)}
    </div>
  </Card>
);

/** 正答・結論のカード（緑の枠）。p で出てくる */
export const AnswerCard: React.FC<{
  p: number;
  children: React.ReactNode;
  label?: string;
  size?: TextSize;
  className?: string;
  style?: React.CSSProperties;
}> = ({ p, children, label = "正答", size = "4xl", className, style }) => (
  <Card
    className={cn(
      "inline-flex flex-row items-center gap-6 px-9 py-6 ring-3 ring-figure-green",
      className,
    )}
    style={{ opacity: p, scale: String(0.94 + 0.06 * p), ...style }}
  >
    <Badge size="xl" className="rounded-lg bg-figure-green-solid text-white">
      {label}
    </Badge>
    <div className={cn("leading-snug font-bold", TEXT_SIZE[size])}>
      {children}
    </div>
  </Card>
);

/** 考える時間のカウントダウン（リング）。from フレームから dur フレームかけて減る */
export const ThinkTimer: React.FC<{
  frame: number;
  fps: number;
  from: number;
  dur: number;
  size?: number;
  label?: string;
}> = ({ frame, fps, from, dur, size = 225, label = "考える時間" }) => {
  const show = interpolate(
    frame,
    [from - 0.4 * fps, from + 0.13 * fps],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  const left = interpolate(frame, [from, from + dur], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sec = Math.max(0, Math.ceil(left * (dur / fps)));
  const r = size / 2 - 12;
  const len = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center gap-3" style={{ opacity: show }}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          className="absolute inset-0 -rotate-90"
          aria-hidden
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            strokeWidth={12}
            className="fill-card stroke-border"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            strokeWidth={12}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={len}
            strokeDashoffset={len * (1 - left)}
            className="stroke-primary"
          />
        </svg>
        <div
          className="absolute inset-0 flex items-center justify-center font-bold text-primary tabular-nums"
          style={{ fontSize: size * 0.4 }}
        >
          {sec}
        </div>
      </div>
      <div className="text-xl font-bold text-muted-foreground">{label}</div>
    </div>
  );
};
