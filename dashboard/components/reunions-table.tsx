"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Tag } from "@/components/dub";
import { dateLongue } from "@/lib/format";
import { ACCENT_ETAT, etatLecture, LIBELLES_ETAT, type EtatLecture } from "@/lib/etat-lecture";
import type { Reunion } from "@/lib/reunions";

/** Chevron dessiné à la main : le dépôt ne porte aucune librairie d'icônes et
 *  n'en ajoutera pas pour une flèche. Décoratif — l'état est déjà porté par
 *  `aria-expanded` sur le bouton. */
function Chevron({ ouvert }: { ouvert: boolean }) {
  return (
    <svg
      viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"
      className="shrink-0 text-fog"
      // Rotation en style inline : Tailwind v4 pilote `rotate` et non
      // `transform`, et la classe utilitaire ne prenait pas ici. Le repli
      // `prefers-reduced-motion` de globals.css neutralise la transition.
      style={{ rotate: ouvert ? "90deg" : "0deg", transition: "rotate 150ms ease-out" }}
    >
      <path d="M4.5 2.5 L8 6 L4.5 9.5" fill="none" stroke="currentColor"
        strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Même trait que Chevron, à la verticale : indicateur de tri sur un en-tête. */
function FlecheTri({ direction }: { direction: "asc" | "desc" }) {
  return (
    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true" className="shrink-0 text-electric-blue"
      style={{ rotate: direction === "desc" ? "180deg" : "0deg" }}>
      <path d="M2.5 7.5 L6 4 L9.5 7.5" fill="none" stroke="currentColor"
        strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type Groupe = { cle: string; libelle: string; lignes: Reunion[] };

/** Une date de séance et les actes qu'elle porte. Regrouper rend une commune
 *  lisible : une grande ville aligne des centaines de délibérations pour une
 *  poignée de dates de séance seulement, et la liste à plat n'apprend rien. La
 *  liste arrive déjà antéchronologique, l'ordre d'apparition suffit. */
function grouperParDate(liste: Reunion[]): Groupe[] {
  const groupes: Groupe[] = [];
  let dateCourante: string | null | undefined;
  for (const r of liste) {
    if (groupes.length && r.dateSeance === dateCourante) {
      groupes[groupes.length - 1].lignes.push(r);
      continue;
    }
    dateCourante = r.dateSeance;
    groupes.push({
      // La clé porte le rang, pas seulement la date : sur la vue toutes
      // collectivités, les documents sans date forment plusieurs blocs non
      // contigus. Une clé partagée ferait replier tous ces blocs ensemble.
      cle: `${r.dateSeance ?? "sans-date"}#${groupes.length}`,
      libelle: r.dateSeance ? dateLongue(r.dateSeance) : "Date non renseignée",
      lignes: [r],
    });
  }
  return groupes;
}

type Colonne = "titre" | "date" | "collectivite" | "lecture" | "signaux" | "source";

// Ordre de progression d'une lecture, pas l'ordre alphabétique du libellé :
// trier par état doit rapprocher les documents au même stade, du moins avancé
// au plus avancé.
const RANG_ETAT: Record<EtatLecture, number> = {
  "pas-telecharge": 0, "pas-analyse": 1, echec: 2, analyse: 3,
};
const RANG_SOURCE = (r: Reunion) => (r.aPdf ? 2 : r.pdfUrl ? 1 : 0);

const COMPARATEURS: Record<Colonne, (a: Reunion, b: Reunion) => number> = {
  titre: (a, b) => a.titre.localeCompare(b.titre, "fr"),
  date: (a, b) => (a.dateSeance ?? "").localeCompare(b.dateSeance ?? ""),
  collectivite: (a, b) => (a.commune ?? a.insee).localeCompare(b.commune ?? b.insee, "fr"),
  lecture: (a, b) => RANG_ETAT[etatLecture(a)] - RANG_ETAT[etatLecture(b)],
  signaux: (a, b) => (a.nMontantsSurs - b.nMontantsSurs) || (a.nPiecesCitees - b.nPiecesCitees),
  source: (a, b) => RANG_SOURCE(a) - RANG_SOURCE(b),
};

const COLONNES: Array<{ cle: Colonne; libelle: string; besoinVille?: boolean; alignDroite?: boolean }> = [
  { cle: "titre", libelle: "Réunion" },
  { cle: "date", libelle: "Séance" },
  { cle: "collectivite", libelle: "Collectivité", besoinVille: true },
  { cle: "lecture", libelle: "Lecture" },
  { cle: "signaux", libelle: "Signaux", alignDroite: true },
  { cle: "source", libelle: "Source", alignDroite: true },
];

export function TableauReunions({ liste, afficherVille = true }: { liste: Reunion[]; afficherVille?: boolean }) {
  const [tri, setTri] = useState<{ colonne: Colonne; direction: "asc" | "desc" } | null>(null);
  const groupes = useMemo(() => grouperParDate(liste), [liste]);
  // La date la plus récente est ouverte : c'est celle qu'on vient consulter.
  const [ouverts, setOuverts] = useState<Set<string>>(() => new Set(groupes.slice(0, 1).map((g) => g.cle)));

  if (liste.length === 0) {
    return <p className="rounded-(--radius-cards) border border-ash px-5 py-10 text-center text-[14px] text-fog">Aucune réunion dans cette vue.</p>;
  }

  const nColonnes = afficherVille ? 6 : 5;
  const basculer = (cle: string) => setOuverts((actuels) => {
    const suivant = new Set(actuels);
    if (!suivant.delete(cle)) suivant.add(cle);
    return suivant;
  });

  // Trier casse le regroupement par date de séance : les deux classements se
  // contrediraient (l'ordre dans un groupe vs l'ordre demandé). Une fois un
  // tri actif, la table redevient une simple liste, sans en-têtes de date.
  const trieeAPlat = tri
    ? [...liste].sort((a, b) => COMPARATEURS[tri.colonne](a, b) * (tri.direction === "desc" ? -1 : 1))
    : null;

  const basculerTri = (colonne: Colonne) => setTri((actuel) => {
    if (!actuel || actuel.colonne !== colonne) return { colonne, direction: "asc" };
    if (actuel.direction === "asc") return { colonne, direction: "desc" };
    return null; // un troisième clic revient au regroupement par date
  });

  return (
    <div className="scroll-fade-x overflow-x-auto rounded-(--radius-cards) border border-ash bg-canvas-white">
      <table className="w-full min-w-[820px] border-collapse text-left">
        <caption className="sr-only">Réunions et délibérations collectées, regroupées par date de séance ou triées par colonne</caption>
        <thead>
          <tr className="border-b border-ash text-[12px] font-medium uppercase tracking-[0.05em] text-fog">
            {COLONNES.filter((c) => !c.besoinVille || afficherVille).map((c) => {
              const actif = tri?.colonne === c.cle;
              return (
                <th key={c.cle} scope="col" aria-sort={actif ? (tri!.direction === "asc" ? "ascending" : "descending") : "none"}
                  className={`py-3 pr-4 first:pl-4 last:pl-4 ${c.alignDroite ? "text-right" : ""}`}>
                  <button
                    type="button"
                    onClick={() => basculerTri(c.cle)}
                    className={`inline-flex min-h-7 items-center gap-1.5 rounded-(--radius-buttons) hover:text-charcoal ${c.alignDroite ? "flex-row-reverse" : ""} ${actif ? "text-charcoal" : ""}`}
                  >
                    {c.libelle}
                    {actif ? <FlecheTri direction={tri!.direction} /> : null}
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        {trieeAPlat ? (
          <tbody>
            {trieeAPlat.map((r, i) => (
              <Ligne key={r.id} r={r} afficherVille={afficherVille} delaiMs={Math.min(i, 8) * 15} />
            ))}
          </tbody>
        ) : groupes.map((groupe) => {
          const ouvert = ouverts.has(groupe.cle);
          const idCorps = `date-${groupe.cle}`;
          return (
            <tbody key={groupe.cle} id={idCorps} className="border-t border-ash first:border-t-0">
              <tr>
                <th scope="colgroup" colSpan={nColonnes} className="p-0 font-normal">
                  <button
                    type="button"
                    onClick={() => basculer(groupe.cle)}
                    aria-expanded={ouvert}
                    aria-controls={idCorps}
                    className="flex min-h-11 w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors hover:bg-paper-mist"
                  >
                    <Chevron ouvert={ouvert} />
                    <span className="text-[13px] font-medium text-charcoal">{groupe.libelle}</span>
                    <span className="ml-auto text-[12px] tabular-nums text-fog">
                      {groupe.lignes.length} document{groupe.lignes.length > 1 ? "s" : ""}
                    </span>
                  </button>
                </th>
              </tr>
              {ouvert ? groupe.lignes.map((r, i) => (
                <Ligne key={r.id} r={r} afficherVille={afficherVille} delaiMs={Math.min(i, 8) * 15} />
              )) : null}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}

function Ligne({ r, afficherVille, delaiMs }: { r: Reunion; afficherVille: boolean; delaiMs: number }) {
  return (
    <tr className="ligne-entree group border-t border-ash align-middle" style={{ animationDelay: `${delaiMs}ms` }}>
      <td className="max-w-[420px] py-4 pr-4 pl-[42px]">
        <Link href={`/reunions/${r.id}`} className="block font-medium leading-5 text-charcoal group-hover:text-electric-blue">
          {r.titre}
        </Link>
        {r.numero ? <p className="mt-1 text-[12px] text-fog">n° {r.numero}</p> : null}
      </td>
      <td className="py-4 pr-4 text-[13px] whitespace-nowrap text-steel">{dateLongue(r.dateSeance)}</td>
      {afficherVille ? (
        <td className="py-4 pr-4 whitespace-nowrap">
          <Link href={`/collectivites/${r.insee}`} className="text-[13px] font-medium hover:underline">
            {r.commune ?? r.insee}
          </Link>
        </td>
      ) : null}
      <td className="py-4 pr-4 whitespace-nowrap">
        <Tag accent={ACCENT_ETAT[etatLecture(r)]}>{LIBELLES_ETAT[etatLecture(r)]}</Tag>
      </td>
      <td className="py-4 pr-4 text-right text-[12px] tabular-nums text-steel whitespace-nowrap">
        {r.nMontantsSurs ? `${r.nMontantsSurs} montant${r.nMontantsSurs > 1 ? "s" : ""}` : "—"}
        {r.nPiecesCitees ? <span className="block">{`${r.nPiecesCitees} ${r.nPiecesCitees > 1 ? "pièces" : "pièce"}`}</span> : null}
      </td>
      <td className="py-4 pr-4 pl-4 text-right whitespace-nowrap">
        {r.aPdf ? (
          <a href={`/reunions/${r.id}/pdf`} target="_blank" rel="noopener" className="text-[13px] font-medium text-electric-blue hover:underline">
            PDF
          </a>
        ) : r.pdfUrl ? (
          <a href={r.pdfUrl} target="_blank" rel="noopener noreferrer" className="text-[13px] font-medium text-steel hover:text-electric-blue hover:underline">
            Site d’origine ↗
          </a>
        ) : <span className="text-[12px] text-silver">Aucune source</span>}
      </td>
    </tr>
  );
}
