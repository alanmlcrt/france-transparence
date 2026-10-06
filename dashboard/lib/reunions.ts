import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
import { etatLecture, type EtatLecture } from "./etat-lecture.ts";

/** Lecture stricte de la base collectee : le dashboard n'est jamais ecrivain. */
export const CHEMIN_DELIB_DB =
  process.env.FT_DELIB_DB ?? path.join(process.cwd(), "..", "data", "deliberations.db");

export class BaseDeliberationsAbsente extends Error {
  constructor(chemin: string) {
    super(`aucune base de deliberations a ${chemin}`);
  }
}

let cache: { chemin: string; db: DatabaseSync } | null = null;

function base(chemin = CHEMIN_DELIB_DB): DatabaseSync {
  if (!fs.existsSync(chemin)) throw new BaseDeliberationsAbsente(chemin);
  if (cache?.chemin === chemin) return cache.db;
  cache?.db.close();
  const db = new DatabaseSync(chemin, { readOnly: true });
  cache = { chemin, db };
  return db;
}

function lire<T>(sql: string, params: unknown[] = [], chemin = CHEMIN_DELIB_DB): T[] {
  return base(chemin).prepare(sql).all(...(params as never[])) as T[];
}

function tableExiste(nom: string): boolean {
  return Boolean(lire<{ n: number }>(
    "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name=?", [nom],
  )[0]?.n);
}

/** Les chemins de PDF s'écrivent relatifs à la racine du dépôt (le dossier
 *  qui contient `data/`) : la base reste valable si le dépôt est déplacé. Un
 *  chemin absolu d'une base ancienne est rendu tel quel. */
export function cheminPdf(enregistre: string, chemin = CHEMIN_DELIB_DB): string {
  return path.resolve(path.dirname(chemin), "..", enregistre);
}

export function fermer(): void {
  cache?.db.close();
  cache = null;
}

export type StatutLecture = "brut" | "lu" | "echec";
export type SourceMoisson = "portail" | "site";
export type CategorieTag = "type" | "theme" | "signal";
export type TagAutomatique = { libelle: string; categorie: CategorieTag };

export type Reunion = {
  id: number;
  insee: string;
  commune: string | null;
  dateSeance: string | null;
  numero: string | null;
  titre: string;
  service: string | null;
  direction: string | null;
  rapporteur: string | null;
  source: SourceMoisson;
  statutLecture: StatutLecture;
  /** Un agent a écrit le résumé du document. `statutLecture` ne dit, lui, que
   *  si le texte a été récupéré ; des montants qualifiés sans résumé ne
   *  suffisent pas (analyse commencée, pas terminée — AGENTS.md, invariant 6). */
  analysee: boolean;
  /** Une synthèse rédigée existe. Sans elle, la fiche n'affiche pas de résumé. */
  resumee: boolean;
  aPdf: boolean;
  /** Adresse d'origine sur le site de la collectivité. Elle existe dès la
   *  collecte, avant tout téléchargement — et reste la source vivante, que
   *  notre copie archivée (aPdf) vient seulement figer. */
  pdfUrl: string | null;
  nMontantsSurs: number;
  nPiecesCitees: number;
  nAlertes: number;
  moissonneeLe: string;
  tags: TagAutomatique[];
};

type LigneReunion = {
  id: number; insee: string; commune: string | null; date_seance: string | null;
  numero: string | null; titre: string; service: string | null; direction: string | null;
  rapporteur: string | null; source: SourceMoisson; statut_lecture: StatutLecture;
  pdf_chemin_local: string | null; pdf_url: string | null;
  n_montants: number; n_pieces: number; n_alertes: number;
  moissonnee_le: string; resumee: number;
};

/** L'URL vient d'une page publique moissonnée : ne jamais la rendre cliquable
 *  sans vérifier le schéma, une href arbitraire n'a rien à faire dans un lien. */
function urlPubliqueSure(url: string | null): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
}

