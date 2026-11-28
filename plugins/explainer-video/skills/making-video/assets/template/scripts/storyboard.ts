// 絵コンテ src/videos/<slug>/STORYBOARD.md を、plan.ts・script.ts・voice.ts から作る。
//   npm run storyboard -- <slug>
// 各シーンの長さは動画本体と同じ計算（src/lib/timeline.ts）。音声を作り直したら、これも作り直す。
import { writeFileSync } from "node:fs";
import path from "node:path";
import { FPS, HEIGHT, WIDTH } from "../src/lib/config.ts";
import { stepSeconds } from "../src/lib/timing.ts";
import { clock, loadVideo } from "./load.ts";

const v = await loadVideo(process.argv[2], "npm run storyboard -- <slug>");

// markdown で崩れないようにする（URL はコードにする）
const md = (s: string) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\|/g, "\\|")
    .replace(
      /https?:\/\/[A-Za-z0-9.\-_/~%?=#:]+/g,
      (u) => `\`${u.replace(/&amp;/g, "&")}\``,
    );
const sec = (s: number) => `${s.toFixed(1)}s`;

const rows = v.timeline.scenes.map(
  (s) =>
    `| ${s.index + 1} | ${clock(s.from)} | ${md(s.plan.title)} | ${md(s.plan.parts ?? "")} | ${md(s.plan.visual ?? "")} | ${v.planned[s.plan.key].length} | ${sec(s.frames / FPS)} |`,
);

let chapter = "";
const script = v.PLAN.filter((p) =>
  v.SCRIPT[p.key].some((s) => s.caption || s.say),
)
  .map((p) => {
    const head =
      p.chapter && p.chapter !== chapter ? `## ${md(p.chapter)}\n\n` : "";
    chapter = p.chapter;
    const s = v.planned[p.key];
    const list = s
      .map((st, i) => {
        const text = st.caption || `（字幕なし。読み上げ: ${st.say ?? ""}）`;
        return `${i + 1}. ${md(text).replace(/^(\d+)\. /, "$1\\. ")}（${sec(stepSeconds(st, i === s.length - 1))}）`;
      })
      .join("\n");
    return `${head}### ${md(p.title)}\n\n${list}`;
  })
  .join("\n\n");

const total = v.timeline.total;
const out = `# 絵コンテ: ${md(v.VIDEO.title)}

- **コンポジション:** \`${v.slug}\`
- **画面:** ${WIDTH}×${HEIGHT} @ ${FPS}fps
- **長さ:** ${total}f = ${(total / FPS).toFixed(1)}s（約 ${clock(total)}）${v.voiced ? "" : "。音声がまだ無いので、読み上げの長さを文字数から見積もった値"}
- **音声:** ${v.voiced ? v.VOICE_CREDIT : "（未作成）"}
- **原稿:** ${md(v.VIDEO.origin ?? "")}
- **出典表記:** ${md(v.VIDEO.source ?? "")}

| # | 開始 | シーン | 部品 | 画面の内容 | ステップ | 長さ |
| --- | --- | --- | --- | --- | --- | --- |
${rows.join("\n")}

シーンの間は ${v.timeline.transition}f 重なる（章の頭は slide、ほかは fade）。

## 台本（画面の字幕）

${script}
`;

writeFileSync(path.join(v.dir, "STORYBOARD.md"), out);
console.log(
  `${v.PLAN.length} シーン、${total}f = ${clock(total)} → src/videos/${v.slug}/STORYBOARD.md`,
);
