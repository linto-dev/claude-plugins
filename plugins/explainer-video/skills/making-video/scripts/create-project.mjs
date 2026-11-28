#!/usr/bin/env node
// 雛形（../assets/template）から、解説動画の新しいプロジェクトを作る。
//   node create-project.mjs <作る場所> [--no-install] [--no-skills]
// 作る場所は、まだ無いフォルダか、空のフォルダ（.DS_Store だけはあってよい）。
// 依存関係を入れ（npm install）、Remotion 公式の Agent Skills を入れる（npx remotion skills add）。
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const destArg = args.find((a) => !a.startsWith("--"));
const install = !args.includes("--no-install");
const skills = !args.includes("--no-skills");

if (!destArg) {
  console.error("使い方: node create-project.mjs <作る場所> [--no-install] [--no-skills]");
  process.exit(1);
}

const template = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../assets/template");
const dest = path.resolve(destArg);

// 消してよいのは OS が作る管理用のファイルだけ（.git や .env は中身として扱う）
const DISPOSABLE = new Set([".DS_Store", "Thumbs.db"]);
if (existsSync(dest)) {
  const rest = readdirSync(dest).filter((f) => !DISPOSABLE.has(f));
  if (rest.length) {
    console.error(`${dest} は空ではありません（${rest.slice(0, 5).join("、")}${rest.length > 5 ? " など" : ""}）。空のフォルダか、まだ無い場所を指定してください。`);
    process.exit(1);
  }
  for (const f of readdirSync(dest)) rmSync(path.join(dest, f));
}

cpSync(template, dest, { recursive: true });

// package.json の name をフォルダ名に合わせる（npm の名前に使えない文字を含むときは雛形のまま）
const pkgFile = path.join(dest, "package.json");
const pkg = JSON.parse(readFileSync(pkgFile, "utf8"));
const base = path.basename(dest).toLowerCase();
if (/^[a-z0-9][a-z0-9._-]*$/.test(base)) pkg.name = base;
writeFileSync(pkgFile, `${JSON.stringify(pkg, null, 2)}\n`);
console.log(`雛形を写しました: ${dest}`);

const run = (cmd, cmdArgs) => execFileSync(cmd, cmdArgs, { cwd: dest, stdio: "inherit" });
if (install) {
  console.log("依存関係を入れています（npm install）…");
  run("npm", ["install", "--loglevel=error", "--no-fund", "--no-audit"]);
}
if (install && skills) {
  console.log("Remotion 公式の Agent Skills を入れています（npx remotion skills add）…");
  try {
    run("npx", ["remotion", "skills", "add"]);
  } catch {
    console.warn("公式のスキルを入れられませんでした。後でプロジェクトのルートで npx remotion skills add を実行してください。");
  }
}

console.log(`
できました。次の手順:
  cd ${dest}
  npm run dev                    # Remotion Studio（見本の動画 sample がある）
  npm run new-video -- <slug>    # 新しい動画のフォルダを作る
見た目の決まりは DESIGN.md、コマンドは README.md にあります。`);
