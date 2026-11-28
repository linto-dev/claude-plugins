// 原稿の表を描き直す部品（shadcn/ui の Table）。行ごとに強調（focus）・薄く（dim）・取り消し線（strike）ができる。
// 行を出し入れする表は border-separate にして罫線をセルに付ける（border-collapse だと opacity で消した行の罫線が残る）。
import type React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { type FigureTone, mixColor, TONE_VAR } from "@/lib/palette";
import { TEXT_SIZE, type TextSize } from "@/lib/text";
import { cn } from "@/lib/utils";
import { Rich } from "./rich";

export const DataTable: React.FC<{
  head: readonly string[];
  rows: readonly (readonly string[])[];
  /** 列の幅（CSS の値。"30%"・"6em" など）。省略で自動 */
  widths?: readonly string[];
  /** 行（0 始まり）ごとの強調（0→1） */
  focus?: Record<number, number>;
  focusTone?: "mark" | FigureTone;
  /** 強調していない行の文字を薄くする度合い（0→1。1 で muted-foreground の色） */
  dim?: number;
  /** 行（0 始まり）ごとの出現（0→1）。省略で全部出す */
  show?: Record<number, number>;
  /** 行（0 始まり）ごとの取り消し線（0→1） */
  strike?: Record<number, number>;
  caption?: string;
  size?: TextSize;
  width?: number;
  className?: string;
  style?: React.CSSProperties;
}> = ({
  head,
  rows,
  widths,
  focus = {},
  focusTone = "mark",
  dim = 0,
  show,
  strike = {},
  caption,
  size = "lg",
  width,
  className,
  style,
}) => {
  const tint =
    focusTone === "mark" ? "var(--marker)" : TONE_VAR[focusTone].tint;
  return (
    <div className={className} style={{ width, ...style }}>
      <Table
        className={cn(
          "border-separate border-spacing-0 rounded-md border-3 border-figure-ink",
          TEXT_SIZE[size],
        )}
      >
        {widths ? (
          <colgroup>
            {widths.map((w, i) => (
              <col key={i} style={{ width: w }} />
            ))}
          </colgroup>
        ) : null}
        <TableHeader>
          <TableRow>
            {head.map((h) => (
              <TableHead
                key={h}
                className="h-auto border-b-3 border-figure-ink bg-muted px-4 py-2 text-foreground"
              >
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, r) => {
            const f = focus[r] ?? 0;
            const s = strike[r] ?? 0;
            return (
              <TableRow
                key={r}
                className="border-0"
                style={{
                  opacity: show ? (show[r] ?? 0) : 1,
                  background: mixColor(tint, f),
                  // 薄くするのは文字の色だけ（opacity で薄くすると 4.5:1 を下回る）
                  color: mixColor(
                    "var(--muted-foreground)",
                    dim * (1 - f),
                    "var(--foreground)",
                  ),
                }}
              >
                {row.map((cell, c) => (
                  <TableCell
                    key={c}
                    className={cn(
                      "relative px-4 py-2 leading-snug break-phrase whitespace-normal",
                      r < rows.length - 1 && "border-b border-figure-gray",
                    )}
                  >
                    <Rich text={cell} />
                    {s > 0 ? (
                      <span
                        className="absolute top-1/2 left-0 h-0.5 bg-foreground"
                        style={{ width: `${s * 100}%` }}
                      />
                    ) : null}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {caption ? (
        <div className="mt-2 text-center text-base font-bold">{caption}</div>
      ) : null}
    </div>
  );
};
