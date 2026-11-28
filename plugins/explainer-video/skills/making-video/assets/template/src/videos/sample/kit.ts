// 台本・音声の長さ・計画を束ねる。シーン（scenes.tsx）は kit.frameOf(key) で枠に渡す値を受け取る。
import { createKit } from "@/lib/video";
import { PLAN, VIDEO } from "./plan";
import { SCRIPT } from "./script";
import { VOICE_SECONDS } from "./voice";

export const kit = createKit({
  meta: VIDEO,
  plan: PLAN,
  script: SCRIPT,
  voiceSeconds: VOICE_SECONDS,
});
