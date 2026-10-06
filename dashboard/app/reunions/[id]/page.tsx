import Link from "next/link";
import { notFound } from "next/navigation";
import { Carte, Etat, Tag } from "@/components/dub";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { dateLongue, montant } from "@/lib/format";
import { ACCENT_ETAT, etatLecture, LIBELLES_ETAT } from "@/lib/etat-lecture";
import { alertesDe, montantsDe, piecesCiteesDe, pointsOrdreJourDe, reunion, syntheseDe } from "@/lib/reunions";

// Explique la nature d'un montant sans alourdir la fiche : seules les valeurs
// qu'on est sûr de comprendre y figurent (voir AGENTS.md, invariant 9 — zéro
// approximation). Une valeur absente de ce dictionnaire s'affiche sans bulle,
// plutôt que de deviner un sens qu'on ne peut pas garantir.
const NATURE_EXPLIQUEE: Record<string, string> = {
  "Dépense": "Une somme que la collectivité verse.",
  "Recette": "Une somme que la collectivité perçoit.",
  "Subvention": "Une aide financière versée par la collectivité à un tiers.",
  "Financement par un tiers": "Une somme versée à la collectivité par un partenaire extérieur.",
  "Recette abandonnée": "Une somme que la collectivité renonce à percevoir.",
  "Garantie d'emprunt": "La collectivité se porte caution d'un emprunt contracté par un tiers : elle ne paie que si l'emprunteur fait défaut.",
  "Autorisation de programme": "Le plafond d'une dépense d'investissement étalée sur plusieurs années ; les crédits sont ouverts année par année.",
  "Plafond voté": "Le montant maximal que le conseil autorise pour une dépense encore à chiffrer ; la dépense réelle peut être inférieure.",
};

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = securise(() => reunion(Number(id)));
  return { title: r ? r.titre.slice(0, 60) : "Réunion" };
}

