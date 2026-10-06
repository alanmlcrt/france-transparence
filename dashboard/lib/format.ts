/**
 * Formatage localisé. Toujours par `Intl`, jamais par concaténation maison :
 * les espaces insécables des milliers et le placement de l'unité sont des
 * règles de langue, pas des détails d'affichage.
 *
 * Les formateurs sont construits une fois au chargement du module : en créer
 * un par rendu coûte cher pour rien.
 */

const NOMBRE = new Intl.NumberFormat("fr-FR");

export const nombre = (v: number) => NOMBRE.format(v);

// Une somme d'argent garde ses centimes en entier : « 697 155,5 € » se lit
// comme une coquille, la délibération écrit 697 155,50 €.
const CENTIMES = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const montant = (v: number) => (Number.isInteger(v) ? NOMBRE.format(v) : CENTIMES.format(v));

const DATE_LONGUE = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Europe/Paris",
});

/**
 * Les dates de la base sont des dates civiles (`YYYY-MM-DD`), sans heure.
 * Les lire en UTC évite qu'un fuseau négatif ne les décale d'un jour — et
 * garantit le même rendu côté serveur et côté client (pas de désynchro
 * d'hydratation).
 */
function jour(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return Number.isNaN(d.getTime()) ? null : d;
}

export function dateLongue(iso?: string | null): string {
  const d = iso ? jour(iso) : null;
  return d ? DATE_LONGUE.format(d) : "—";
}
