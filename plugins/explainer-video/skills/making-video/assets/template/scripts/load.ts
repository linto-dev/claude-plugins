// scripts/ が共通で使う、動画のフォルダ（src/videos/<slug>/）の読み込み。
import { existsSync } from "node:fs";
import path from "node:path";
import { FPS } from "../src/lib/config.ts";
import type { Step } from "../src/lib/step.ts";
import {
  buildTimeline,
  type PlanEntry,
  type VideoMeta,
  type VoiceSeconds,
  withVoice,
} from "../src/lib/timeline.ts";

export const ROOT = path.resolve(import.meta.dirname, "..");

export const loadVideo = async (slug: string | undefined, usage: string) => {
  if (!slug) {
    console.error(`使い方: ${usage}`);
    process.exit(1);
  }
  const dir = path.join(ROOT, "src/videos", slug);
  if (!existsSync(path.join(dir, "plan.ts"))) {
    console.error(`src/videos/${slug}/plan.ts がありません。`);
    process.exit(1);
  }
  const { PLAN, VIDEO } = (await import(path.join(dir, "plan.ts"))) as {
    PLAN: readonly PlanEntry[];
    VIDEO: VideoMeta;
  };
  const { SCRIPT } = (await import(path.join(dir, "script.ts"))) as {
    SCRIPT: Record<string, readonly Step[]>;
  };
  const { VOICE_SECONDS, VOICE_CREDIT } = (await import(
    path.join(dir, "voice.ts")
  )) as { VOICE_SECONDS: VoiceSeconds; VOICE_CREDIT: string };
  const voiced = Object.keys(VOICE_SECONDS).length > 0;
  // 音声がまだ無いときは、読み上げの長さを文字数から見積もる（6.6 字/秒。VOICEVOX の話速 1.1 のとき）。
  // 字幕の無い表紙なども、読み上げの分だけ長く見積もれる。動画本体（Studio）は音声ができるまで字幕の長さだけで動く
  // steps: 今の動画本体と同じステップ（静止画の時点に使う）。planned: 絵コンテ・チャプター用（音声が無ければ見積もり）
  const steps = withVoice(SCRIPT, VOICE_SECONDS);
  const planned = voiced ? steps : withVoice(SCRIPT, estimateVoice(SCRIPT));
  const timeline = buildTimeline(PLAN, planned, FPS);
  return {
    slug,
    dir,
    PLAN,
    VIDEO,
    SCRIPT,
    VOICE_CREDIT,
    steps,
    planned,
    timeline,
    voiced,
  };
};

/** 台本の文字数から、各ステップの読み上げの秒数を見積もる */
const estimateVoice = (script: Record<string, readonly Step[]>): VoiceSeconds =>
  Object.fromEntries(
    Object.entries(script).map(([key, steps]) => [
      key,
      steps.map((s) => {
        const text = (s.say ?? s.caption).trim();
        return text ? Array.from(text).length / 6.6 : null;
      }),
    ]),
  );

/** フレーム数を「分:秒」（1 時間以上は「時:分:秒」）にする */
export const clock = (frames: number) => {
  const s = Math.floor(frames / FPS);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
};
