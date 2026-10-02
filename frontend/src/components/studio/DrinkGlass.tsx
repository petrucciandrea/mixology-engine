"use client";

import { useId, type CSSProperties, type ReactNode } from "react";

import {
  TALLEST_GLASS_PX,
  levelForFraction,
  sliceOutline,
  type GlassShape,
} from "@/lib/glassShapes";
import { formatMl } from "@/lib/utils";
import type { ServingIce } from "@/types/api";

/**
 * Il drink come volume, non come elenco.
 *
 * Il colore di ogni banda viene dalla famiglia merceologica, non da una
 * tavolozza arbitraria: un distillato è ambrato, un succo di agrume è
 * verde-giallo, un bitter è rosso. Chi conosce il bar riconosce la ricetta
 * dalla proporzione dei colori prima di leggere i nomi.
 *
 * Con un bicchiere dalla capienza nota il disegno è in scala: il liquido
 * sale fin dove il suo volume arriva, dentro la sagoma vera del vetro, e il
 * ghiaccio di servizio sposta il livello di quanto spazio occupa. Senza
 * capienza si riempie il bicchiere per intero e le bande mostrano solo le
 * proporzioni.
 */

export interface GlassBand {
  key: string;
  label: string;
  volumeMl: number;
  color: string;
  /** Acqua che nessuno versa (diluizione, fusione): si disegna più tenue. */
  isWater?: boolean;
}

interface DrinkGlassProps {
  shape: GlassShape;
  bands: readonly GlassBand[];
  /** Capienza a filo; `null` = disegno in proporzione, senza scala. */
  capacityMl: number | null;
  /** Il drink massimo ammesso e lo spazio del ghiaccio, dal backend. */
  maxVolumeMl: number | null;
  iceVolumeMl: number;
  iceType: ServingIce;
  /** Frazione del ghiaccio non ancora fusa, in [0, 1]. */
  iceRemaining: number;
  overflows: boolean;
  bubbles: boolean;
  width: number;
  ariaLabel: string;
}

const VIEW_WIDTH = 190;
const VIEW_BOTTOM = 238;
/** Dove poggia il piede (o il fondo, se non c'è stelo). */
const BASELINE_Y = 226;
/** Il disegno parte dal bordo del bicchiere più alto, più il margine per
    lo spessore del contorno: tutti i bicchieri condividono scala e piano
    d'appoggio, e lo spazio sopra resta solo dove il vetro è più basso. */
const VIEW_TOP = BASELINE_Y - TALLEST_GLASS_PX - 4;
const VIEW_HEIGHT = VIEW_BOTTOM - VIEW_TOP;
const CENTRE_X = VIEW_WIDTH / 2;
const OUTLINE = "#4a5852";

/** Lato del cubetto, in unità del viewBox, a ghiaccio intatto. */
const ICE_SIZE: Record<Exclude<ServingIce, "NONE">, number> = {
  CUBES: 24,
  LARGE_CUBE: 52,
  CRUSHED: 8,
};

/** Pseudo-casuale deterministico: il ghiaccio non deve ridisporsi a ogni
    render, o tremerebbe mentre si muove uno slider. */
