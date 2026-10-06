/**
 * État de lecture d'un document, tel que l'utilisateur le voit.
 *
 * Volontairement isolé de `lib/reunions.ts` : ce vocabulaire est partagé avec
 * le tableau, qui est un composant client. Or `lib/reunions.ts` ouvre la base
 * via `node:sqlite` — l'importer depuis le navigateur fait échouer le build.
 * Ce module ne dépend donc de rien et décrit sa donnée d'entrée par sa forme.
 *
 * Défini une seule fois parce que le tableau et le filtre doivent parler le
 * même langage : sinon filtrer « lu et analysé » ramène des lignes marquées
 * « pas analysé ».
 */

export type EtatLecture = "pas-telecharge" | "pas-analyse" | "analyse" | "echec";

export const LIBELLES_ETAT: Record<EtatLecture, string> = {
  "pas-telecharge": "Pas téléchargé",
  "pas-analyse": "Pas analysé",
  analyse: "Lu et analysé",
  echec: "Lecture échouée",
};

export const ACCENT_ETAT: Record<EtatLecture, "green" | "orange" | "violet" | "blue"> = {
  echec: "orange",
  "pas-telecharge": "violet",
  "pas-analyse": "blue",
  analyse: "green",
};

type Lisible = {
  statutLecture: "brut" | "lu" | "echec";
  aPdf: boolean;
  analysee: boolean;
};

export function etatLecture(r: Lisible): EtatLecture {
  if (r.statutLecture === "echec") return "echec";
  if (!r.aPdf) return "pas-telecharge";
  return r.analysee ? "analyse" : "pas-analyse";
}
