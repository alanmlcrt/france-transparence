import { Etat } from "@/components/dub";
import { BaseDeliberationsAbsente } from "@/lib/reunions";

/** Écran de premier lancement. Le dépôt arrive sans base : ce n'est pas une
 *  panne, c'est l'état normal tant qu'aucune collectivité n'a été demandée.
 *  Le dire, et donner la première action, plutôt qu'un constat d'absence. */
export function BaseAbsente() {
  return (
    <div className="py-16">
      <Etat
        genre="vide"
        titre="Aucune collectivité suivie pour l'instant"
        detail={
          <>
            Le tableau de bord lit une base que rien n&apos;a encore remplie.
            La collecte est faite par un agent, pas par un script : demandez-lui
            de suivre une collectivité.
            <code className="mt-3 block rounded-(--radius-buttons) border border-ash bg-paper-mist px-3 py-2 text-left text-[13px] text-midnight-ink">
              « Surveille les délibérations de ma commune »
            </code>
            <span className="mt-3 block">
              Il trouvera où elle publie ses actes, les téléchargera et les
              lira. Si la base n&apos;existe pas encore :{" "}
              <code className="text-[13px]">python scripts/base.py</code>.
            </span>
          </>
        }
      />
    </div>
  );
}

/** Seule l'absence de base mérite cet écran d'accueil. Toute autre erreur
 *  (requête cassée, schéma qui a dérivé) doit se voir, pas se déguiser en
 *  premier lancement. */
export function siBaseAbsente(erreur: unknown) {
  if (erreur instanceof BaseDeliberationsAbsente) return <BaseAbsente />;
  throw erreur;
}
