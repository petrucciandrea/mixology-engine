import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Spectral } from "next/font/google";

import "./globals.css";

/**
 * Tre ruoli tipografici, non tre font per decorazione: Spectral porta il
 * peso dei titoli, Plex Sans regge l'interfaccia, Plex Mono incolonna le
 * misure — che in questa applicazione si leggono confrontandole fra loro.
 */
const spectral = Spectral({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-spectral",
  display: "swap",
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Mixology Engine",
  description:
    "Bilanciamento scientifico di cocktail d'autore: solver a ottimizzazione vincolata e matcher organolettico.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="it" className={`${spectral.variable} ${plexSans.variable} ${plexMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
