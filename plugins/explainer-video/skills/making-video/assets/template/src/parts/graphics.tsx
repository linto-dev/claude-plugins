// 図の部品: アイコン・判定のバッジ・チップ・色つきの囲み・矢印・位置指定・箱。
// 座標は 1920×1080 の画面の px。色は src/lib/palette.ts の tone で渡す（意味は DESIGN.md の「図の色」）。
import {
  Alert02Icon,
  Cancel01Icon,
  LockIcon,
  ServerStack01Icon,
  Tick02Icon,
  UserIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import type React from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  type EmphasisTone,
  mixColor,
  TONE_BORDER,
  TONE_LINE_TEXT,
  TONE_SOLID,
  TONE_TEXT,
  TONE_VAR,
  type Tone,
} from "@/lib/palette";
import { Phrase } from "@/lib/phrase";
import { TEXT_SIZE, type TextSize } from "@/lib/text";
import { cn } from "@/lib/utils";

export type Pos = { x: number; y: number };

// ---------- アイコン（Hugeicons。色は className の text-* で指定し、線は currentColor） ----------
// ほかのアイコンは @hugeicons/core-free-icons から読み、<Glyph icon={…} /> で使う。

type IconSvg = React.ComponentProps<typeof HugeiconsIcon>["icon"];

export const Glyph: React.FC<{
  icon: IconSvg;
  size?: number;
  className?: string;
}> = ({ icon, size = 60, className }) => (
  <HugeiconsIcon
    icon={icon}
    size={size}
    strokeWidth={1.8}
    className={cn("text-foreground", className)}
  />
);

type GlyphProps = { size?: number; className?: string };
export const PersonGlyph: React.FC<GlyphProps> = ({ size = 66, className }) => (
  <Glyph icon={UserIcon} size={size} className={className} />
);
export const ServerGlyph: React.FC<GlyphProps> = ({ size = 60, className }) => (
  <Glyph icon={ServerStack01Icon} size={size} className={className} />
);
export const LockGlyph: React.FC<GlyphProps> = ({ size = 33, className }) => (
  <Glyph
    icon={LockIcon}
    size={size}
    className={cn("text-figure-blue", className)}
  />
);
export const AlertGlyph: React.FC<GlyphProps> = ({ size = 42, className }) => (
  <Glyph
    icon={Alert02Icon}
    size={size}
    className={cn("text-figure-vermillion", className)}
  />
);

// 判定の丸いバッジ（✓ / ✗ / ？）。正しいものは緑、誤りは朱、未定はグレー。
const VERDICT_TONE = {
  ok: "green",
  ng: "vermillion",
  unknown: "gray",
} as const;

export const Verdict: React.FC<{
  kind: "ok" | "ng" | "unknown";
  size?: number;
}> = ({ kind, size = 51 }) => (
  <span
    className={cn(
      "inline-flex shrink-0 items-center justify-center rounded-full",
      TONE_SOLID[VERDICT_TONE[kind]],
    )}
    style={{ width: size, height: size }}
  >
    {kind === "unknown" ? (
      <span
        className="leading-none font-bold"
        style={{ fontSize: size * 0.56 }}
      >
        ?
      </span>
    ) : (
      <HugeiconsIcon
        icon={kind === "ok" ? Tick02Icon : Cancel01Icon}
        size={size * 0.62}
        strokeWidth={2.6}
      />
    )}
  </span>
);

// ---------- 文字のかたまり ----------

/** チップの色。emphasis は解説の要点（マーカーと同じ淡い黄色）、それ以外は図の色 */
const CHIP_VARIANT = {
  neutral: "outline",
  emphasis: "marker",
  blue: "blue",
  vermillion: "vermillion",
  green: "green",
  gray: "outline",
} as const;

export const Chip: React.FC<{
  children: React.ReactNode;
  tone?: EmphasisTone;
  size?: "sm" | "base" | "lg" | "xl" | "2xl";
  mono?: boolean;
  className?: string;
  style?: React.CSSProperties;
}> = ({
  children,
  tone = "neutral",
  size = "xl",
  mono = false,
  className,
  style,
}) => (
  <Badge
    variant={CHIP_VARIANT[tone]}
    size={size}
    className={cn(
      tone === "gray" && "text-muted-foreground",
      mono && "font-mono",
      className,
    )}
    style={style}
  >
    {children}
  </Badge>
);

/** 番号や記号のタグ（黒地に白抜き。設問番号・手順の番号など） */
export const NumTag: React.FC<{
  children: React.ReactNode;
  size?: "sm" | "base" | "lg" | "xl" | "2xl";
}> = ({ children, size = "xl" }) => (
  <Badge variant="ink" size={size}>
    {children}
  </Badge>
);

/** 囲みの枠の色（Card に足す）。neutral は Card の既定の淡い枠、emphasis は解説の要点の淡い黄色の地 */
export const TONE_RING: Record<EmphasisTone, string> = {
  neutral: "",
  emphasis: "bg-marker",
  blue: "ring-3 ring-figure-blue",
  vermillion: "ring-3 ring-figure-vermillion",
  green: "ring-3 ring-figure-green",
  gray: "ring-3 ring-figure-gray",
};

