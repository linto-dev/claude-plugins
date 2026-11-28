// 動画の台本（src/videos/<slug>/script.ts）を VOICEVOX エンジンで音声にする。
//   docker run -d --rm --name voicevox-engine -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest
//   npm run voice -- <slug>
// 出力: public/voice/<slug>/<scene>-<n>.wav、src/videos/<slug>/voice.ts（各音声の秒数とクレジット）、out/voice-kana-<slug>.txt（読みの確認用）
// 文と設定が前回と同じ音声は作り直さない（public/voice/<slug>/manifest.json）。台本から消えたステップの音声は消す。
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { toReading } from "./reading.ts";

const slug = process.argv[2];
if (!slug) {
  console.error("使い方: npm run voice -- <slug>");
  process.exit(1);
}

const ENGINE = process.env.VOICEVOX_URL ?? "http://127.0.0.1:50021";
// 話速・抑揚などの既定。script.ts の VOICE.params で動画ごとに上書きできる。
const DEFAULT_PARAMS = {
  speedScale: 1.1,
  intonationScale: 1.15,
  pitchScale: 0,
  volumeScale: 1,
  prePhonemeLength: 0.05,
  postPhonemeLength: 0.1,
  outputSamplingRate: 48000,
  outputStereo: false,
};

type Step = { caption: string; say?: string };
type VoiceSetting = {
  speaker?: string;
  style?: string;
  params?: Partial<typeof DEFAULT_PARAMS>;
};
const root = new URL("..", import.meta.url);
const scriptUrl = new URL(`src/videos/${slug}/script.ts`, root);
if (!existsSync(scriptUrl)) {
  console.error(`src/videos/${slug}/script.ts がありません。`);
  process.exit(1);
}
const {
  SCRIPT,
  VOICE = {},
  READINGS = [],
  READING_RULES = [],
  USER_DICT = [],
} = (await import(scriptUrl.href)) as {
  SCRIPT: Record<string, readonly Step[]>;
  VOICE?: VoiceSetting;
  READINGS?: readonly [string, string][];
  READING_RULES?: readonly [RegExp, string][];
  USER_DICT?: readonly [string, string, number][];
};
const SPEAKER = {
  name: VOICE.speaker ?? "青山龍星",
  style: VOICE.style ?? "喜び",
};
const PARAMS = { ...DEFAULT_PARAMS, ...VOICE.params };

const engine = async (path: string, init?: RequestInit) => {
  try {
    const res = await fetch(`${ENGINE}${path}`, init);
    if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
    return res;
  } catch (e) {
    if (e instanceof TypeError) {
      console.error(
        `VOICEVOX エンジン（${ENGINE}）につながりません。次で起動してから、もう一度実行してください。\n` +
          "  docker run -d --rm --name voicevox-engine -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest",
      );
      process.exit(1);
    }
    throw e;
  }
};

const speakers = (await (await engine("/speakers")).json()) as {
  name: string;
  styles: { name: string; id: number }[];
}[];
const speaker = speakers.find((s) => s.name === SPEAKER.name);
const style = speaker?.styles.find((s) => s.name === SPEAKER.style);
if (!speaker || !style) {
  console.error(
    `${SPEAKER.name}（${SPEAKER.style}）が見つかりません。使える話者とスタイル:\n` +
      speakers
        .map((s) => `  ${s.name}: ${s.styles.map((t) => t.name).join("・")}`)
        .join("\n"),
  );
  process.exit(1);
}
console.log(`${speaker.name}（${style.name}）id=${style.id}`);

// ユーザー辞書に登録する（同じ表記の語は消してから登録し直す）。辞書はエンジンの中で共有されるので、
// 同じエンジンで作るほかの動画と、同じ表記の読みをそろえる。
if (USER_DICT.length) {
  const dict = (await (await engine("/user_dict")).json()) as Record<
    string,
    { surface: string }
  >;
  for (const [surface, pronunciation, accent] of USER_DICT) {
    // エンジンは表記を全角にして持つ
    const wide = surface.replace(/[!-~]/g, (c) =>
      String.fromCharCode(c.charCodeAt(0) + 0xfee0),
    );
    for (const [id, w] of Object.entries(dict))
      if (w.surface === wide || w.surface === surface)
        await engine(`/user_dict_word/${id}`, { method: "DELETE" });
    const q = new URLSearchParams({
      surface,
      pronunciation,
      accent_type: String(accent),
      word_type: "PROPER_NOUN",
    });
    await engine(`/user_dict_word?${q}`, { method: "POST" });
  }
  console.log(`ユーザー辞書 ${USER_DICT.length} 語`);
}

