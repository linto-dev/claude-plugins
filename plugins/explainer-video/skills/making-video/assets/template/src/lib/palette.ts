// 図の色（Okabe-Ito）を TypeScript から使うための表。値は src/styles/globals.css の --figure-* にある。
// 意味の割り当ては DESIGN.md の「図の色」: blue = 注目させる要素、vermillion = 注意・危険・誤り、green = 正答・安全・うまくいく状態、gray = 補足。動画ごとに意味を固定する。
//
// Tailwind はソースの中の完全なクラス名しか拾わないので、tone ごとのクラスはここに完全な文字列で並べる。

export type FigureTone = "blue" | "vermillion" | "green" | "gray";
/** 図の要素の色。neutral は色を付けない（線は ink、地は白） */
export type Tone = FigureTone | "neutral";
/** 図の色に、解説の要点（emphasis。マーカーと同じ淡い黄色）を足したもの。チップと囲みに使う */
export type EmphasisTone = Tone | "emphasis";

/** 線（矢印・枠）。SVG の stroke="currentColor" と組み合わせる */
export const TONE_LINE_TEXT: Record<Tone, string> = {
  neutral: "text-figure-ink",
  blue: "text-figure-blue",
  vermillion: "text-figure-vermillion",
  green: "text-figure-green",
  gray: "text-figure-gray",
};

/** 枠線の色 */
export const TONE_BORDER: Record<Tone, string> = {
  neutral: "border-figure-ink",
  blue: "border-figure-blue",
  vermillion: "border-figure-vermillion",
  green: "border-figure-green",
  gray: "border-figure-gray",
};

/** 淡色の地と、その上の文字 */
export const TONE_TINT: Record<Tone, string> = {
  neutral: "bg-card text-foreground",
  blue: "bg-figure-blue-tint text-figure-blue-text",
  vermillion: "bg-figure-vermillion-tint text-figure-vermillion-text",
  green: "bg-figure-green-tint text-figure-green-text",
  gray: "bg-figure-gray-tint text-figure-gray-text",
};

/** 淡色の上の文字だけ */
export const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-foreground",
  blue: "text-figure-blue-text",
  vermillion: "text-figure-vermillion-text",
  green: "text-figure-green-text",
  gray: "text-figure-gray-text",
};

/** 濃色の地に白文字（その図で一番言いたい 1 か所だけ） */
export const TONE_SOLID: Record<Tone, string> = {
  neutral: "bg-figure-ink text-white",
  blue: "bg-figure-blue-solid text-white",
  vermillion: "bg-figure-vermillion-solid text-white",
  green: "bg-figure-green-solid text-white",
  gray: "bg-figure-gray-solid text-white",
};

/** CSS 変数の名前（style や SVG の属性で使う） */
export const TONE_VAR: Record<
  Tone,
  { line: string; text: string; tint: string; solid: string }
> = {
  neutral: {
    line: "var(--figure-ink)",
    text: "var(--foreground)",
    tint: "var(--card)",
    solid: "var(--figure-ink)",
  },
  blue: {
    line: "var(--figure-blue)",
    text: "var(--figure-blue-text)",
    tint: "var(--figure-blue-tint)",
    solid: "var(--figure-blue-solid)",
  },
  vermillion: {
    line: "var(--figure-vermillion)",
    text: "var(--figure-vermillion-text)",
    tint: "var(--figure-vermillion-tint)",
    solid: "var(--figure-vermillion-solid)",
  },
  green: {
    line: "var(--figure-green)",
    text: "var(--figure-green-text)",
    tint: "var(--figure-green-tint)",
    solid: "var(--figure-green-solid)",
  },
  gray: {
    line: "var(--figure-gray)",
    text: "var(--figure-gray-text)",
    tint: "var(--figure-gray-tint)",
    solid: "var(--figure-gray-solid)",
  },
};

/**
 * 色をフレームの進み具合 p（0→1）で出す。p = 0 で透明、1 で color そのもの。
 * 例: style={{ background: mixColor(TONE_VAR.blue.tint, focus) }}
 */
export const mixColor = (color: string, p: number, base = "transparent") => {
  const t = Math.max(0, Math.min(1, p));
  if (t <= 0) return base;
  if (t >= 1) return color;
  return `color-mix(in srgb, ${color} ${(t * 100).toFixed(1)}%, ${base})`;
};
