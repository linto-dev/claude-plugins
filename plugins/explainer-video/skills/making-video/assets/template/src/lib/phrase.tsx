// 日本語を文節の境目で折り返すための部品。
// BudouX で文節の境目に <wbr> を入れ、親の break-phrase（src/styles/globals.css。word-break: keep-all）で <wbr>・空白・句読点の後でだけ改行させる。
// CSS の word-break: auto-phrase は Chrome の版で区切り方が変わるので使わない。
import { loadDefaultJapaneseParser } from "budoux";
import { Fragment } from "react";

const parser = loadDefaultJapaneseParser();
const cache = new Map<string, string[]>();

// 半角の語のあとの空白を改行しない空白に変える（「XSS 脆弱性」「p.5 の」を泣き別れにしない）。
// 英数字にはさまれたハイフンの前後にも改行しない文字（U+2060）を入れる（「図3-8」「a-sha」を切らない）。
export const keepTogether = (text: string) =>
  text
    .replace(/([\x21-\x7e]) (?=[^\s])/g, "$1 ")
    .replace(/([0-9A-Za-z])-(?=[0-9A-Za-z])/g, "$1⁠-⁠");

const phrases = (text: string) => {
  let hit = cache.get(text);
  if (!hit) {
    hit = parser.parse(text);
    cache.set(text, hit);
  }
  return hit;
};

/** 文節の境目に <wbr> を入れた文。親に break-phrase を付ける */
export const Phrase: React.FC<{ text: string }> = ({ text }) => (
  <>
    {phrases(keepTogether(text)).map((chunk, i) => (
      <Fragment key={i}>
        {i > 0 ? <wbr /> : null}
        {chunk}
      </Fragment>
    ))}
  </>
);
