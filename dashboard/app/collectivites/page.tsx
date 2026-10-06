import { siBaseAbsente } from "@/components/base-absente";
import Link from "next/link";
import { Etat, Tag } from "@/components/dub";
import { communesMoissonnees, progressionLecture, type CommuneMoissonnee, type TypeCollectivite } from "@/lib/reunions";

export const metadata = { title: "Collectivités" };
export const dynamic = "force-dynamic";

type Filtre = "toutes" | TypeCollectivite;

const LIBELLES: Record<Filtre, string> = {
  toutes: "Toutes",
  commune: "Communes",
  epci: "Intercommunalités",
};

export default async function Collectivites({
  searchParams,
}: {
  searchParams: Promise<{ [cle: string]: string | string[] | undefined }>;
}) {
  const demande = (await searchParams).type;
  const filtre: Filtre = demande === "commune" || demande === "epci" ? demande : "toutes";

  try {
    const toutes = communesMoissonnees();
    const compte: Record<Filtre, number> = {
      toutes: toutes.length,
      commune: toutes.filter((c) => c.type === "commune").length,
      epci: toutes.filter((c) => c.type === "epci").length,
    };
    const liste = filtre === "toutes" ? toutes : toutes.filter((c) => c.type === filtre);

    return (
      <div className="py-10 sm:py-14">
        <header className="max-w-[680px]">
          <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">Annuaire</p>
          <h1 className="mt-2 font-display text-[clamp(36px,6vw,48px)] font-medium leading-none tracking-[-0.04em]">Collectivités suivies</h1>
          <p className="mt-5 text-body-lg text-steel">
            Communes et intercommunalités présentes dans la base. Une agglomération porte les
            compétences les plus coûteuses — transports, déchets, eau, voirie — que la commune
            seule ne décide pas.
          </p>
        </header>

        <nav aria-label="Filtrer par type de collectivité" className="mt-8">
          <ul className="flex flex-wrap items-center gap-1 rounded-(--radius-buttons) border border-ash p-1 sm:inline-flex">
            {(Object.keys(LIBELLES) as Filtre[]).map((cle) => {
              const actif = cle === filtre;
              return (
                <li key={cle}>
                  <Link
                    href={cle === "toutes" ? "/collectivites" : `/collectivites?type=${cle}`}
                    aria-current={actif ? "page" : undefined}
                    aria-label={`${LIBELLES[cle]} (${compte[cle]})`}
                    className={`inline-flex min-h-11 items-center gap-2 rounded-(--radius-buttons) px-3 text-[13px] transition-colors ${
                      actif
                        ? "bg-paper-mist font-medium text-charcoal"
                        : "font-medium text-steel hover:bg-paper-mist/60 hover:text-charcoal"
                    }`}
                  >
                    {LIBELLES[cle]}
                    <span className="text-[12px] tabular-nums text-fog">{compte[cle]}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {liste.length ? (
          <div className="mt-6 overflow-hidden rounded-(--radius-cards) border border-ash">
            {liste.map((c) => <Ligne key={c.insee} collectivite={c} />)}
          </div>
        ) : (
          <div className="mt-6">
            <Etat
              genre="vide"
              titre={filtre === "epci" ? "Aucune intercommunalité dans la base" : "Aucune commune dans la base"}
              detail="Lancez une moisson sur cette collectivité pour la voir apparaître ici."
              action={<Link href="/collectivites" className="text-[13px] font-medium text-electric-blue hover:underline">Voir toutes les collectivités</Link>}
            />
          </div>
        )}
      </div>
    );
  } catch (erreur) {
    return siBaseAbsente(erreur);
  }
}

function Ligne({ collectivite }: { collectivite: CommuneMoissonnee }) {
  const progression = progressionLecture(collectivite);
  const epci = collectivite.type === "epci";

  return (
    <Link
      href={`/collectivites/${collectivite.insee}`}
      className="group grid gap-4 border-b border-ash p-5 last:border-b-0 hover:bg-paper-mist sm:grid-cols-[1fr_120px_180px_24px] sm:items-center"
    >
      <div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h2 className="font-medium group-hover:text-electric-blue">{collectivite.commune ?? collectivite.insee}</h2>
          <Tag accent={epci ? "violet" : "blue"}>{epci ? "Intercommunalité" : "Commune"}</Tag>
          {collectivite.suivie ? <Tag accent="green">Suivie</Tag> : null}
        </div>
        <p className="mt-1 font-mono text-[11px] text-fog">
          {epci ? "SIREN" : "Code INSEE"} {collectivite.insee}
        </p>
      </div>
      <p className="text-[13px] text-steel"><span className="font-medium text-charcoal">{collectivite.nReunions}</span> documents</p>
      <div>
        <div className="flex justify-between text-[11px] text-fog"><span>{collectivite.nLues} lus sur {collectivite.nArchivees} PDF</span><span>{progression}%</span></div>
        <div className="mt-2 h-1 rounded-full bg-ash"><div className="h-full rounded-full bg-electric-blue" style={{ width: `${progression}%` }} /></div>
      </div>
      <span aria-hidden="true" className="hidden text-right text-silver group-hover:text-electric-blue sm:block">→</span>
    </Link>
  );
}
