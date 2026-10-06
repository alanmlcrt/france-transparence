import { NextResponse } from "next/server";
import { communesMoissonnees, reunions } from "@/lib/reunions";

/**
 * Données de la palette de commande (Cmd/Ctrl+K) : chargées en un seul appel
 * à la première ouverture, filtrées ensuite côté client (cmdk). Base absente
 * ou vide -> listes vides, jamais une erreur qui casse la palette.
 */
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const communes = communesMoissonnees().map((c) => ({
      insee: c.insee, commune: c.commune, type: c.type,
    }));
    const liste = reunions(undefined, 1000).map((r) => ({
      id: r.id, titre: r.titre, commune: r.commune, insee: r.insee,
    }));
    return NextResponse.json({ communes, reunions: liste });
  } catch {
    return NextResponse.json({ communes: [], reunions: [] });
  }
}
