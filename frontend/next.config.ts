import type { NextConfig } from "next";

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
};

export default nextConfig;
