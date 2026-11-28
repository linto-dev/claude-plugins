// YouTube の概要欄に貼るチャプター（時刻付きの目次）とクレジットを out/<slug>-description.txt に書き出す。
//   npm run chapters -- <slug>
// チャプターは最初のシーンと、plan.ts で mark を付けたシーンで切る。YouTube は最初が 0:00 で、3 つ以上・各 10 秒以上のときにチャプターとして扱う。
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { FPS } from "../src/lib/config.ts";
import { chapterMarks } from "../src/lib/timeline.ts";
import { clock, loadVideo, ROOT } from "./load.ts";

const v = await loadVideo(process.argv[2], "npm run chapters -- <slug>");
if (!v.voiced)
  console.warn(
    "音声がまだ無いので、時刻は読み上げの長さを文字数から見積もった値です。",
  );

const marks = chapterMarks(v.timeline);
const short = marks.filter(
  (m, i) => (marks[i + 1]?.frame ?? v.timeline.total) - m.frame < 10 * FPS,
);
if (marks.length < 3)
  console.warn(
    "チャプターが 3 つ未満なので、YouTube はチャプターとして扱いません。",
  );
if (short.length)
  console.warn(
    `10 秒未満のチャプターがあります: ${short.map((m) => m.label).join("、")}`,
  );

const out = [
  v.VIDEO.subtitle ? `${v.VIDEO.title} ― ${v.VIDEO.subtitle}` : v.VIDEO.title,
  "",
  "チャプター",
  ...marks.map((m) => `${clock(m.frame)} ${m.label}`),
  "",
  ...(v.VIDEO.source ? [v.VIDEO.source] : []),
  ...(v.VIDEO.notes ?? []),
  ...(v.voiced ? [`音声：${v.VOICE_CREDIT}`] : []),
  "",
].join("\n");

mkdirSync(path.join(ROOT, "out"), { recursive: true });
const file = path.join(ROOT, "out", `${v.slug}-description.txt`);
writeFileSync(file, out);
console.log(out);
console.log(
  `全体 ${clock(v.timeline.total)}（${v.timeline.total}f）→ out/${v.slug}-description.txt`,
);
