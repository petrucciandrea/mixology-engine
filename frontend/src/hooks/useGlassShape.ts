"use client";

import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";
import { blendShapes, type GlassShape } from "@/lib/glassShapes";

const MORPH_MS = 300;

/**
 * La sagoma da disegnare, con il passaggio dalla precedente. `target` deve
 * avere un'identità stabile per lo stesso bicchiere (`shapeFor`,
 * `shapeForModel` la garantiscono), o la trasformazione ripartirebbe a ogni
 * render.
 *
 * Il punto di partenza è la sagoma *mostrata*, non quella del bicchiere
 * precedente: se si cambia bicchiere a metà trasformazione, la nuova parte
 * da dov'è l'occhio invece di saltare indietro.
 */
export function useGlassShape(target: GlassShape): GlassShape {
  const reducedMotion = useReducedMotion();
  const [shape, setShape] = useState<GlassShape>(target);
  const shownRef = useRef(shape);

  useEffect(() => {
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
  }, [target, reducedMotion]);

  return shape;
}
