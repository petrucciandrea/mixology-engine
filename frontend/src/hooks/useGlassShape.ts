"use client";

import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";
import { blendShapes, shapeFor, type GlassShape } from "@/lib/glassShapes";
import type { GlassType } from "@/types/api";

const MORPH_MS = 300;

/**
 * La sagoma da disegnare per il bicchiere scelto, con il passaggio dalla
 * precedente.
 *
 * Il punto di partenza è la sagoma *mostrata*, non quella del bicchiere
 * precedente: se si cambia bicchiere a metà trasformazione, la nuova parte
 * da dov'è l'occhio invece di saltare indietro.
 */
export function useGlassShape(glass: GlassType | null): GlassShape {
  const reducedMotion = useReducedMotion();
  const [shape, setShape] = useState<GlassShape>(() => shapeFor(glass));
  const shownRef = useRef(shape);

  useEffect(() => {
    const target = shapeFor(glass);
    const origin = shownRef.current;
    if (reducedMotion || origin === target) {
      shownRef.current = target;
      setShape(target);
      return;
    }

    let frame = 0;
    let start = 0;
    const step = (now: number) => {
      if (start === 0) start = now;
      const linear = Math.min(1, (now - start) / MORPH_MS);
      // Uscita cubica: il grosso del cambiamento subito, l'assestamento dopo.
      const eased = 1 - (1 - linear) ** 3;
      const next = blendShapes(origin, target, eased);
      shownRef.current = next;
      setShape(next);
      if (linear < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [glass, reducedMotion]);

  return shape;
}