/** 枠の色つきの囲み（Card に TONE_RING を当てたもの）。位置・大きさ・出現は style で渡す */
export const ToneCard: React.FC<{
  tone?: EmphasisTone;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({ tone = "neutral", className, style, children }) => (
  <Card
    className={cn("gap-0 px-4 py-3", TONE_RING[tone], className)}
    style={style}
  >
    {children}
  </Card>
);

// ---------- 線と箱 ----------

/** 矢印。progress で根元から伸びる。実線 = ふつうの流れ、破線 = 例外・任意の流れ */
export const Arrow: React.FC<{
  from: Pos;
  to: Pos;
  progress?: number;
  tone?: Tone;
  width?: number;
  dashed?: boolean;
  head?: boolean;
}> = ({
  from,
  to,
  progress = 1,
  tone = "gray",
  width = 4,
  dashed = false,
  head = true,
}) => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy);
  const ang = (Math.atan2(dy, dx) * 180) / Math.PI;
  const shown = len * Math.max(0, Math.min(1, progress));
  if (shown <= 0.5) return null;
  return (
    <svg
      className={cn(
        "pointer-events-none absolute top-0 left-0 overflow-visible",
        TONE_LINE_TEXT[tone],
      )}
      width={1}
      height={1}
      aria-hidden
    >
      <g transform={`translate(${from.x} ${from.y}) rotate(${ang})`}>
        <line
          x1={0}
          y1={0}
          x2={Math.max(0, shown - (head ? 9 : 0))}
          y2={0}
          stroke="currentColor"
          strokeWidth={width}
          strokeLinecap="round"
          strokeDasharray={dashed ? "12 12" : undefined}
        />
        {head ? (
          <path
            d={`M ${shown - 18} -10 L ${shown} 0 L ${shown - 18} 10`}
            stroke="currentColor"
            strokeWidth={width}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}
      </g>
    </svg>
  );
};

/** 位置指定のラッパー。anchor の点を (x, y) に合わせる */
export const Place: React.FC<{
  x: number;
  y: number;
  children: React.ReactNode;
  opacity?: number;
  anchor?: "center" | "left" | "right" | "top" | "top-left";
  className?: string;
  style?: React.CSSProperties;
}> = ({ x, y, children, opacity = 1, anchor = "center", className, style }) => {
  const tr = {
    center: "-50% -50%",
    left: "0 -50%",
    right: "-100% -50%",
    top: "-50% 0",
    "top-left": "0 0",
  }[anchor];
  return (
    <div
      className={cn("absolute", className)}
      style={{ left: x, top: y, translate: tr, opacity, ...style }}
    >
      {children}
    </div>
  );
};

/** ラベル付きの矢印。ラベルは矢印の中点から offset だけずらして置く（何をする関係かを動詞で書く） */
export const LabeledArrow: React.FC<{
  from: Pos;
  to: Pos;
  p: number;
  label?: string;
  tone?: Tone;
  dashed?: boolean;
  width?: number;
  offset?: Pos;
  labelSize?: TextSize;
}> = ({
  from,
  to,
  p,
  label,
  tone = "gray",
  dashed = false,
  width = 4,
  offset = { x: 0, y: -27 },
  labelSize = "base",
}) => (
  <>
    <Arrow
      from={from}
      to={to}
      progress={p}
      tone={tone}
      dashed={dashed}
      width={width}
    />
    {label ? (
      <Place
        x={(from.x + to.x) / 2 + offset.x}
        y={(from.y + to.y) / 2 + offset.y}
        opacity={Math.max(0, Math.min(1, (p - 0.4) / 0.6))}
      >
        <span
          className={cn(
            "rounded-sm bg-card px-1 font-bold whitespace-nowrap",
            TEXT_SIZE[labelSize],
            tone === "neutral" || tone === "gray"
              ? "text-foreground"
              : TONE_TEXT[tone],
          )}
        >
          <Phrase text={label} />
        </span>
      </Place>
    ) : null}
  </>
);

/** 位置を指定した箱（主体・仕組みの図に使う）。hi（0→1）で図の色の枠と淡色の地になる */
export const Box: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  p?: number;
  hi?: number;
  tone?: Tone;
  children: React.ReactNode;
  size?: TextSize;
  dashed?: boolean;
  className?: string;
}> = ({
  x,
  y,
  w,
  h,
  p = 1,
  hi = 0,
  tone = "blue",
  children,
  size = "xl",
  dashed = false,
  className,
}) => {
  const on = hi > 0.5;
  return (
    <div
      className={cn(
        "absolute flex flex-col items-center justify-center rounded-xl border-3 text-center leading-snug font-bold",
        TEXT_SIZE[size],
        on ? TONE_BORDER[tone] : "border-figure-gray",
        on && tone !== "neutral" ? TONE_TEXT[tone] : "text-foreground",
        dashed && "border-dashed",
        className,
      )}
      style={{
        left: x,
        top: y,
        width: w,
        height: h,
        opacity: p,
        background: mixColor(TONE_VAR[tone].tint, hi, "var(--card)"),
      }}
    >
      {children}
    </div>
  );
};
