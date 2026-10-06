import { siBaseAbsente } from "@/components/base-absente";
import Link from "next/link";
import { ArrowFillLink } from "@/components/block/arrow-fill-link";
import { Tag } from "@/components/dub";
import { nombre } from "@/lib/format";
import { TableauReunions } from "@/components/reunions-table";
import { communesMoissonnees, progressionLecture, reunions, statistiques } from "@/lib/reunions";

export const dynamic = "force-dynamic";

export default function Accueil() {
  try {
    const stats = statistiques();
    const villes = communesMoissonnees();
    const recentes = reunions(undefined, 6);

    return (
      <div className="py-10 sm:py-14">
        <section className="grid gap-10 border-b border-ash pb-12 lg:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)] lg:items-end">
          <div>
            <h1 className="font-display text-[clamp(40px,7vw,64px)] font-medium leading-[0.98] tracking-[-0.045em]">
              Comprendre ce que décide votre ville.
            </h1>
            <p className="mt-6 max-w-[62ch] text-body-lg text-steel">
              Les comptes rendus publics sont rassemblés, lus et classés automatiquement. Chaque information reste reliée au PDF officiel qui la prouve.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              {/* Composant ObsidianUI (components/block/arrow-fill-button) :
                  recoloré sur nos tokens, pas ses orange/blanc par défaut. */}
              <ArrowFillLink
                href="/collectivites"
                bgColor="#2563eb"
                textColor="#ffffff"
                fillBgColor="#ffffff"
                fillTextColor="#2563eb"
                hoverFillBgColor="#ffffff"
                hoverFillTextColor="#2563eb"
              >
                Parcourir les collectivités
              </ArrowFillLink>
              <Link href="/reunions" className="inline-flex min-h-12 items-center rounded-(--radius-buttons) border border-ash px-4 text-[14px] font-medium hover:bg-paper-mist">
                Voir toutes les réunions
              </Link>
            </div>
          </div>

          <div className="grid grid-cols-2 overflow-hidden rounded-(--radius-cards) border border-ash bg-canvas-white">
            <Metrique valeur={stats.collectivites} libelle="collectivités" />
            <Metrique valeur={stats.reunions} libelle="actes collectés" bordGauche />
            <Metrique valeur={stats.lues} libelle="PDF analysés" bordHaut />
            <Metrique valeur={stats.montants} libelle="décisions financières" bordGauche bordHaut />
          </div>
        </section>

        <section className="py-12" aria-labelledby="villes-recentes">
          <div className="mb-6 flex items-end justify-between gap-4">
            <div>
              <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">Territoires</p>
              <h2 id="villes-recentes" className="mt-1 text-heading font-medium tracking-[-0.025em]">Collectivités dans la base</h2>
            </div>
            <Link href="/collectivites" className="text-[13px] font-medium text-electric-blue hover:underline">Toutes les collectivités →</Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {villes.slice(0, 6).map((ville) => {
              const progression = progressionLecture(ville);
              const epci = ville.type === "epci";
              return (
                <Link key={ville.insee} href={`/collectivites/${ville.insee}`} className="group rounded-(--radius-cards) border border-ash p-5 transition-colors hover:border-smoke hover:bg-paper-mist/50">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-body-lg font-medium group-hover:text-electric-blue">{ville.commune ?? ville.insee}</h3>
                      <p className="mt-1 font-mono text-[11px] text-fog">
                        {epci ? "SIREN" : "INSEE"} {ville.insee}
                      </p>
                    </div>
                    <span aria-hidden="true" className="text-silver group-hover:text-electric-blue">↗</span>
                  </div>
                  <p className="mt-3 flex flex-wrap gap-2">
                    <Tag accent={epci ? "violet" : "blue"}>{epci ? "Intercommunalité" : "Commune"}</Tag>
                    {ville.suivie ? <Tag accent="green">Suivie</Tag> : null}
                  </p>
                  <div className="mt-6 flex items-center justify-between text-[12px] text-steel">
                    <span>{ville.nReunions} documents</span><span>{progression}% des PDF lus</span>
                  </div>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-ash"><div className="h-full rounded-full bg-electric-blue" style={{ width: `${progression}%` }} /></div>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="border-t border-ash pt-12" aria-labelledby="dernieres-reunions">
          <div className="mb-6">
            <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">Derniers ajouts</p>
            <h2 id="dernieres-reunions" className="mt-1 text-heading font-medium tracking-[-0.025em]">Réunions récentes</h2>
          </div>
          <TableauReunions liste={recentes} />
        </section>
      </div>
    );
  } catch (erreur) {
    return siBaseAbsente(erreur);
  }
}

function Metrique({ valeur, libelle, bordGauche = false, bordHaut = false }: { valeur: number; libelle: string; bordGauche?: boolean; bordHaut?: boolean }) {
  return (
    <div className={`p-5 sm:p-6 ${bordGauche ? "border-l border-ash" : ""} ${bordHaut ? "border-t border-ash" : ""}`}>
      <p className="text-[clamp(26px,4vw,36px)] font-medium tracking-[-0.04em] tabular-nums">{nombre(valeur)}</p>
      <p className="mt-1 text-[12px] text-fog">{libelle}</p>
    </div>
  );
}