const voiceDir = new URL(`public/voice/${slug}/`, root);
mkdirSync(voiceDir, { recursive: true });
mkdirSync(new URL("out/", root), { recursive: true });
const manifestUrl = new URL("manifest.json", voiceDir);
const manifest: Record<string, string> = existsSync(manifestUrl)
  ? JSON.parse(readFileSync(manifestUrl, "utf8"))
  : {};

// WAV のヘッダーから秒数を出す
const wavSeconds = (buf: Buffer) => {
  const rate = buf.readUInt32LE(24);
  const channels = buf.readUInt16LE(22);
  const bits = buf.readUInt16LE(34);
  let off = 12;
  while (off < buf.length) {
    const id = buf.toString("ascii", off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    if (id === "data") return size / (rate * channels * (bits / 8));
    off += 8 + size;
  }
  throw new Error("WAV に data チャンクがありません");
};

const seconds: Record<string, (number | null)[]> = {};
const kanaLines: string[] = [];
const used = new Set<string>();
let made = 0;
for (const [key, steps] of Object.entries(SCRIPT)) {
  seconds[key] = [];
  for (const [i, step] of steps.entries()) {
    const raw = (step.say ?? step.caption).trim();
    if (!raw) {
      seconds[key].push(null);
      continue;
    }
    const text = toReading(raw, READINGS, READING_RULES);
    const file = `${key}-${i}.wav`;
    used.add(file);
    const url = new URL(file, voiceDir);
    // USER_DICT を変えると全部の音声を作り直す（辞書は最初に決め、後の直しは READINGS で行う）
    const hash = createHash("sha256")
      .update(
        JSON.stringify({
          text,
          id: style.id,
          PARAMS,
          ...(USER_DICT.length ? { USER_DICT } : {}),
        }),
      )
      .digest("hex");
    const query = await (
      await engine(
        `/audio_query?speaker=${style.id}&text=${encodeURIComponent(text)}`,
        { method: "POST" },
      )
    ).json();
    kanaLines.push(`${file}\t${text}\n\t${query.kana}`);
    if (manifest[file] !== hash || !existsSync(url)) {
      const res = await engine(`/synthesis?speaker=${style.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...query, ...PARAMS }),
      });
      writeFileSync(url, Buffer.from(await res.arrayBuffer()));
      manifest[file] = hash;
      made++;
      console.log(`作成 ${file}`);
    }
    seconds[key].push(Math.round(wavSeconds(readFileSync(url)) * 1000) / 1000);
  }
}

// 台本から消えたステップの音声を消す
for (const f of readdirSync(voiceDir)) {
  if (f.endsWith(".wav") && !used.has(f)) {
    rmSync(new URL(f, voiceDir));
    delete manifest[f];
    console.log(`削除 ${f}`);
  }
}

writeFileSync(manifestUrl, JSON.stringify(manifest, null, 2));
writeFileSync(
  new URL(`out/voice-kana-${slug}.txt`, root),
  `${kanaLines.join("\n")}\n`,
);
writeFileSync(
  new URL(`src/videos/${slug}/voice.ts`, root),
  "// scripts/voice.ts が生成。手で編集しない。\n" +
    `export const VOICE_CREDIT = "VOICEVOX:${speaker.name}";\n` +
    `export const VOICE_SECONDS: Record<string, readonly (number | null)[]> = ${JSON.stringify(seconds, null, 2)};\n`,
);
const total = Object.values(seconds)
  .flat()
  .reduce<number>((a, b) => a + (b ?? 0), 0);
console.log(
  `作成 ${made} 件、読み上げの合計 ${total.toFixed(1)} 秒（${(total / 60).toFixed(1)} 分）`,
);
console.log(`読みの確認: out/voice-kana-${slug}.txt`);
