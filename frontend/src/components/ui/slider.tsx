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
 *
 * La traccia prende il colore della famiglia dell'ingrediente: lo slider
 * di un distillato e quello di un succo si riconoscono senza leggere.
 *
 * `aria-label` va sul pollice, che è l'elemento con `role="slider"`: sulla
 * radice non darebbe un nome al controllo.
 */
export function Slider({
  className,
  rangeColor,
  "aria-label": ariaLabel,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root> & { rangeColor?: string }) {
  return (
    <SliderPrimitive.Root
      className={cn(
        "relative flex h-[18px] w-full cursor-grab touch-none select-none items-center active:cursor-grabbing",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-hover">
        <SliderPrimitive.Range
          className="absolute h-full rounded-full bg-accent"
          style={rangeColor !== undefined ? { backgroundColor: rangeColor } : undefined}
        />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        aria-label={ariaLabel}
        className="block h-[18px] w-1.5 rounded-[3px] bg-foreground transition-transform hover:scale-x-125 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" />
    </SliderPrimitive.Root>
  );
}
