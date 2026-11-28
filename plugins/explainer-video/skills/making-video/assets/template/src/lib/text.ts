// 文字の大きさの段階（DESIGN.md の「文字」）。部品の size には、px の数ではなくこの名前を渡す。
// 値は src/styles/globals.css の @theme（1920×1080 の動画向け）。Tailwind はソースの中の完全なクラス名しか拾わないので、クラスはここに完全な文字列で並べる。

export type TextSize =
  | "sm"
  | "base"
  | "lg"
  | "xl"
  | "2xl"
  | "3xl"
  | "4xl"
  | "5xl"
  | "6xl";

export const TEXT_SIZE: Record<TextSize, string> = {
  sm: "text-sm",
  base: "text-base",
  lg: "text-lg",
  xl: "text-xl",
  "2xl": "text-2xl",
  "3xl": "text-3xl",
  "4xl": "text-4xl",
  "5xl": "text-5xl",
  "6xl": "text-6xl",
};

/** 各段階の px（SVG の座標計算や、文字の大きさに比例する寸法に使う） */
export const TEXT_PX: Record<TextSize, number> = {
  sm: 21,
  base: 24,
  lg: 27,
  xl: 30,
  "2xl": 36,
  "3xl": 45,
  "4xl": 54,
  "5xl": 72,
  "6xl": 90,
};
