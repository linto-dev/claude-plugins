// shadcn/ui（base-vega）の separator を、動画向けに変えたもの（npx shadcn add separator で取り込んだ）。
// 動画向けに変えた点: transition・hover・focus-visible・aria-invalid を外した（Remotion はフレームごとに描く）。font-medium を font-bold にした。
import { Separator as SeparatorPrimitive } from "@base-ui/react/separator"
import { cn } from "@/lib/utils"

function Separator({
  className,
  orientation = "horizontal",
  ...props
}: SeparatorPrimitive.Props) {
  return (
    <SeparatorPrimitive
      data-slot="separator"
      orientation={orientation}
      className={cn(
        "shrink-0 bg-border data-horizontal:h-px data-horizontal:w-full data-vertical:w-px data-vertical:self-stretch",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
