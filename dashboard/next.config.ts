import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // /villes a precede l'arrivee des EPCI dans la base : les liens deja
  // partages doivent continuer a ouvrir la meme fiche.
  redirects() {
    return Promise.resolve([
      { source: "/villes", destination: "/collectivites", permanent: true },
      { source: "/villes/:code", destination: "/collectivites/:code", permanent: true },
    ]);
  },
};

export default nextConfig;
