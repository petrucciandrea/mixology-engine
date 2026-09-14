"use client";

import { useMemo } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import type { Dose } from "@/hooks/useRecipe";

/**
 * Il profilo organolettico della miscela.
 *
 * L'aggregazione è fatta qui e non sul backend perché è una scelta di
 * *rappresentazione*, non di dominio: il modello non definisce cosa sia il
 * "sapore di una miscela", e inventarlo nel dominio significherebbe dargli
 * un'autorità che non ha. La regola usata è la più semplice difendibile —
 * media delle intensità pesata sulla quota di volume di ciascun
 * ingrediente — ed è dichiarata sotto il grafico, così chi guarda sa cosa
 * sta leggendo.
 *
 * Un limite noto: 30 ml di un liquore intensamente aromatico pesano quanto
 * 30 ml di acqua, mentre in bocca non è così. Una pesatura per intensità
 * percepita richiederebbe dati che non abbiamo.
 */

/** Quanti assi mostrare. Un radar a 32 punte è illeggibile: si tengono i
    descrittori più presenti, che sono poi quelli che definiscono il drink. */
const MAX_AXES = 8;

/** Sotto questa intensità un descrittore è rumore di compilazione, non un
    carattere del drink. */
const PRESENCE_FLOOR = 0.02;

const LABELS: Record<string, string> = {
  sweet: "dolce",
  sour: "acido",
  bitter: "amaro",
  salty: "sapido",
  umami: "umami",
  alcohol_heat: "calore",
  astringency: "astringente",
  cooling: "fresco",
  pungency: "pungente",
  citrus: "agrumato",
  orchard_fruit: "pomacee",
  stone_fruit: "drupacee",
  berry: "bacche",
  tropical_fruit: "tropicale",
  dried_fruit: "frutta secca",
  floral: "floreale",
  herbaceous: "erbaceo",
  mint: "menta",
  anise: "anice",
  resinous: "resinoso",
  pepper: "pepe",
  warm_spice: "spezie dolci",
  earthy: "terroso",
  woody: "legno",
  vanilla: "vaniglia",
  caramel: "caramello",
  smoke: "affumicato",
  roasted: "tostato",
  nutty: "nocciolato",
  honey: "miele",
  funky: "fermentato",
  medicinal: "medicinale",
};

interface FlavorRadarProps {
  doses: Dose[];
}

export function FlavorRadar({ doses }: FlavorRadarProps) {
  const data = useMemo(() => {
    const totalVolume = doses.reduce((sum, dose) => sum + dose.volumeMl, 0);
    if (totalVolume === 0) return [];

    const blended = new Map<string, number>();
    for (const dose of doses) {
      const profile = dose.ingredient.flavor_profile;
      if (profile === null) continue;
      const share = dose.volumeMl / totalVolume;
      for (const [descriptor, intensity] of Object.entries(profile)) {
        blended.set(descriptor, (blended.get(descriptor) ?? 0) + intensity * share);
      }
    }

    return [...blended.entries()]
      .filter(([, intensity]) => intensity >= PRESENCE_FLOOR)
      .sort((left, right) => right[1] - left[1])
      .slice(0, MAX_AXES)
      // Riordinati per nome: senza, gli assi si riorganizzerebbero a ogni
      // movimento di slider e il grafico "salterebbe" invece di deformarsi.
      .sort((left, right) => left[0].localeCompare(right[0]))
      .map(([descriptor, intensity]) => ({
        descriptor: LABELS[descriptor] ?? descriptor,
        intensity: Number(intensity.toFixed(3)),
      }));
  }, [doses]);

  const hasProfiles = doses.some((dose) => dose.ingredient.flavor_profile !== null);

  if (!hasProfiles || data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted">
        {doses.length === 0
          ? "Il profilo aromatico compare con il primo ingrediente."
          : "Nessuno degli ingredienti scelti ha un profilo organolettico."}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="72%">
            <PolarGrid stroke="#253029" />
            <PolarAngleAxis
              dataKey="descriptor"
              tick={{ fill: "#8a9690", fontSize: 10 }}
            />
            {/* L'asse radiale è fisso da 0 a 1: se si adattasse ai dati, due
                drink di intensità molto diversa disegnerebbero la stessa
                forma e il confronto perderebbe senso. */}
            <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
            <Radar
              dataKey="intensity"
              stroke="#d9a441"
              fill="#d9a441"
              fillOpacity={0.28}
              isAnimationActive={false}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-center text-[0.68rem] leading-relaxed text-muted">
        Intensità dei descrittori, pesate sulla quota di volume. Aggregazione
        di sola visualizzazione.
      </p>
    </div>
  );
}
