// shadcn/ui（base-vega）の badge を、動画向けに変えたもの（npx shadcn add badge で取り込んだ）。
// 動画向けに変えた点:
// - transition・hover・focus-visible・aria-invalid を外した（Remotion はフレームごとに描く）
// - 太さを font-medium → font-bold にした
// - 図の色の variant（blue・vermillion・green・ink）と、マーカーの variant（marker）を足した
// - 動画の文字の大きさの size を足した（h-5・text-xs は外した）
import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "group/badge inline-flex w-fit shrink-0 items-center justify-center overflow-hidden whitespace-nowrap rounded-4xl border border-transparent font-bold [&>svg]:pointer-events-none",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground",
        secondary: "bg-secondary text-secondary-foreground",
        outline: "border-border bg-background text-foreground",
        // 解説の要点（マーカーと同じ淡い黄色）
        marker: "bg-marker text-marker-foreground",
        // 図の色（Okabe-Ito）。淡色の地に、同じ色相の文字と線
        blue: "border-figure-blue bg-figure-blue-tint text-figure-blue-text",
        vermillion:
          "border-figure-vermillion bg-figure-vermillion-tint text-figure-vermillion-text",
        green: "border-figure-green bg-figure-green-tint text-figure-green-text",
        // 番号など、黒地に白抜き
        ink: "bg-foreground text-background",
      },
      size: {
        sm: "gap-1 px-2 py-0.5 text-sm",
        base: "gap-1 px-3 py-0.5 text-base",
        lg: "gap-2 px-3 py-1 text-lg",
        xl: "gap-2 px-4 py-1 text-xl",
        "2xl": "gap-2 px-4 py-1.5 text-2xl",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "base",
    },
  },
);

function Badge({
  className,
  variant = "default",
  size = "base",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant, size }), className),
      },
      props,
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  });
}

export { Badge };
