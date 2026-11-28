// 動画を書き出し、音量を YouTube 向けにそろえ、概要欄のチャプターを作る。
//   npm run render -- <slug>
// 出力: out/<slug>.mp4（書き出したまま）・out/<slug>-master.mp4（公開用）・out/<slug>-description.txt
// 書き出しの細かい指定（並列数・画質など）を変えるときは、npx remotion render を直接使う（Remotion 公式の remotion-render スキル）。
import { execFileSync } from "node:child_process";
import { loadVideo } from "./load.ts";

const v = await loadVideo(process.argv[2], "npm run render -- <slug>");
if (!v.voiced) {
  console.error(
    `音声がまだありません。先に npm run voice -- ${v.slug} で読み上げを作ってください。`,
  );
  process.exit(1);
}
const run = (cmd: string, args: string[]) =>
  execFileSync(cmd, args, { stdio: "inherit" });

run("npx", ["remotion", "render", v.slug, `out/${v.slug}.mp4`]);
run("sh", [
  "scripts/master.sh",
  `out/${v.slug}.mp4`,
  `out/${v.slug}-master.mp4`,
]);
run("node", ["scripts/chapters.ts", v.slug]);
console.log(`公開用: out/${v.slug}-master.mp4`);
