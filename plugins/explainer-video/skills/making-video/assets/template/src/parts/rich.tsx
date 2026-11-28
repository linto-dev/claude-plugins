// 字幕以外の本文（引用・カード・手順・コード）に使う簡単な記法。
//   {{…}}   マーカー（出てくる順に 0, 1, 2…。marks[i] が 0→1 で左から引かれる）
//   __…__   下線（原稿の下線①など）
//   !!…!!   注意・危険の語（朱）
//   ``…``   等幅（本文中のコード・コマンド・値）
//   [[a]]   空欄（fills に答えを渡すと緑の文字で埋まる）。英小文字 1 字と α・β・γ
// {{…}} の中に __…__ は書けるが、__…__ の中に {{…}} は書けない（下線を分けて書く）。
import type React from "react";
import { Fragment } from "react";
import { Phrase } from "@/lib/phrase";
import { TEXT_SIZE, type TextSize } from "@/lib/text";
import { cn } from "@/lib/utils";

export type RichOpts = {
  marks?: readonly number[];
  fills?: Partial<Record<string, { text: React.ReactNode; p: number }>>;
  /** マーカーの色（CSS の色。既定は --marker）。図の色なら TONE_VAR.<tone>.tint */
  markColor?: string;
  blankSize?: TextSize;
  /** 文節の境目で折り返す（コードでは false） */
  phrase?: boolean;
};

const TOKEN =
  /(\[\[[a-zα-γ]\]\]|\{\{[\s\S]*?\}\}|__[\s\S]*?__|!![\s\S]*?!!|``[\s\S]*?``)/g;

export const Rich: React.FC<{ text: string } & RichOpts> = ({
  text,
  marks = [],
  fills = {},
  markColor,
  blankSize,
  phrase = true,
}) => {
  let mi = 0;
  const parts = text.split(TOKEN);
  const plain = (s: string) => (phrase ? <Phrase text={s} /> : s);
  return (
    <>
      {parts.map((part, i) => {
        if (!part) return null;
        if (part.startsWith("[[")) {
          const id = part.slice(2, -2);
          return <Blank key={i} id={id} fill={fills[id]} size={blankSize} />;
        }
        if (part.startsWith("{{")) {
          const m = marks[mi++] ?? 0;
          return (
            <Mark key={i} p={m} color={markColor}>
              <Rich
                text={part.slice(2, -2)}
                fills={fills}
                blankSize={blankSize}
                phrase={phrase}
              />
            </Mark>
          );
        }
        if (part.startsWith("__")) {
          return (
            <span key={i} className="underline decoration-3 underline-offset-6">
              {plain(part.slice(2, -2))}
            </span>
          );
        }
        if (part.startsWith("!!")) {
          return (
            <span key={i} className="font-bold text-figure-vermillion-text">
              {plain(part.slice(2, -2))}
            </span>
          );
        }
        if (part.startsWith("``")) {
          return (
            <span key={i} className="font-mono">
              {part.slice(2, -2)}
            </span>
          );
        }
        return <Fragment key={i}>{plain(part)}</Fragment>;
      })}
    </>
  );
};

/** 蛍光ペンのマーカー。p（0→1）で左から右へ引かれる */
export const Mark: React.FC<{
  p: number;
  color?: string;
  children: React.ReactNode;
}> = ({ p, color = "var(--marker)", children }) => (
  <span
    className="rounded-sm box-decoration-clone bg-no-repeat"
    style={{
      backgroundImage: `linear-gradient(${color}, ${color})`,
      backgroundSize: `${Math.max(0, Math.min(1, p)) * 100}% 72%`,
      backgroundPosition: "0 75%",
    }}
  >
    {children}
  </span>
);

/** 空欄 [ a ]。答えが入ると緑の文字に置き換わる */
export const Blank: React.FC<{
  id: string;
  fill?: { text: React.ReactNode; p: number };
  size?: TextSize;
}> = ({ id, fill, size }) => {
  const p = fill?.p ?? 0;
  return (
    <span
      className={cn(
        "mx-1 inline-grid indent-0 align-baseline",
        size && TEXT_SIZE[size],
      )}
    >
      <span
        className="col-start-1 row-start-1 inline-flex min-w-[3.2em] items-center justify-center rounded-sm border-3 border-foreground bg-card px-[0.5em] font-sans text-[0.8em] leading-snug font-bold"
        style={{ opacity: 1 - p }}
      >
        {id}
      </span>
      {fill ? (
        <span
          className="col-start-1 row-start-1 rounded-sm bg-figure-green-tint px-[0.3em] font-bold whitespace-nowrap text-figure-green-text"
          style={{ opacity: p, translate: `0 ${(1 - p) * 9}px` }}
        >
          {fill.text}
        </span>
      ) : null}
    </span>
  );
};
