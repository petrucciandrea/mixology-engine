"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import type { ReactNode } from "react";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { ServingProfile } from "@/types/api";

/** Geometria del grafico, in unità del viewBox. I margini laterali
    ospitano le due scale: temperatura a sinistra, ABV a destra. */
const WIDTH = 380;
const HEIGHT = 230;
const LEFT = 40;
const RIGHT = 44;
const TOP = 14;
const BOTTOM = 26;
const PLOT_WIDTH = WIDTH - LEFT - RIGHT;
const PLOT_HEIGHT = HEIGHT - TOP - BOTTOM;

/** Scala fissa della temperatura, allargata solo se un drink ne esce: così
    due drink si confrontano a colpo d'occhio, e un built a 20 °C ci sta. */
const TEMPERATURE_RANGE: [number, number] = [-12, 22];

const ABV_COLOR = "#e8812b";
const TEMPERATURE_COLOR = "#8fb3c0";

interface DilutionCurveProps {
  /** Il drink minuto per minuto dal servizio; `null` senza ghiaccio. */
  curve: ServingProfile[] | null;
  /** Il profilo di servizio di riferimento (10 minuti, dal backend). */
  reference: ServingProfile | null;
  minutes: number;
  onMinutesChange: (minutes: number) => void;
  hasDoses: boolean;
}

/**
 * Cosa succede al drink mentre lo si beve.
 *
 * Le due curve si leggono insieme: un built su ghiaccio crolla di
 * temperatura nel primo minuto e poi si diluisce lentamente, uno shakerato
 * parte già freddo e si annacqua soltanto. Trascinando sul grafico si
 * sceglie il minuto, e il bicchiere accanto mostra ghiaccio e acqua di
 * fusione a quel punto. Ogni numero viene dal modello del backend: qui si
 * disegna e basta.
 */
export function DilutionCurve({
  curve,
  reference,
  minutes,
  onMinutesChange,
  hasDoses,
}: DilutionCurveProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Diluizione nel tempo</CardTitle>
        <span className="flex gap-3 font-mono text-xs" aria-hidden>
          <span className="text-accent-light">— ABV</span>
          <span className="text-cold">— °C</span>
        </span>
      </CardHeader>
      <div className="px-3 pb-3.5 pt-2.5">
        {curve !== null && curve.length > 1 ? (
          <Chart
            curve={curve}
            reference={reference}
            minutes={minutes}
            onMinutesChange={onMinutesChange}
          />
        ) : (
          <p className="px-1.5 py-[18px] text-center text-[13px] leading-normal text-muted">
            {hasDoses
              ? "Servito senza ghiaccio: la diluizione si ferma alla preparazione, non c'è curva di servizio."
              : "La curva compare con il primo ingrediente, se il drink è servito su ghiaccio."}
          </p>
        )}
      </div>
    </Card>
  );
}

