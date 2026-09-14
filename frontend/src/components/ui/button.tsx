"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        // L'oro è riservato all'azione principale della pagina. Usarlo per
        // tutto lo svuoterebbe di significato: se tutto risalta, niente risalta.
        primary: "bg-accent text-ink hover:bg-accent-strong font-semibold",
        secondary: "bg-surface-2 text-foreground hover:bg-line border border-line",
        ghost: "text-muted hover:text-foreground hover:bg-surface-2",
        danger: "bg-alert-soft text-alert border border-alert/30 hover:bg-alert/15",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
