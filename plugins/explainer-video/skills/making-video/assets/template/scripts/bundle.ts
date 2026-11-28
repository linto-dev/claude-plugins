// バンドラの設定（remotion.config.ts と scripts/review.ts で共有する）。どちらもプロジェクトのルートで動かす（npm run が cwd をそろえる）。
// shadcn/ui の部品は components.json の "@/" の別名で互いを読み込む。バンドラは tsconfig の paths を読まないので、ここで別名を解決する。
// Tailwind CSS v4（src/styles/globals.css）は @remotion/tailwind-v4 で有効にする。enableTailwind は既存の .css の規則を外してから足すので、2 回通っても重複しない。
import path from "node:path";
import { enableTailwind } from "@remotion/tailwind-v4";

export const withProjectBundler = <C extends { resolve?: object }>(
  config: C,
): C =>
  enableTailwind({
    ...config,
    resolve: {
      ...config.resolve,
      alias: {
        ...((config.resolve as { alias?: object } | undefined)?.alias ?? {}),
        "@": path.join(process.cwd(), "src"),
      },
    },
  } as Parameters<typeof enableTailwind>[0]) as C;
