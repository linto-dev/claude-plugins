// 新しい動画のフォルダを作り、src/Root.tsx に登録する。
//   npm run new-video -- <slug> [--from <元の slug>]   （省略時は sample を写す）
// plan.ts・script.ts・kit.ts・index.tsx・figures/ を写す。plan.ts と script.ts は元のままなので、原稿に合わせて書き換える。
// シーンは写さない（scenes.tsx は空の SCENES にし、全シーンが「作成中」の仮のシーンになる。書き方は元の scenes を読む）。voice.ts は空にする。
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { ROOT } from "./load.ts";

const args = process.argv.slice(2);
const slug = args.find((a) => !a.startsWith("--"));
const fromIdx = args.indexOf("--from");
const from = fromIdx >= 0 ? args[fromIdx + 1] : "sample";
const usage = "使い方: npm run new-video -- <slug> [--from <元の slug>]";

if (!slug || !from) {
  console.error(usage);
  process.exit(1);
}
// コンポジションの ID に使えて、ファイル名にもなる形に絞る
if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
  console.error(
    `slug は英小文字・数字・ハイフンで書きます（例: tcpip-ch5）: ${slug}`,
  );
  process.exit(1);
}
const videos = path.join(ROOT, "src/videos");
const src = path.join(videos, from);
const dest = path.join(videos, slug);
if (!existsSync(path.join(src, "plan.ts"))) {
  console.error(`写す元の src/videos/${from}/ がありません。`);
  process.exit(1);
}
if (existsSync(dest)) {
  console.error(`src/videos/${slug}/ はもうあります。`);
  process.exit(1);
}

/** slug から export の名前を作る（tcpip-ch5 → tcpipCh5。数字で始まるときは頭に v を付ける） */
const ident = (s: string) => {
  const camel = s.replace(/-([a-z0-9])/g, (_, c: string) => c.toUpperCase());
  return /^[0-9]/.test(camel) ? `v${camel}` : camel;
};

const SKIP = ["STORYBOARD.md", "scenes.tsx", "scenes"];
cpSync(src, dest, {
  recursive: true,
  filter: (p) => p === src || !SKIP.includes(path.relative(src, p)),
});
const edit = (file: string, f: (s: string) => string) => {
  const p = path.join(dest, file);
  writeFileSync(p, f(readFileSync(p, "utf8")));
};
edit("plan.ts", (s) => s.replace(`slug: "${from}"`, `slug: "${slug}"`));
edit("index.tsx", (s) =>
  s.replace(`export const ${ident(from)} =`, `export const ${ident(slug)} =`),
);
writeFileSync(
  path.join(dest, "scenes.tsx"),
  `// シーン。plan.ts のキーごとに書き、SCENES に足す。足していないシーンは「作成中」の仮のシーンになる。
// 書き方は src/videos/${from}/scenes${existsSync(path.join(src, "scenes")) ? "/" : ".tsx"} と DESIGN.md。
import type React from "react";
import type { SceneKey } from "./plan";

export const SCENES: Partial<Record<SceneKey, React.FC>> = {};
`,
);
writeFileSync(
  path.join(dest, "voice.ts"),
  "// scripts/voice.ts が生成。手で編集しない。\n" +
    'export const VOICE_CREDIT = "";\n' +
    "export const VOICE_SECONDS: Record<string, readonly (number | null)[]> = {};\n",
);

// Root.tsx の目印の行の上に、import とコンポジションを足す
const rootFile = path.join(ROOT, "src/Root.tsx");
const root = readFileSync(rootFile, "utf8");
const IMPORT_MARK = "// new-video: imports";
const COMP_MARK = "{/* new-video: compositions";
if (!root.includes(IMPORT_MARK) || !root.includes(COMP_MARK)) {
  console.error(
    "src/Root.tsx に new-video の目印の行がありません。import とコンポジションを手で足してください。",
  );
  process.exit(1);
}
const name = ident(slug);
const composition = `<Composition
        id="${slug}"
        component={${name}.Video}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={${name}.calculateMetadata}
      />
      {sceneFolder(${name})}
      `;
writeFileSync(
  rootFile,
  root
    .replace(
      IMPORT_MARK,
      `import { ${name} } from "./videos/${slug}";\n${IMPORT_MARK}`,
    )
    .replace(COMP_MARK, `${composition}${COMP_MARK}`),
);
// import の並びと字下げを Biome にそろえさせる（失敗しても登録はできている）
try {
  execFileSync("npx", ["biome", "check", "--write", "src/Root.tsx"], {
    cwd: ROOT,
    stdio: "ignore",
  });
} catch {
  console.warn(
    "src/Root.tsx の整形に失敗しました。npm run check で整えてください。",
  );
}
console.log(
  `src/videos/${slug}/ を作り、src/Root.tsx に登録しました（元: ${from}）。`,
);
console.log(
  "次: plan.ts（VIDEO と PLAN）と script.ts（SCRIPT）を原稿に合わせて書き換え、scenes.tsx にシーンを書く。",
);