function Chart({
  curve,
  reference,
  minutes,
  onMinutesChange,
}: {
  curve: ServingProfile[];
  reference: ServingProfile | null;
  minutes: number;
  onMinutesChange: (minutes: number) => void;
}) {
  const first = curve[0]!;
  const last = curve[curve.length - 1]!;
  const step = curve[1]!.consumption_minutes - first.consumption_minutes;
  const span = last.consumption_minutes;
  const at = (time: number) =>
    curve[Math.min(curve.length - 1, Math.max(0, Math.round(time / step)))]!;
  const point = at(minutes);

  const temperatures = curve.map((sample) => sample.temperature_c);
  const tMin = Math.min(TEMPERATURE_RANGE[0], Math.floor(Math.min(...temperatures)));
  const tMax = Math.max(TEMPERATURE_RANGE[1], Math.ceil(Math.max(...temperatures)));
  // L'ABV scende sempre: la scala parte dal valore al servizio, con un
  // margine, arrotondata a multipli di 5 punti.
  const abvMax = Math.max(5, Math.ceil((first.abv * 100 * 1.12) / 5) * 5);

  const x = (time: number) => LEFT + (time / span) * PLOT_WIDTH;
  const yTemperature = (celsius: number) =>
    TOP + PLOT_HEIGHT * (1 - (celsius - tMin) / (tMax - tMin));
  const yAbv = (fraction: number) => TOP + PLOT_HEIGHT * (1 - (fraction * 100) / abvMax);

  const line = (y: (sample: ServingProfile) => number) =>
    curve
      .map(
        (sample, i) =>
          `${i === 0 ? "M" : "L"}${x(sample.consumption_minutes).toFixed(1)} ${y(sample).toFixed(1)}`,
      )
      .join(" ");
  const abvLine = line((sample) => yAbv(sample.abv));
  const temperatureLine = line((sample) => yTemperature(sample.temperature_c));

  const grid: ReactNode[] = [];
  for (let i = 0; i <= 4; i++) {
    const y = TOP + (PLOT_HEIGHT * i) / 4;
    grid.push(
      <line key={`g${i}`} x1={LEFT} x2={LEFT + PLOT_WIDTH} y1={y} y2={y} stroke="#253029" />,
      <text key={`t${i}`} x={LEFT - 6} y={y + 4} textAnchor="end" fontSize={11} fill="#9fb9c4">
        {Math.round(tMax - ((tMax - tMin) * i) / 4)}°
      </text>,
      <text key={`a${i}`} x={LEFT + PLOT_WIDTH + 6} y={y + 4} fontSize={11} fill="#f0a868">
        {(abvMax - (abvMax * i) / 4).toFixed(abvMax % 4 === 0 ? 0 : 1)}%
      </text>,
    );
  }
  const ticks: ReactNode[] = [];
  for (let time = 0; time <= span; time += 5) {
    ticks.push(
      <text
        key={`x${time}`}
        x={x(time)}
        y={HEIGHT - 8}
        textAnchor="middle"
        fontSize={11}
        fill="#a9b4ae"
      >
        {time}
        {time + 5 > span ? " min" : ""}
      </text>,
    );
  }

  const marker = (sample: ServingProfile, strong: boolean) => {
    const xx = x(sample.consumption_minutes);
    const r = strong ? 4 : 3;
    return (
      <g key={strong ? "cursor" : "reference"}>
        <line
          x1={xx}
          x2={xx}
          y1={TOP}
          y2={TOP + PLOT_HEIGHT}
          stroke={strong ? "#e8ede9" : "#56655e"}
          strokeOpacity={strong ? 0.6 : 1}
          strokeDasharray={strong ? undefined : "3 3"}
        />
        <circle cx={xx} cy={yAbv(sample.abv)} r={r} fill="#0b0e0d" stroke={ABV_COLOR} strokeWidth={2} />
        <circle
          cx={xx}
          cy={yTemperature(sample.temperature_c)}
          r={r}
          fill="#0b0e0d"
          stroke={TEMPERATURE_COLOR}
          strokeWidth={2}
        />
      </g>
    );
  };

  return (
    <>
      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="block h-auto w-full font-mono"
          role="img"
          aria-label={`Curva di diluizione: da ${first.temperature_c.toFixed(1)} °C e ${(first.abv * 100).toFixed(1)}% a ${last.temperature_c.toFixed(1)} °C e ${(last.abv * 100).toFixed(1)}% dopo ${span} minuti`}
        >
          <defs>
            <linearGradient id="dilution-abv-area" x1={0} x2={0} y1={0} y2={1}>
              <stop offset={0} stopColor={ABV_COLOR} stopOpacity={0.26} />
              <stop offset={1} stopColor={ABV_COLOR} stopOpacity={0} />
            </linearGradient>
          </defs>
          {grid}
          {ticks}
          {tMin < 0 && tMax > 0 && (
            <line
              x1={LEFT}
              x2={LEFT + PLOT_WIDTH}
              y1={yTemperature(0)}
              y2={yTemperature(0)}
              stroke="#3a4742"
              strokeDasharray="2 3"
            />
          )}
          <path
            d={`${abvLine} L${x(span)} ${TOP + PLOT_HEIGHT} L${LEFT} ${TOP + PLOT_HEIGHT} Z`}
            fill="url(#dilution-abv-area)"
          />
          <path d={abvLine} fill="none" stroke={ABV_COLOR} strokeWidth={2} strokeLinejoin="round" />
          <path
            d={temperatureLine}
            fill="none"
            stroke={TEMPERATURE_COLOR}
            strokeWidth={2}
            strokeLinejoin="round"
          />
          {reference !== null && reference.consumption_minutes <= span && marker(reference, false)}
          {minutes > 0 && marker(point, true)}
        </svg>

        {/* Il cursore copre l'area del grafico: si trascina sulla curva, non
            su una barra a parte. Il pollice è invisibile finché non ha il
            fuoco da tastiera: la posizione la mostra già il grafico. */}
        <SliderPrimitive.Root
          className="absolute flex cursor-ew-resize touch-none select-none items-center"
          style={{
            left: `${(LEFT / WIDTH) * 100}%`,
            right: `${(RIGHT / WIDTH) * 100}%`,
            top: 0,
            bottom: `${(BOTTOM / HEIGHT) * 100}%`,
          }}
          min={0}
          max={span}
          step={step}
          value={[minutes]}
          onValueChange={([next]) => {
            if (next !== undefined) onMinutesChange(next);
          }}
        >
          <SliderPrimitive.Track className="relative h-full w-full" />
          <SliderPrimitive.Thumb
            aria-label="Minuti nel bicchiere"
            aria-valuetext={`${point.consumption_minutes} minuti`}
            className="block h-3 w-3 rounded-full opacity-0 focus-visible:bg-foreground focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          />
        </SliderPrimitive.Root>
      </div>

      <dl className="mt-2 grid grid-cols-4 gap-2 rounded-lg border border-line-soft bg-recess p-2.5">
        <Reading label="Minuto" value={point.consumption_minutes.toFixed(0)} />
        <Reading
          label="ABV"
          value={`${(point.abv * 100).toFixed(1)}%`}
          className="text-accent-strong"
        />
        <Reading label="Temp." value={`${point.temperature_c.toFixed(1)}°`} className="text-cold" />
        <Reading label="Fusione" value={`+${point.melt_water_ml.toFixed(1)}`} unit="ml" />
      </dl>

      <p className="mx-0.5 mt-2 text-[12.5px] leading-normal text-muted">
        Trascina sulla curva: il bicchiere mostra ghiaccio e acqua di fusione al minuto
        scelto.
        {reference !== null &&
          ` Profilo di servizio a ${reference.consumption_minutes.toFixed(0)} min: ${(reference.abv * 100).toFixed(1)}% · ${reference.final_volume_ml.toFixed(1)} ml.`}
      </p>
    </>
  );
}

function Reading({
  label,
  value,
  unit,
  className,
}: {
  label: string;
  value: string;
  unit?: string;
  className?: string;
}) {
  return (
    <div>
      <dt className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
        {label}
      </dt>
      <dd className={`tabular mt-[3px] font-mono text-[17px] font-medium ${className ?? ""}`}>
        {value}
        {unit !== undefined && <span className="text-xs text-muted"> {unit}</span>}
      </dd>
    </div>
  );
}
