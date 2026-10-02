"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-[7px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        // L'arancio è riservato all'azione principale della pagina, che è
        // "Bilancia". Usarlo anche per salvare lo svuoterebbe di significato:
        // se tutto risalta, niente risalta.
        primary: "bg-accent font-semibold text-ink hover:bg-accent-strong",
        secondary:
          "bg-surface-2 font-semibold text-foreground shadow-[inset_0_0_0_1px_var(--color-outline)] hover:bg-line",
        outline: "border border-line bg-transparent text-foreground hover:bg-surface-2",
        ghost: "bg-transparent text-soft hover:bg-surface-2 hover:text-foreground",
      },
      size: {
        sm: "h-7 rounded-md px-2.5 text-[12.5px]",
        md: "h-9 px-3.5 text-[13.5px]",
        icon: "h-[30px] w-[30px] rounded-md text-lg leading-none",
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
  type = "button",
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      type={asChild ? undefined : type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