const SELECT_REUNIONS = `
  SELECT d.id, d.insee, d.commune, s.date_seance, d.numero, d.titre, d.service,
         d.direction, d.rapporteur, d.source, d.statut_lecture,
         d.pdf_chemin_local, d.pdf_url, d.moissonnee_le,
         (SELECT COUNT(*) FROM montants_extraits m
           WHERE m.deliberation_id=d.id AND m.verifie=1 AND m.retenu=1 AND m.decision_financiere=1) AS n_montants,
         (SELECT COUNT(*) FROM pieces_citees p WHERE p.deliberation_id=d.id) AS n_pieces,
         (SELECT COUNT(*) FROM alertes_donnees_personnelles a WHERE a.deliberation_id=d.id) AS n_alertes,
         EXISTS(SELECT 1 FROM syntheses_reunions y WHERE y.deliberation_id=d.id) AS resumee
  FROM deliberations d LEFT JOIN seances s ON s.id=d.seance_id
`;

const REGLES_TAGS: Array<[string, CategorieTag, RegExp]> = [
  ["Budget et fiscalité", "theme", /budget|credits? (?:budgetaires?|ouverts?|inscrits?)|compte (?:administratif|financier)|fiscalite|taux d'imposition|emprunt|dette/i],
  ["Subventions", "theme", /subventions?|participation financiere/i],
  ["Commande publique", "theme", /marches? publics?|appel d'offres|accord-cadre|delegation de service public/i],
  ["Urbanisme et foncier", "theme", /urbanisme|\bplui?\b|foncier|permis de construire|droit de preemption/i],
  ["Mobilités et voirie", "theme", /voirie|mobilite|stationnement|transports?|piste cyclable/i],
  ["Bâtiments et patrimoine", "theme", /patrimoine|batiment communal|travaux de renovation|monument historique/i],
  ["Transition écologique", "theme", /environnement|transition ecologique|energie|climat|biodiversite|dechets?/i],
  ["Ressources humaines", "theme", /personnel communal|ressources humaines|creation de poste|tableau des effectifs|regime indemnitaire/i],
  ["Éducation et jeunesse", "theme", /ecole|scolaire|periscolaire|petite enfance|creche|jeunesse/i],
  ["Culture", "theme", /culturel|bibliotheque|mediatheque|musee|spectacle vivant/i],
  ["Sports", "theme", /sport(?:if|ive|ifs|ives)?|gymnase|stade|equipement sportif/i],
  ["Solidarités et santé", "theme", /action sociale|solidarite|sante|handicap|personnes agees/i],
  ["Sécurité", "theme", /police municipale|videoprotection|securite publique|prevention de la delinquance/i],
  ["Numérique", "theme", /numerique|informatique|cybersecurite|dematerialisation|donnees ouvertes/i],
  ["Logement", "theme", /logements?|habitat|bailleur social|logement social/i],
  ["Eau et assainissement", "theme", /assainissement|eau potable|eaux usees|eaux pluviales/i],
];

function sansAccents(texte: string): string {
  return texte.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function tagsMetadonnees(l: LigneReunion): TagAutomatique[] {
  const texte = sansAccents([l.titre, l.service, l.direction].filter(Boolean).join(" "));
  const type = /proces-verbal|\bpv\b/i.test(texte) ? "Procès-verbal"
    : /compte.?rendu/i.test(texte) ? "Compte rendu"
      : /arrete/i.test(texte) ? "Arrêté"
        : /bulletin/i.test(texte) ? "Bulletin communal" : "Délibération";
  const tags: TagAutomatique[] = [{ libelle: type, categorie: "type" }];
  for (const [libelle, categorie, motif] of REGLES_TAGS) {
    if (motif.test(texte)) tags.push({ libelle, categorie });
  }
  return tags;
}

/** Tous les tags persistés, en une requête : les lire ligne par ligne coûtait
 *  deux requêtes par délibération, deux mille pour un tableau de mille. */
function tagsPersistes(portee: { id?: number; insee?: string } = {}): Map<number, TagAutomatique[]> {
  const parId = new Map<number, TagAutomatique[]>();
  if (!tableExiste("tags_automatiques")) return parId;
  // Bornés à ce qu'on affiche : une fiche de collectivité ne lit pas les tags
  // de toute la base.
  const [filtre, params] = portee.id !== undefined ? ["WHERE deliberation_id=?", [portee.id]]
    : portee.insee !== undefined
      ? ["WHERE deliberation_id IN (SELECT id FROM deliberations WHERE insee=?)", [portee.insee]]
      : ["", []];
  for (const t of lire<TagAutomatique & { deliberation_id: number }>(
    `SELECT deliberation_id, libelle, categorie FROM tags_automatiques ${filtre} ORDER BY categorie, libelle`,
    params,
  )) {
    // node:sqlite rend des objets à prototype nul : recopier en objets ordinaires,
    // sinon ils ne peuvent pas traverser la frontière serveur → client.
    const liste = parId.get(t.deliberation_id) ?? [];
    liste.push({ libelle: t.libelle, categorie: t.categorie });
    parId.set(t.deliberation_id, liste);
  }
  return parId;
}

function versReunion(l: LigneReunion, persistes: Map<number, TagAutomatique[]>): Reunion {
  // Une délibération n'est « analysée » qu'une fois son résumé écrit — des
  // montants qualifiés sans résumé sont une analyse commencée, pas terminée
  // (voir AGENTS.md, invariant 6) : les compter ici affichait le badge vert
  // au-dessus d'une fiche dont le résumé manquait encore.
  const analysee = l.resumee === 1;
  // Le type du document (« Délibération », « Procès-verbal »...) se déduit
  // toujours de l'intitulé : aucun agent ne l'écrit en base.
  // Les sujets, eux, ne sont devinés par motif que tant que personne n'a lu le
  // document. L'agent lit le texte de la décision, le motif ne voit que
  // l'intitulé et le service : une fois la lecture faite, elle fait foi seule,
  // sinon un classement approximatif survivrait à la lecture qui le corrige.
  const devines = tagsMetadonnees(l).filter((tag) => tag.categorie === "type" || !analysee);
  const fusion = [...(persistes.get(l.id) ?? []), ...devines];
  const tags = fusion.filter((tag, index) => fusion.findIndex((t) => t.libelle === tag.libelle) === index);
  return {
    id: l.id, insee: l.insee, commune: l.commune,
    // Une date de séance n'est écrite que lorsqu'un agent l'a réellement lue,
    // sur la source ou dans l'acte. Ce garde-fou filtrait autrefois les dates
    // qu'un collecteur scripté inventait en datant la « séance » du jour de
    // sa moisson : ce script n'existe plus, et masquer une date lue serait
    // désormais perdre une information vraie.
    dateSeance: l.date_seance,
    numero: l.numero, titre: l.titre, service: l.service, direction: l.direction,
    rapporteur: l.rapporteur, source: l.source,
    statutLecture: l.statut_lecture, aPdf: l.pdf_chemin_local !== null,
    analysee,
    resumee: l.resumee === 1, pdfUrl: urlPubliqueSure(l.pdf_url),
    nMontantsSurs: l.n_montants, nPiecesCitees: l.n_pieces, nAlertes: l.n_alertes,
    moissonneeLe: l.moissonnee_le, tags,
  };
}

/** `limite = -1` : sans limite (convention SQLite). */
export function reunions(insee?: string, limite = 200): Reunion[] {
  const sql = insee
    ? `${SELECT_REUNIONS} WHERE d.insee=? ORDER BY s.date_seance DESC, d.id DESC LIMIT ?`
    : `${SELECT_REUNIONS} ORDER BY d.moissonnee_le DESC, d.id DESC LIMIT ?`;
  const persistes = tagsPersistes({ insee });
  return lire<LigneReunion>(sql, insee ? [insee, limite] : [limite]).map((l) => versReunion(l, persistes));
}

export type { EtatLecture } from "./etat-lecture.ts";

export type FiltresReunions = {
  q?: string;
  insee?: string;
  etat?: EtatLecture;
  type?: string;
  theme?: string;
  signal?: string;
  du?: string;
  au?: string;
};

/** Délibérations dont le résumé rédigé par l'agent contient `recherche` —
 *  seul le texte que l'IA a vraiment écrit après lecture du PDF, pas les
 *  montants ou citations bruts. Requête séparée plutôt qu'un JOIN dans
 *  SELECT_REUNIONS : le résumé est un texte long, inutile à charger sur
 *  chaque ligne du tableau quand aucune recherche n'est en cours. */
function idsResumeCorrespondant(recherche: string): Set<number> {
  const lignes = lire<{ deliberation_id: number; resume: string | null }>(
    "SELECT deliberation_id, resume FROM syntheses_reunions WHERE resume IS NOT NULL");
  return new Set(lignes
    .filter((l) => sansAccents(l.resume!).toLocaleLowerCase("fr").includes(recherche))
    .map((l) => l.deliberation_id));
}

/** Filtres de consultation : les tags restent stockes, mais ne saturent pas le tableau. */
export function reunionsFiltrees(filtres: FiltresReunions, limite?: number): Reunion[] {
  const recherche = sansAccents(filtres.q?.trim() ?? "").toLocaleLowerCase("fr");
  const idsResume = recherche ? idsResumeCorrespondant(recherche) : null;
  // Tout filtrer avant de borner : couper à mille d'abord faisait disparaître
  // en silence les actes plus anciens de tous les filtres.
  return reunions(filtres.insee, -1).filter((r) => {
    if (filtres.etat && etatLecture(r) !== filtres.etat) return false;
    if (filtres.du && (!r.dateSeance || r.dateSeance < filtres.du)) return false;
    if (filtres.au && (!r.dateSeance || r.dateSeance > filtres.au)) return false;
    if (filtres.type && !r.tags.some((tag) => tag.categorie === "type" && tag.libelle === filtres.type)) return false;
    if (filtres.theme && !r.tags.some((tag) => tag.categorie === "theme" && tag.libelle === filtres.theme)) return false;
    if (filtres.signal && !r.tags.some((tag) => tag.categorie === "signal" && tag.libelle === filtres.signal)) return false;
    if (recherche) {
      const texte = sansAccents([r.titre, r.commune, r.numero, r.service, r.direction].filter(Boolean).join(" ")).toLocaleLowerCase("fr");
      if (!texte.includes(recherche) && !idsResume!.has(r.id)) return false;
    }
    return true;
  }).slice(0, limite);
}

export function optionsTags(): { types: string[]; themes: string[]; signals: string[] } {
  const tags = reunions(undefined, -1).flatMap((r) => r.tags);
  const uniques = (categorie: CategorieTag) => [...new Set(tags.filter((tag) => tag.categorie === categorie).map((tag) => tag.libelle))].sort((a, b) => a.localeCompare(b, "fr"));
  return { types: uniques("type"), themes: uniques("theme"), signals: uniques("signal") };
}

export function reunion(id: number): Reunion | null {
  const l = lire<LigneReunion>(`${SELECT_REUNIONS} WHERE d.id=?`, [id])[0];
  return l ? versReunion(l, tagsPersistes({ id })) : null;
}

/** Une commune est designee par son code INSEE, un EPCI (agglo, metropole,
 *  communaute de communes) par son SIREN. Le type vient de la base : c'est
 *  une colonne generee du schema (`scripts/base.py`) qui le derive du code,
 *  le dashboard ne refait pas la regle. */
export type TypeCollectivite = "commune" | "epci";

export type CommuneMoissonnee = {
  insee: string; commune: string | null; type: TypeCollectivite;
  nReunions: number; nLues: number; derniere: string;
  /** Actes dont le PDF est archivé : les seuls qu'on puisse lire. */
  nArchivees: number;
  /** Suivi actif (mode `surveiller`), pas juste "a des actes en base" :
   *  voir AGENTS.md et SKILL.md, « Suivi actif, et consultation ponctuelle ». */
  suivie: boolean;
};

export function communesMoissonnees(): CommuneMoissonnee[] {
  // Table ajoutee apres coup : une base plus ancienne, jamais repassee par
  // `scripts/base.py`, peut ne pas l'avoir encore. Absente -> personne n'est
  // marque suivi, jamais une erreur qui casse toute la page.
  const colonneSuivi = tableExiste("suivi")
    ? "COALESCE((SELECT actif FROM suivi WHERE suivi.insee = deliberations.insee), 0)"
    : "0";
  return lire<{ insee: string; commune: string | null; type_collectivite: TypeCollectivite; n_reunions: number; n_lues: number; n_archivees: number; derniere: string; suivie: number }>(
    `SELECT insee, MAX(commune) AS commune, MAX(type_collectivite) AS type_collectivite,
            COUNT(*) AS n_reunions,
            SUM(CASE WHEN EXISTS(SELECT 1 FROM syntheses_reunions y
                                 WHERE y.deliberation_id = deliberations.id)
                     THEN 1 ELSE 0 END) AS n_lues,
            SUM(pdf_chemin_local IS NOT NULL) AS n_archivees,
            MAX(moissonnee_le) AS derniere,
            MAX(${colonneSuivi}) AS suivie
     FROM deliberations GROUP BY insee ORDER BY commune COLLATE NOCASE`,
  ).map((r) => ({
    insee: r.insee, commune: r.commune, type: r.type_collectivite ?? "commune",
    nReunions: r.n_reunions, nLues: r.n_lues, nArchivees: r.n_archivees, derniere: r.derniere,
    suivie: r.suivie === 1,
  }));
}

/** Part lue des actes archivés. Rapportée à tous les actes, Paris affichait
 *  4 % alors que ses 150 recueils non téléchargés le sont par choix (--limite),
 *  pas par retard de lecture. */
export function progressionLecture(c: Pick<CommuneMoissonnee, "nLues" | "nArchivees">): number {
  return c.nArchivees ? Math.round((c.nLues / c.nArchivees) * 100) : 0;
}

export function communeMoissonnee(insee: string): CommuneMoissonnee | null {
  return communesMoissonnees().find((c) => c.insee === insee) ?? null;
}

/** Code INSEE de commune (5 caracteres) ou SIREN d'EPCI (9 chiffres). */
export function codeCollectiviteValide(code: string): boolean {
  return /^[0-9][0-9AB][0-9]{3}$/i.test(code) || /^\d{9}$/.test(code);
}

export type Rattachement = { siren: string; nom: string; connue: boolean };

/** Intercommunalite dont depend une commune. `connue` dit si elle a deja des
 *  actes en base (a ne pas confondre avec `CommuneMoissonnee.suivie`, le
 *  suivi actif) : sinon on nomme l'agglo sans promettre une fiche vide. */
export function epciDeLaCommune(insee: string): Rattachement | null {
  const [ligne] = lire<{ epci_siren: string; epci_nom: string; connue: number }>(
    `SELECT a.epci_siren, a.epci_nom,
            EXISTS(SELECT 1 FROM deliberations d WHERE d.insee = a.epci_siren) AS connue
     FROM appartenances_epci a WHERE a.insee = ?`,
    [insee],
  );
  return ligne ? { siren: ligne.epci_siren, nom: ligne.epci_nom, connue: ligne.connue === 1 } : null;
}

export type Statistiques = { collectivites: number; reunions: number; lues: number; pdf: number; montants: number };
export function statistiques(): Statistiques {
  return lire<Statistiques>(`
    SELECT COUNT(DISTINCT insee) AS collectivites, COUNT(*) AS reunions,
           SUM(CASE WHEN EXISTS(SELECT 1 FROM syntheses_reunions y
                                WHERE y.deliberation_id = deliberations.id)
                    THEN 1 ELSE 0 END) AS lues,
           SUM(CASE WHEN pdf_chemin_local IS NOT NULL THEN 1 ELSE 0 END) AS pdf,
           (SELECT COUNT(*) FROM montants_extraits
             WHERE verifie=1 AND retenu=1 AND decision_financiere=1) AS montants
    FROM deliberations
  `)[0] ?? { collectivites: 0, reunions: 0, lues: 0, pdf: 0, montants: 0 };
}

/** Tout montant lu ici a été qualifié par un agent : il porte sa phrase de
 *  preuve et son `explication`. La fiche décide ensuite de l'afficher ou non
 *  sur `verifie`/`retenu`/`decisionFinanciere` (invariant 9). */
export type MontantExtrait = {
  valeur: number;
  suffixe: string | null;
  phrase: string;
  pointOrdreJour: string | null;
  nature: string;
  decisionFinanciere: number;
  verifie: number;
  retenu: number;
  explication: string | null;
};
export function montantsDe(id: number): MontantExtrait[] {
  return lire<{
    valeur: number; suffixe: string | null; phrase: string;
    point_ordre_jour: string | null; nature: string; decision_financiere: number; verifie: number; retenu: number; explication: string | null;
  }>("SELECT valeur, suffixe, phrase, point_ordre_jour, nature, decision_financiere, verifie, retenu, explication FROM montants_extraits WHERE deliberation_id=? ORDER BY valeur DESC", [id]).map((m) => ({
    valeur: m.valeur, suffixe: m.suffixe, phrase: m.phrase,
    pointOrdreJour: m.point_ordre_jour, nature: m.nature,
    decisionFinanciere: m.decision_financiere, verifie: m.verifie, retenu: m.retenu, explication: m.explication,
  }));
}

export type PieceCitee = { id: number; nature: string; statut: string };
export function piecesCiteesDe(id: number): PieceCitee[] {
  return lire<PieceCitee>("SELECT id, nature, statut FROM pieces_citees WHERE deliberation_id=? ORDER BY nature", [id]);
}

export function alertesDe(id: number): string[] {
  return lire<{ point_ordre_jour: string }>("SELECT point_ordre_jour FROM alertes_donnees_personnelles WHERE deliberation_id=?", [id]).map((r) => r.point_ordre_jour);
}

export type PointOrdreJour = { ordre: number; titre: string; decision: string | null; resultat_vote: string | null; est_budget: number };
export function pointsOrdreJourDe(id: number): PointOrdreJour[] {
  if (!tableExiste("points_ordre_jour")) return [];
  return lire<PointOrdreJour>("SELECT ordre, titre, decision, resultat_vote, est_budget FROM points_ordre_jour WHERE deliberation_id=? ORDER BY ordre", [id]);
}

/** L'existence d'une synthèse vaut preuve qu'un agent a lu le PDF en entier :
 *  sans elle, la fiche annonce « pas encore lu » au lieu de présenter des
 *  fragments comme une analyse. `statut_lecture='lu'` ne dit, lui,
 *  que « texte récupéré ». */
export type SyntheseReunion = { nombrePresents: number | null; voteGlobal: string | null; nombrePoints: number; nombreDecisions: number; resume: string | null };
export function syntheseDe(id: number): SyntheseReunion | null {
  if (!tableExiste("syntheses_reunions")) return null;
  const l = lire<{ nombre_presents: number | null; vote_global: string | null; nombre_points: number; nombre_decisions: number; resume: string | null }>(
    "SELECT nombre_presents, vote_global, nombre_points, nombre_decisions, resume FROM syntheses_reunions WHERE deliberation_id=?", [id],
  )[0];
  return l ? { nombrePresents: l.nombre_presents, voteGlobal: l.vote_global, nombrePoints: l.nombre_points, nombreDecisions: l.nombre_decisions, resume: l.resume } : null;
}

/** Le chemin provient exclusivement de la base, jamais de la requete. */
export function pdfDe(id: number): { cheminLocal: string; titre: string } | null {
  const l = lire<{ pdf_chemin_local: string | null; titre: string }>("SELECT pdf_chemin_local, titre FROM deliberations WHERE id=?", [id])[0];
  return l?.pdf_chemin_local ? { cheminLocal: cheminPdf(l.pdf_chemin_local), titre: l.titre } : null;
}
