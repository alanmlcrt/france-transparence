import Link from "next/link";
import { notFound } from "next/navigation";
import { Tag } from "@/components/dub";
import { TableauReunions } from "@/components/reunions-table";
import { codeCollectiviteValide, communeMoissonnee, epciDeLaCommune, progressionLecture, reunions, type Rattachement } from "@/lib/reunions";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const collectivite = securise(() => communeMoissonnee(code));
  return { title: collectivite?.commune ?? `Collectivité ${code}` };
}

export default async function PageCollectivite({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!codeCollectiviteValide(code)) notFound();
  const collectivite = securise(() => communeMoissonnee(code));
  if (!collectivite) notFound();
  const liste = securise(() => reunions(code, -1)) ?? [];
  const progression = progressionLecture(collectivite);
  const epci = collectivite.type === "epci";
  const rattachement = epci ? null : securise(() => epciDeLaCommune(code));

  return (
    <div className="py-10 sm:py-14">
      <p><Link href="/collectivites" className="text-[13px] text-fog hover:underline">← Toutes les collectivités</Link></p>
      <header className="mt-7 grid gap-8 border-b border-ash pb-10 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Tag accent={epci ? "violet" : "blue"}>{epci ? "Intercommunalité" : "Commune"}</Tag>
            {collectivite.suivie ? <Tag accent="green">Suivie</Tag> : null}
          </div>
          <h1 className="mt-4 font-display text-[clamp(38px,7vw,56px)] font-medium leading-none tracking-[-0.045em]">{collectivite.commune ?? collectivite.insee}</h1>
          <p className="mt-2 text-[13px] text-fog">{epci ? "SIREN" : "Code INSEE"} {collectivite.insee}</p>
          <p className="mt-4 max-w-[58ch] text-body-lg text-steel">
            {epci
              ? "Toutes les délibérations collectées pour cette intercommunalité — celles qui engagent les communes membres sans passer par leur conseil municipal."
              : "Toutes les réunions et délibérations collectées pour cette commune, avec leur état de lecture et leur classement automatique."}
          </p>
        </div>
        <div className="min-w-[250px] rounded-(--radius-cards) border border-ash p-5">
          <div className="flex items-end justify-between"><p className="text-[13px] text-steel">Documents analysés</p><p className="text-heading-sm font-medium tabular-nums">{progression}%</p></div>
          <div className="mt-3 h-1.5 rounded-full bg-ash"><div className="h-full rounded-full bg-electric-blue" style={{ width: `${progression}%` }} /></div>
          <p className="mt-3 text-[12px] text-fog">{collectivite.nLues} lus sur {collectivite.nArchivees} PDF archivés ({collectivite.nReunions} documents référencés)</p>
        </div>
      </header>

      {rattachement ? <CarteEpci rattachement={rattachement} /> : null}

      <section className="pt-10" aria-labelledby="documents-collectivite">
        <div className="mb-5 flex items-center justify-between gap-4">
          <h2 id="documents-collectivite" className="text-heading-sm font-medium tracking-[-0.02em]">Documents</h2>
          <span className="text-[12px] text-fog">{liste.length} éléments</span>
        </div>
        <TableauReunions liste={liste} afficherVille={false} />
      </section>
    </div>
  );
}

/** Passerelle vers l'agglo dont depend la commune : ce qu'elle decide n'apparait
 *  dans aucun de ces documents, alors que ca engage les memes habitants. */
function CarteEpci({ rattachement }: { rattachement: Rattachement }) {
  const contenu = (
    <>
      <span>
        <span className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">Intercommunalité de rattachement</span>
        <span className="mt-1 block text-body-lg font-medium">{rattachement.nom}</span>
        <span className="mt-1 block max-w-[62ch] text-[13px] text-steel">
          {rattachement.connue
            ? "Transports, déchets, eau, voirie : ces compétences se votent ici, pas au conseil municipal."
            : "Cette intercommunalité n’est pas encore dans la base : ses délibérations n’apparaissent donc nulle part ici."}
        </span>
      </span>
      {rattachement.connue ? (
        <span aria-hidden="true" className="shrink-0 text-silver group-hover:text-electric-blue">→</span>
      ) : null}
    </>
  );

  const classes = "mt-10 flex items-start justify-between gap-4 rounded-(--radius-cards) border border-ash p-5";
  return rattachement.connue ? (
    <Link href={`/collectivites/${rattachement.siren}`} className={`group ${classes} transition-colors hover:border-smoke hover:bg-paper-mist`}>
      {contenu}
    </Link>
  ) : (
    <div className={classes}>{contenu}</div>
  );
}

function securise<T>(fn: () => T): T | null {
  try { return fn(); } catch { return null; }
}
