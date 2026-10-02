import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-[3px] font-mono text-[11px] font-medium uppercase leading-none",
  {
    variants: {
      tone: {
        neutral: "bg-surface-2 text-soft",
        good: "bg-good-soft text-good",
        alert: "bg-alert-soft text-alert",
        accent: "bg-accent-soft text-accent-strong",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