function jitter(index: number): number {
  const x = Math.sin(index * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

export function DrinkGlass({
  shape,
  bands,
  capacityMl,
  maxVolumeMl,
  iceVolumeMl,
  iceType,
  iceRemaining,
  overflows,
  bubbles,
  width,
  ariaLabel,
}: DrinkGlassProps) {
  // `useId` produce caratteri (":", "«") che dentro `url(#…)` andrebbero
  // sfuggiti: si tengono solo quelli sicuri, l'unicità resta.
  const id = `glass${useId().replace(/[^\w-]/g, "")}`;
  const bowlBottom = BASELINE_Y - shape.stemPx;
  const visible = bands.filter((band) => band.volumeMl > 0.01);
  const liquid = visible.reduce((sum, band) => sum + band.volumeMl, 0);

  const sized = capacityMl !== null;
  const capacity = sized ? capacityMl : liquid || 1;
  const iceMl = iceType !== "NONE" && sized ? iceVolumeMl * iceRemaining : 0;
  const filled = liquid + iceMl;
  // Oltre il bordo il disegno si ferma al vetro: le bande si riscalano
  // invece di uscire dalla sagoma. Il ghiaccio, poi, alza il livello: le
  // bande si allungano di quanto il solido sposta.
  const scale = (filled > capacity ? capacity / filled : 1) * (liquid > 0 ? filled / liquid : 1);

  let poured = 0;
  const geometry = visible.map((band) => {
    const from = levelForFraction(shape, (poured * scale) / capacity);
    poured += band.volumeMl;
    const to = levelForFraction(shape, (poured * scale) / capacity);
    return { band, from, to, path: sliceOutline(shape, from, to, CENTRE_X, bowlBottom) };
  });

  const top = geometry.length > 0 ? geometry[geometry.length - 1]!.to : 0;
  const topY = bowlBottom - top * shape.heightPx;
  const halfWidthAt = (t: number) => (shape.width(Math.min(1, t)) * shape.widthPx) / 2;
  const glassPath = sliceOutline(shape, 0, 1, CENTRE_X, bowlBottom);

  const inner: ReactNode[] = [
    <path key="body" d={glassPath} fill={`url(#${id}-body)`} />,
    ...geometry.map(({ band, path }) => (
      <path
        key={band.key}
        d={path}
        fill={band.color}
        fillOpacity={band.isWater ? 0.65 : 0.92}
      />
    )),
    ...geometry.slice(0, -1).map(({ band, to }) => {
      const y = bowlBottom - to * shape.heightPx;
      const half = halfWidthAt(to);
      return (
        <line
          key={`sep-${band.key}`}
          x1={CENTRE_X - half}
          x2={CENTRE_X + half}
          y1={y}
          y2={y}
          stroke="#000"
          strokeOpacity={0.28}
          strokeWidth={0.6}
        />
      );
    }),
  ];

  if (top > 0) {
    inner.push(
      <rect
        key="shade"
        x={CENTRE_X - shape.widthPx / 2}
        width={shape.widthPx}
        y={topY}
        height={bowlBottom - topY}
        fill={`url(#${id}-shade)`}
      />,
    );
  }

  if (iceMl > 0 && iceType !== "NONE") {
    inner.push(...iceCubes(shape, iceType, iceRemaining, top, bowlBottom));
  }

  if (bubbles && top > 0.05) {
    inner.push(...risingBubbles(shape, top, topY, bowlBottom));
  }

  if (top > 0) {
    const half = halfWidthAt(top);
    inner.push(
      <line
        key="meniscus"
        x1={CENTRE_X - half + 1}
        x2={CENTRE_X + half - 1}
        y1={topY}
        y2={topY}
        stroke="#fff"
        strokeOpacity={0.3}
        strokeWidth={0.8}
      />,
    );
  }

  // Il tetto del bicchiere: dove arriva il drink massimo ammesso insieme al
  // suo ghiaccio. È il limite che il solver rispetta, non il bordo.
  const ceilingMl = sized && maxVolumeMl !== null ? maxVolumeMl + iceVolumeMl : null;
  const ceilingLevel = ceilingMl === null ? null : levelForFraction(shape, ceilingMl / capacity);

  return (
    <svg
      viewBox={`0 ${VIEW_TOP} ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      width={width}
      height={(width * VIEW_HEIGHT) / VIEW_WIDTH}
      className="block h-auto max-w-full overflow-visible"
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        <clipPath id={`${id}-clip`}>
          <path d={glassPath} />
        </clipPath>
        <linearGradient id={`${id}-shade`} x1={0} x2={1} y1={0} y2={0}>
          <stop offset={0} stopColor="#fff" stopOpacity={0.1} />
          <stop offset={0.35} stopColor="#fff" stopOpacity={0} />
          <stop offset={1} stopColor="#000" stopOpacity={0.28} />
        </linearGradient>
        <linearGradient id={`${id}-body`} x1={0} x2={0} y1={0} y2={1}>
          <stop offset={0} stopColor="#fff" stopOpacity={0.035} />
          <stop offset={1} stopColor="#fff" stopOpacity={0.01} />
        </linearGradient>
      </defs>

      <g clipPath={`url(#${id}-clip)`}>{inner}</g>

      <path
        d={glassPath}
        fill="none"
        stroke={overflows ? "#f87171" : OUTLINE}
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
      {shape.stemPx > 0.5 && (
        <>
          <line
            x1={CENTRE_X}
            x2={CENTRE_X}
            y1={bowlBottom}
            y2={BASELINE_Y}
            stroke={OUTLINE}
            strokeWidth={1.5}
          />
          <line
            x1={CENTRE_X - shape.footPx / 2}
            x2={CENTRE_X + shape.footPx / 2}
            y1={BASELINE_Y}
            y2={BASELINE_Y}
            stroke={OUTLINE}
            strokeWidth={1.5}
            strokeLinecap="round"
          />
        </>
      )}

      {ceilingLevel !== null && maxVolumeMl !== null && (
        <line
          x1={CENTRE_X - halfWidthAt(ceilingLevel)}
          x2={CENTRE_X + halfWidthAt(ceilingLevel)}
          y1={bowlBottom - ceilingLevel * shape.heightPx}
          y2={bowlBottom - ceilingLevel * shape.heightPx}
          stroke="#34d399"
          strokeWidth={1}
          strokeDasharray="3 3"
        >
          <title>
            {`Volume massimo ammesso: ${formatMl(maxVolumeMl)} ml di drink`}
            {iceVolumeMl > 0 ? ` più ${formatMl(iceVolumeMl)} ml di ghiaccio` : ""}
          </title>
        </line>
      )}
    </svg>
  );
}

/**
 * I pezzi di ghiaccio, a file sfalsate dal fondo fino a poco sopra il
 * liquido. Si rimpiccioliscono con la radice cubica della quota rimasta:
 * è il volume che fonde, il lato cala più lentamente.
 */
function iceCubes(
  shape: GlassShape,
  iceType: Exclude<ServingIce, "NONE">,
  remaining: number,
  top: number,
  bowlBottom: number,
): ReactNode[] {
  const cubes: ReactNode[] = [];
  const size = ICE_SIZE[iceType] * Math.cbrt(Math.max(0.05, remaining));
  const ceiling = Math.min(Math.max(top + (size * 0.45) / shape.heightPx, 0.12), 0.97);
  const isLarge = iceType === "LARGE_CUBE";
  const isCrushed = iceType === "CRUSHED";

  let y = bowlBottom - 1;
  let index = 0;
  for (let row = 0; row < 60; row++) {
    const level = Math.min(1, (bowlBottom - (y - size / 2)) / shape.heightPx);
    if (level > ceiling) break;

    const span = shape.width(level) * shape.widthPx;
    // Il cubo grosso è uno solo, e non può essere più largo del vetro.
    const side = isLarge ? Math.min(size, span * 0.78) : size;
    const half = isLarge ? 0 : span / 2 - side * 0.55;
    const count = isLarge ? 1 : Math.max(0, Math.floor((2 * half) / (side * 1.04)) + 1);

    if (count >= 1 && half >= 0) {
      const offset = row % 2 === 1 ? side * 0.22 : -side * 0.18;
      for (let k = 0; k < count; k++) {
        const inner = k > 0 && k < count - 1;
        const x =
          count > 1 ? CENTRE_X - half + (2 * half * k) / (count - 1) + (inner ? offset : 0) : CENTRE_X;
        const rotation = (jitter(index) - 0.5) * (isCrushed ? 80 : 22);
        const aboveLiquid = bowlBottom - (y - side / 2) > top * shape.heightPx;
        const height = side * (isCrushed ? 0.7 + jitter(index + 9) * 0.5 : 1);
        cubes.push(
          <rect
            key={`ice-${index}`}
            x={x - side / 2}
            y={y - side}
            width={side}
            height={height}
            rx={side * 0.2}
            transform={`rotate(${rotation.toFixed(1)} ${x.toFixed(1)} ${(y - side / 2).toFixed(1)})`}
            fill="#dcebf0"
            fillOpacity={aboveLiquid ? 0.2 : 0.13}
            stroke="#e6f1f5"
            strokeOpacity={aboveLiquid ? 0.6 : 0.42}
            strokeWidth={0.8}
          />,
        );
        index++;
      }
    }
    if (isLarge) break;
    y -= side * 0.9;
  }
  return cubes;
}

/** Bollicine per spritz e sparkling: salgono dal fondo fino al livello. */
function risingBubbles(
  shape: GlassShape,
  top: number,
  topY: number,
  bowlBottom: number,
): ReactNode[] {
  const lowY = bowlBottom - 3;
  const rise = Math.max(4, lowY - topY - 2);
  return Array.from({ length: 16 }, (_, i) => {
    const level = Math.min(0.15 + jitter(i + 40) * 0.5, top);
    const half = (shape.width(level) * shape.widthPx) / 2;
    const style = {
      "--rise": `${-rise}px`,
      opacity: 0,
      animation: `mx-rise ${(1.6 + (i % 5) * 0.4).toFixed(2)}s linear ${(-(i * 0.43) % 2.4).toFixed(2)}s infinite`,
    } as CSSProperties;
    return (
      <circle
        key={`bubble-${i}`}
        className="mx-loop"
        cx={CENTRE_X + (jitter(i + 3) - 0.5) * half * 1.4}
        cy={lowY}
        r={0.8 + jitter(i + 7) * 1.1}
        fill="none"
        stroke="#fff"
        strokeOpacity={0.65}
        strokeWidth={0.6}
        style={style}
      />
    );
  });
}
