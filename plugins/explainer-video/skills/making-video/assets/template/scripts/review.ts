// シーンごとに、各ステップの動きが落ち着いた時点の静止画を書き出し、1 枚の一覧（contact sheet）にまとめる。
//   npm run review -- <slug> [scene...]   （シーンのキーを並べる。省略で全シーン）
// 出力: out/review/<slug>/<key>/<step>.png と out/review/<slug>/<key>.png（一覧。3 列、各 640×360）
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { FPS } from "../src/lib/config.ts";
import { stepFrames, stepStarts } from "../src/lib/timing.ts";
import { withProjectBundler } from "./bundle.ts";
import { loadVideo, ROOT } from "./load.ts";

const [slugArg, ...keys] = process.argv.slice(2);
const { slug, PLAN, steps, voiced } = await loadVideo(
  slugArg,
  "npm run review -- <slug> [scene...]",
);
if (!voiced)
  console.warn(
    "音声がまだ無いので、静止画の時点は見積もりです（npm run voice の後に撮り直す）。",
  );

const serveUrl = await bundle({
  entryPoint: path.join(ROOT, "src/index.ts"),
  publicDir: path.join(ROOT, "public"),
  webpackOverride: withProjectBundler,
});

const TILE = { w: 640, h: 360 };
const targets = keys.length ? keys : PLAN.map((p) => p.key);
for (const key of targets) {
  const idx = PLAN.findIndex((p) => p.key === key);
  if (idx < 0) {
    console.error(`${key} は plan.ts にありません`);
    continue;
  }
  const id = `${slug}-${String(idx + 1).padStart(2, "0")}-${key}`;
  const composition = await selectComposition({ serveUrl, id });
  const s = steps[key];
  const { starts } = stepStarts(s, FPS);
  const dir = path.join(ROOT, "out/review", slug, key);
  mkdirSync(dir, { recursive: true });
  const end = composition.durationInFrames;
  // 1 ステップだけのシーンは、始め・中ほど・終わりの 3 時点を撮る。
  // ほかは各ステップの 75% の時点（動きが落ち着き、次の字幕に替わる前）を撮る。
  const frames =
    s.length === 1
      ? [Math.round(1.3 * FPS), Math.round(end / 2), end - 10]
      : s.map((st, i) => {
          const len = stepFrames(st, FPS, i === s.length - 1);
          return Math.min(
            end - 1,
            starts[i] + Math.min(len - 4, Math.max(70, Math.round(len * 0.75))),
          );
        });
  const files: string[] = [];
  for (const [i, frame] of frames.entries()) {
    const output = path.join(dir, `${String(i).padStart(2, "0")}.png`);
    await renderStill({
      composition,
      serveUrl,
      output,
      frame,
      imageFormat: "png",
    });
    files.push(output);
  }
  const cols = Math.min(3, files.length);
  const rows = Math.ceil(files.length / cols);
  const pad = cols * rows - files.length;
  const filter = [
    files.map((_, i) => `[${i}:v]scale=${TILE.w}:${TILE.h}[s${i}]`).join(";"),
    Array.from(
      { length: pad },
      (_, i) => `color=c=white:s=${TILE.w}x${TILE.h}:d=1[p${i}]`,
    ).join(";"),
    `${[
      ...files.map((_, i) => `[s${i}]`),
      ...Array.from({ length: pad }, (_, i) => `[p${i}]`),
    ].join("")}xstack=inputs=${cols * rows}:layout=${layout(cols, rows)}[out]`,
  ]
    .filter(Boolean)
    .join(";");
  execFileSync("ffmpeg", [
    "-hide_banner",
    "-v",
    "error",
    "-y",
    ...files.flatMap((f) => ["-i", f]),
    "-filter_complex",
    filter,
    "-map",
    "[out]",
    "-frames:v",
    "1",
    path.join(ROOT, "out/review", slug, `${key}.png`),
  ]);
  console.log(`${key}: ${files.length} 枚 → out/review/${slug}/${key}.png`);
}

function layout(cols: number, rows: number) {
  const cells: string[] = [];
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++) cells.push(`${c * TILE.w}_${r * TILE.h}`);
  return cells.join("|");
}
