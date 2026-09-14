import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[0.65rem] uppercase tracking-[0.08em] whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "bg-surface-2 text-muted border border-line-soft",
        good: "bg-good-soft text-good",
        alert: "bg-alert-soft text-alert",
        accent: "bg-accent-soft text-accent",
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
