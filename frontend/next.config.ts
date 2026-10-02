import type { NextConfig } from "next";

/** Dove il server Next trova il backend: un indirizzo interno, che il
    browser non vede mai. In Docker è l'hostname del servizio. */
const BACKEND_URL = (process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

const nextConfig: NextConfig = {
  // `standalone` produce un bundle autosufficiente: l'immagine di
  // produzione non ha bisogno di node_modules, e resta piccola.
  output: "standalone",
  reactStrictMode: true,
  typescript: {
    // Nessuna build passa con errori di tipo: il type check e' un cancello,
    // non un avviso. La stessa regola vale per MyPy sul backend.
    ignoreBuildErrors: false,
  },
  // Il browser parla solo con l'origine da cui ha caricato la pagina, e il
  // server Next inoltra l'API al backend. Niente CORS e niente IP da
  // configurare: lo studio si apre da qualsiasi dispositivo in rete.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${BACKEND_URL}/api/v1/:path*` }];
  },
};

export default nextConfig;
