"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Slider su primitiva Radix invece che su `<input type="range">`.
 *
 * Non è una preferenza estetica: Radix porta con sé la navigazione da
 * tastiera, i ruoli ARIA e il comportamento al trascinamento fuori dai
 * bordi. Riscriverli a mano significa, nella pratica, dimenticarne metà.
 */
export function Slider({
  className,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root
      className={cn("relative flex w-full touch-none select-none items-center", className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1 w-full grow overflow-hidden rounded-full bg-line">
        <SliderPrimitive.Range className="absolute h-full bg-accent" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb className="block h-4 w-4 rounded-full border-2 border-accent bg-ink transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-ink" />
    </SliderPrimitive.Root>
  );
}