export default async function PageReunion({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const n = Number(id);
  if (!Number.isInteger(n)) notFound();
  const r = securise(() => reunion(n));
  if (!r) notFound();

  const montants = securise(() => montantsDe(n)) ?? [];
  const pieces = securise(() => piecesCiteesDe(n)) ?? [];
  const alertes = securise(() => alertesDe(n)) ?? [];
  const points = securise(() => pointsOrdreJourDe(n)) ?? [];
  const synthese = securise(() => syntheseDe(n));
  // Seules les dépenses actées comptent : un montant simplement mentionné dans
  // le débat (estimation, historique, budget de référence, part d'un tiers)
  // reste en base pour l'audit mais ne doit jamais apparaître ici — ce n'est
  // pas parce qu'un chiffre est cité qu'il a été décidé.
  const decides = montants.filter((m) => m.verifie === 1 && m.retenu === 1 && m.decisionFinanciere === 1);
  const impactsFinanciers = decides.filter((montant, index, liste) =>
    liste.findIndex((autre) => autre.valeur === montant.valeur
      && autre.pointOrdreJour === montant.pointOrdreJour
      && autre.nature === montant.nature) === index);
  // Un montant n'est « masqué » que s'il a été examiné puis écarté — son
  // explication en est la trace. Les candidats bruts jamais relus ne sont pas
  // masqués, ils sont inconnus : les compter reviendrait à annoncer un tri qui
  // n'a pas eu lieu.
  const examines = montants.filter((m) => m.explication !== null && m.explication !== "");
  const nNonVerifies = examines.length - impactsFinanciers.length;
  // Distinct de `r.analysee` (qui pilote le badge et le filtre, et exige
  // quelque chose à AFFICHER : un résumé ou une dépense actée). Ici on demande
  // juste si un agent a réellement ouvert le PDF, ce que `statutLecture` dit
  // sans détour. Sans cette distinction, une délibération aux montants tous
  // écartés (SIRET, bornes de tableau) affichait « aucun agent ne l'a encore
  // examiné » alors que 21 montants avaient été lus et triés à raison.
  const lu = r.statutLecture === "lu";

  return (
    <div className="py-10 sm:py-14">
      <nav aria-label="Fil d’Ariane" className="flex flex-wrap items-center gap-2 text-[12px] text-fog">
        <Link href="/collectivites" className="hover:underline">Collectivités</Link><span aria-hidden="true">/</span>
        <Link href={`/collectivites/${r.insee}`} className="hover:underline">{r.commune ?? r.insee}</Link><span aria-hidden="true">/</span>
        <span className="text-steel">Réunion</span>
      </nav>

      <header className="mt-7 border-b border-ash pb-9">
        <div className="flex flex-wrap gap-2">
          <Tag accent={ACCENT_ETAT[etatLecture(r)]}>{LIBELLES_ETAT[etatLecture(r)]}</Tag>
          {r.tags.filter((tag) => tag.categorie === "type").slice(0, 1).map((tag) => <Tag key={tag.libelle} accent="violet">{tag.libelle}</Tag>)}
        </div>
        <h1 className="mt-5 max-w-[980px] font-display text-[clamp(30px,5vw,44px)] font-medium leading-[1.08] tracking-[-0.035em]">{r.titre}</h1>
        <p className="mt-4 text-[13px] text-steel">
          {r.commune ?? r.insee}{r.dateSeance ? ` · séance du ${dateLongue(r.dateSeance)}` : ""}{r.numero ? ` · n° ${r.numero}` : ""}
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          {/* Pas encore archivé ne veut pas dire introuvable : l'adresse d'origine
              est connue dès la collecte, autant y mener. */}
          {r.aPdf ? <a href={`/reunions/${r.id}/pdf`} target="_blank" rel="noopener" className="inline-flex min-h-11 items-center rounded-(--radius-buttons) bg-midnight-ink px-4 text-[14px] font-medium text-white hover:bg-graphite">Ouvrir le PDF officiel ↗</a>
            : r.pdfUrl ? <a href={r.pdfUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center rounded-(--radius-buttons) border border-ash px-4 text-[14px] font-medium hover:bg-paper-mist">Ouvrir sur le site d’origine ↗</a>
              : <span className="inline-flex min-h-11 items-center rounded-(--radius-buttons) bg-paper-mist px-4 text-[13px] text-fog">Aucune source enregistrée</span>}
          {/* Pas de bouton vers la collectivité : le fil d'Ariane y mène déjà. */}
        </div>
      </header>

      <section className="grid gap-3 py-8 sm:grid-cols-2 lg:grid-cols-4" aria-label="Synthèse">
        <Indicateur valeur={synthese?.nombrePresents?.toString() ?? "—"} libelle="présents" />
        <Indicateur valeur={(synthese?.nombreDecisions ?? points.filter((p) => p.decision).length).toString()} libelle="décisions repérées" />
        <Indicateur valeur={impactsFinanciers.length.toString()} libelle="décisions financières" />
        <Indicateur valeur={pieces.length.toString()} libelle="pièces citées" />
      </section>

      <div className="mt-2 grid gap-12 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
        <div>
          {synthese?.resume ? (
            <section className="border-y border-ash py-8" aria-labelledby="resume-seance">
              <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">En clair</p>
              <h2 id="resume-seance" className="mt-1 text-heading-sm font-medium tracking-[-0.02em]">Résumé</h2>
              <div className="mt-4 max-w-[78ch] space-y-3 text-body-lg leading-7 text-charcoal">
                {synthese.resume.split("\n\n").map((paragraphe, i) => <p key={i}>{paragraphe}</p>)}
              </div>
            </section>
          ) : null}

          {/* `lu` sans résumé n'existe plus : analyse.py refuse de l'écrire et
              base.py rend à la lecture ceux d'avant (invariant 6). */}
          {!synthese?.resume ? (
            <div className="py-8">
              <Etat
                genre="alerte"
                titre="Ce document n’a pas encore été lu"
                detail={`${r.aPdf ? "Son PDF est archivé" : "Son PDF n’est pas encore téléchargé"}, mais aucun agent ne l’a encore lu. Rien n’est affirmé ici tant que ce n’est pas fait — ni décision, ni montant, ni ordre du jour.`}
                action={r.aPdf ? <a href={`/reunions/${r.id}/pdf`} target="_blank" rel="noopener" className="text-[13px] font-medium text-electric-blue hover:underline">Lire le PDF officiel ↗</a>
                  : r.pdfUrl ? <a href={r.pdfUrl} target="_blank" rel="noopener noreferrer" className="text-[13px] font-medium text-electric-blue hover:underline">Lire le PDF sur le site d’origine ↗</a> : undefined}
              />
            </div>
          ) : null}

          {alertes.length > 0 ? <Etat genre="alerte" titre="Un passage contenant probablement des données personnelles a été écarté" detail="Son contenu n’est ni résumé ni affiché dans le dashboard." /> : null}

          <section className="mt-10" aria-labelledby="points-importants">
            <div className="flex items-end justify-between gap-4 border-b border-ash pb-4">
              <div><p className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">Ordre du jour</p><h2 id="points-importants" className="mt-1 text-heading-sm font-medium tracking-[-0.02em]">Points importants</h2></div>
              {points.length ? <span className="text-[12px] text-fog">{points.length} points</span> : null}
            </div>
            {synthese?.voteGlobal ? <div className="mt-5 rounded-(--radius-cards) border border-ash bg-paper-mist p-4"><p className="text-[12px] font-medium uppercase tracking-[0.05em] text-fog">Résultat du vote</p><p className="mt-2 text-[14px] font-medium text-charcoal">{synthese.voteGlobal}</p></div> : null}
            {points.length ? (
              <ol className="divide-y divide-ash">
                {points.map((point) => (
                  <li key={point.ordre} className="grid gap-3 py-5 sm:grid-cols-[28px_1fr]">
                    <span className="flex size-7 items-center justify-center rounded-full bg-paper-mist font-mono text-[11px] text-fog">{point.ordre}</span>
                    <div>
                      <div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{point.titre}</h3>{point.est_budget ? <Tag accent="green">Budget</Tag> : null}</div>
                      {point.decision ? <p className="mt-2 text-[14px] leading-6 text-steel">{point.decision}</p> : null}
                      {point.resultat_vote ? <p className="mt-2 text-[12px] font-medium text-vivid-green">Vote · {point.resultat_vote}</p> : null}
                    </div>
                  </li>
                ))}
              </ol>
            ) : <p className="py-8 text-[14px] text-fog">{lu ? "Ce document ne se découpe pas en points d’ordre du jour : c’est une pièce unique, pas un procès-verbal de séance." : "Les points apparaîtront quand un agent aura lu le PDF."}</p>}
          </section>
        </div>

        <aside className="space-y-5">
          <Carte>
            <h2 className="text-[14px] font-medium">Informations</h2>
            <dl className="mt-4 space-y-3 text-[13px]">
              <Ligne libelle="Type" valeur={r.tags.find((t) => t.categorie === "type")?.libelle ?? "Délibération"} />
              <Ligne libelle="Source" valeur={r.source === "portail" ? "Portail de délibérations" : "Site communal"} />
              <Ligne libelle="Service" valeur={r.service ?? "Non renseigné"} />
              <Ligne libelle="Direction" valeur={r.direction ?? "Non renseignée"} />
              <Ligne libelle="Rapporteur·e" valeur={r.rapporteur ?? "Non renseigné·e"} />
            </dl>
          </Carte>
          <Carte>
            <h2 className="text-[14px] font-medium">Pièces citées dans le PDF</h2>
            {/* Une citation, pas une classification : pas de pill colorée ici,
                réservée aux attributs qu'on peut filtrer (voir dashboard/AGENTS.md). */}
            {pieces.length ? <><p className="mt-2 text-[12px] leading-5 text-fog">Les documents auxquels l’acte renvoie — convention, devis, marché, annexe… — et qui ne sont pas forcément publiés avec lui. Cette liste prouve seulement qu’ils sont cités : elle ne suppose ni leur présence ni leur absence dans la publication.</p>
            <ul className="mt-4 divide-y divide-ash text-[13px]">{pieces.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-2 capitalize first:pt-0 last:pb-0">
                <span className="text-charcoal">{p.nature}</span>
                {p.statut !== "reperee" ? <span className="text-[12px] text-fog">{p.statut}</span> : null}
              </li>
            ))}</ul></> : <p className="mt-3 text-[13px] text-fog">Aucune pièce citée repérée dans le texte.</p>}
          </Carte>
        </aside>
      </div>

      {/* Sans montant acté, cette section ne dirait que pourquoi elle est vide :
          la carte « Finances » et le résumé le disent déjà, plus haut et mieux. */}
      {impactsFinanciers.length ? (
      <section className="mt-12 border-t border-ash pt-10" aria-labelledby="montants">
        <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">Compréhension financière</p>
        <h2 id="montants" className="mt-1 text-heading-sm font-medium tracking-[-0.02em]">Décisions financières</h2>
        <p className="mt-2 max-w-[72ch] text-[14px] leading-6 text-steel">Seuls les montants réellement décidés apparaissent ici : le même point doit contenir à la fois une décision financière et un résultat de vote explicites. Un chiffre seulement cité dans un débat — estimation, historique, budget de référence, part d’un tiers — n’y figure jamais, même s’il ressemble à une décision. Le tag précise la nature exacte : une dépense, une recette, une subvention versée, un financement reçu d’un tiers ne se lisent pas de la même façon — toutes n’apparaissent pas ici sous « dépense ». Une garantie d’emprunt, une autorisation de programme ou un plafond voté engagent la collectivité sans être une dépense : ces montants ne s’additionnent pas aux autres.</p>
        {lu && nNonVerifies ? <p className="mt-2 text-[12px] text-fog">{nNonVerifies} occurrence{nNonVerifies > 1 ? "s ont" : " a"} été masquée{nNonVerifies > 1 ? "s" : ""} : montant non décidé par un vote explicite, preuve insuffisante, répétition ou arrondi remplacé par le montant final.</p> : null}
        <div className="mt-5 grid gap-4">{impactsFinanciers.map((m, i) => (
          <article key={`${m.valeur}-${m.pointOrdreJour}-${i}`} className="rounded-(--radius-cards) border border-ash p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><p className="text-heading-sm font-medium tabular-nums">{montant(m.valeur)}{m.suffixe ? ` ${m.suffixe}` : " €"}</p><div className="mt-2 flex flex-wrap gap-2">
                {NATURE_EXPLIQUEE[m.nature] ? (
                  <Tooltip>
                    <TooltipTrigger className="cursor-help border-none bg-transparent p-0"><Tag accent="blue">{m.nature}</Tag></TooltipTrigger>
                    <TooltipContent>{NATURE_EXPLIQUEE[m.nature]}</TooltipContent>
                  </Tooltip>
                ) : <Tag accent="blue">{m.nature}</Tag>}
              </div></div>
              <a href={`/reunions/${r.id}/pdf`} target="_blank" rel="noopener" className="text-[12px] font-medium text-electric-blue hover:underline">PDF officiel ↗</a>
            </div>
            {m.pointOrdreJour ? <p className="mt-4 text-[13px] font-medium leading-5 text-charcoal">{m.pointOrdreJour}</p> : null}
            {m.explication ? <p className="mt-2 text-[14px] leading-6 text-steel">{m.explication}</p> : null}
            <blockquote className="mt-4 border-l-2 border-ash pl-4 text-[13px] leading-6 text-fog">{m.phrase}</blockquote>
          </article>
        ))}</div>
      </section>
      ) : null}
    </div>
  );
}

function Indicateur({ valeur, libelle }: { valeur: string; libelle: string }) {
  return <div className="rounded-(--radius-cards) border border-ash p-4"><p className="text-heading-sm font-medium tracking-[-0.03em] tabular-nums">{valeur}</p><p className="mt-1 text-[12px] text-fog">{libelle}</p></div>;
}

function Ligne({ libelle, valeur }: { libelle: string; valeur: string }) {
  return <div className="flex items-start justify-between gap-4 border-b border-ash pb-3 last:border-0 last:pb-0"><dt className="text-fog">{libelle}</dt><dd className="max-w-[60%] text-right text-charcoal">{valeur}</dd></div>;
}

function securise<T>(fn: () => T): T | null { try { return fn(); } catch { return null; } }
