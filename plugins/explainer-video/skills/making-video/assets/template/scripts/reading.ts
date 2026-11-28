// 読み上げの前に、VOICEVOX が読み違える書き方を読み方に置き換える（どの動画にも効く共通の表）。
// 台本の say に読み方で書くのが基本。ここはその取りこぼしを拾う安全網。動画だけの読み替えは script.ts の READINGS・READING_RULES に書く。
// 読みは out/voice-kana-<slug>.txt で確かめる。

const WORDS: [string, string][] = [
  ["https://", "エイチティーティーピーエス "],
  ["http://", "エイチティーティーピー "],
  ["Ver.", "バージョン"],
];

const RULES: [RegExp, string][] = [
  // 図3-2 → 図3の2、3-3〜3-9 → 3の3から3の9
  [/(\d)-(\d)〜(\d)-(\d)/g, "$1の$2から$3の$4"],
  [/(\d)-(\d)/g, "$1の$2"],
  // 問1(4) → 問1の4
  [/(\d)\((\d)\)/g, "$1の$2"],
  // p.4〜6 → 4から6ページ、p.5 → 5ページ
  [/p\.(\d+)〜(\d+)/g, "$1から$2ページ"],
  [/p\.(\d+)/g, "$1ページ"],
  [/〜/g, "から"],
  [/[→⇒]/g, "、"],
  [/↔/g, "と、"],
  [/＝/g, "は、"],
  // 値（あたい）を「ね」と読む。前が漢字・カタカナのとき（数値・ハッシュ値）は正しく読めるので置き換えない
  [/(?<![一-鿿ァ-ヶー])値(?![一-鿿])/g, "あたい"],
  // 日本語の前後の半角の空白は「、」の間として読まれるので取る（英字どうしの間の空白は残す）
  [/(?<=\P{ASCII}) +| +(?=\P{ASCII})/gu, ""],
];

// extra: 動画ごとの読み替え（READINGS）。共通の表と合わせて長い語から置き換える。
// rules: 動画ごとの正規表現の置き換え（READING_RULES）。共通の RULES の前にかける。
export const toReading = (
  text: string,
  extra: readonly [string, string][] = [],
  rules: readonly [RegExp, string][] = [],
) => {
  let out = text;
  for (const [from, to] of [...extra, ...WORDS].sort(
    (a, b) => b[0].length - a[0].length,
  ))
    out = out.split(from).join(to);
  for (const [re, to] of [...rules, ...RULES]) out = out.replace(re, to);
  return out;
};
