/**
 * Lecture de la base de délibérations collectées : jointure séance, comptage
 * des pièces citées et des alertes, tri par date.
 *
 *   node --test dashboard/test/reunions.test.ts
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

const dossierTmp = fs.mkdtempSync(path.join(os.tmpdir(), "ft-reunions-"));
const chemin = path.join(dossierTmp, "deliberations.db");

/** Sous-ensemble du schéma réel de scripts/base.py. */
function monterBase() {
  const db = new DatabaseSync(chemin);
  db.exec(`
    CREATE TABLE seances (
      id INTEGER PRIMARY KEY, insee TEXT, date_seance TEXT, source TEXT, moissonnee_le TEXT);
    CREATE TABLE deliberations (
      id INTEGER PRIMARY KEY, seance_id INTEGER, insee TEXT, commune TEXT, numero TEXT,
      titre TEXT, service TEXT, direction TEXT, rapporteur TEXT, source TEXT,
      doc_id_source TEXT, pdf_url TEXT, pdf_chemin_local TEXT,
      statut_lecture TEXT, moissonnee_le TEXT,
      type_collectivite TEXT GENERATED ALWAYS AS
        (CASE WHEN length(insee)=9 THEN 'epci' ELSE 'commune' END) VIRTUAL);
    CREATE TABLE montants_extraits (
      id INTEGER PRIMARY KEY, deliberation_id INTEGER, valeur REAL, suffixe TEXT,
      phrase TEXT, point_ordre_jour TEXT,
      nature TEXT DEFAULT 'Montant mentionné', decision_financiere INTEGER DEFAULT 0,
      verifie INTEGER DEFAULT 0, retenu INTEGER DEFAULT 0, explication TEXT);
    CREATE TABLE pieces_citees (
      id INTEGER PRIMARY KEY, deliberation_id INTEGER, nature TEXT, statut TEXT);
    CREATE TABLE alertes_donnees_personnelles (
      id INTEGER PRIMARY KEY, deliberation_id INTEGER, point_ordre_jour TEXT);
    CREATE TABLE tags_automatiques (
      id INTEGER PRIMARY KEY, deliberation_id INTEGER, libelle TEXT, categorie TEXT, source TEXT);
    CREATE TABLE points_ordre_jour (
      id INTEGER PRIMARY KEY, deliberation_id INTEGER, ordre INTEGER, titre TEXT,
      decision TEXT, resultat_vote TEXT, est_budget INTEGER);
    CREATE TABLE syntheses_reunions (
      deliberation_id INTEGER PRIMARY KEY, nombre_presents INTEGER, vote_global TEXT,
      nombre_points INTEGER, nombre_decisions INTEGER, resume TEXT);
    CREATE TABLE appartenances_epci (
      insee TEXT PRIMARY KEY, epci_siren TEXT, epci_nom TEXT, releve_le TEXT);

    INSERT INTO appartenances_epci (insee,epci_siren,epci_nom,releve_le) VALUES
      ('99001','900000001','Métropole Exemple','2026-09-21T08:00:00Z'),
      ('99002','900000002','Communauté de communes des Coteaux','2026-09-21T08:00:00Z');

    INSERT INTO seances (id,insee,date_seance,source,moissonnee_le) VALUES
      (1,'99001','2026-06-19','portail','2026-09-04T10:00:00Z'),
      (2,'99001','2026-01-15','portail','2026-09-04T10:00:00Z');
    INSERT INTO deliberations
      (id,seance_id,insee,commune,numero,titre,service,direction,rapporteur,source,
       doc_id_source,pdf_chemin_local,statut_lecture,moissonnee_le) VALUES
      (1,1,'99001','Bourg-Exemple','26/216','Procès-verbal de la séance','Subventions et vie associative',
       'Affaires juridiques','M. Deslandes','portail','226028',
       '${path.join(dossierTmp, "a.pdf").replace(/\\/g, "\\\\")}','lu',
       '2026-09-04T10:01:00Z'),
      (2,NULL,'99002','Petiteville',NULL,'Compte rendu du 12 mars : subvention au club',NULL,NULL,NULL,
       'site','abc123',NULL,'brut','2026-09-04T09:00:00Z'),
      (3,NULL,'900000001','Métropole Exemple',NULL,'Délibérations',NULL,NULL,NULL,
       'site','def456',NULL,'brut','2026-09-21T09:00:00Z'),
      (4,2,'99001','Bourg-Exemple','26/217','Admission en non-valeur',NULL,NULL,NULL,
       'portail','226029',
       '${path.join(dossierTmp, "a.pdf").replace(/\\/g, "\\\\")}','lu',
       '2026-09-04T10:01:00Z'),
      (5,2,'99001','Bourg-Exemple','26/218','Subvention au club de basket',NULL,NULL,NULL,
       'portail','226030',
       '${path.join(dossierTmp, "a.pdf").replace(/\\/g, "\\\\")}','lu',
       '2026-09-04T10:01:00Z');
    INSERT INTO montants_extraits
      (deliberation_id,valeur,suffixe,phrase,point_ordre_jour,nature,decision_financiere,verifie,retenu,explication) VALUES
      -- Lue, un montant "examiné" (explication non nulle) mais écarté : ni
      -- dépense actée, ni résumé. Doit rester "pas-analyse", pas "analyse".
      (4,226444.0,NULL,'Numéro de dossier cité dans le corps du texte.',
       NULL,'Montant mentionné',0,1,0,'Numéro de dossier, pas un montant financier.'),
      (1,22128.0,NULL,'Achat de matériel de voirie 22 128,00 EUR.',
       '26/216 Achat de matériel','Dépense',1,1,1,'Le montant est associé à un achat décidé.'),
      -- Une dépense actée (affichée) mais sans résumé : analyse commencée,
      -- pas terminée. Ne doit toujours pas se marquer "analyse".
      (5,18576.0,NULL,'Subvention exceptionnelle de 18 576,00 EUR TTC.',
       NULL,'Dépense',1,1,1,'Formulation opératoire explicite et vote à l''unanimité.');
    INSERT INTO pieces_citees (deliberation_id,nature,statut) VALUES
      (1,'devis','reperee'), (1,'convention','demandee');
    INSERT INTO alertes_donnees_personnelles (deliberation_id,point_ordre_jour) VALUES
      (1,'SECOURS EXCEPTIONNEL');
    INSERT INTO tags_automatiques (deliberation_id,libelle,categorie,source) VALUES
      (1,'Budget et fiscalité','theme','contenu'),
      (1,'Dépense détectée','signal','contenu');
    INSERT INTO points_ordre_jour (deliberation_id,ordre,titre,decision,resultat_vote,est_budget) VALUES
      (1,1,'BUDGET 2026','Le Conseil adopte le budget.','Adopte a l unanimite',1);
    INSERT INTO syntheses_reunions (deliberation_id,nombre_presents,vote_global,nombre_points,nombre_decisions,resume) VALUES
      (1,23,'Adopte a l unanimite',1,1,'Le conseil a adopte le budget 2026.');
  `);
  db.close();
}

monterBase();
process.env.FT_DELIB_DB = chemin;
const reunionsLib = await import("../lib/reunions.ts");
const { etatLecture } = await import("../lib/etat-lecture.ts");

test("reunions() joint la date de séance et compte pièces citées et alertes", () => {
  const liste = reunionsLib.reunions();
  assert.equal(liste.length, 5);
  const bourg = liste.find((r) => r.id === 1)!;
  assert.equal(bourg.dateSeance, "2026-06-19");
  assert.equal(bourg.nMontantsSurs, 1);
  assert.equal(bourg.nPiecesCitees, 2);
  assert.equal(bourg.nAlertes, 1);
  assert.equal(bourg.aPdf, true);
  assert.ok(bourg.tags.some((tag) => tag.libelle === "Budget et fiscalité"));
});

test("un montant examiné puis écarté ne rend pas un document \"analysé\"", () => {
  // Délib 4 : lue, un montant porte une explication (donc "examiné") mais il
  // est écarté (retenu=0) — ce n'est pas une dépense affichable — et aucun
  // résumé n'existe. La fiche n'a rien à montrer : le badge doit rester
  // "pas-analyse", pas "analyse" au-dessus d'une page vide.
  const delib4 = reunionsLib.reunions("99001").find((r) => r.id === 4)!;
  assert.equal(delib4.analysee, false);
  assert.equal(delib4.nMontantsSurs, 0);
  assert.equal(etatLecture(delib4), "pas-analyse");
});

test("une dépense actée sans résumé ne rend pas un document \"analysé\"", () => {
  // Délib 5 : une dépense réellement affichable (verifie/retenu/decision
  // financière) mais aucune ligne dans syntheses_reunions. C'est une analyse
  // commencée, pas terminée (AGENTS.md, invariant 6) : le badge doit rester
  // "pas-analyse" tant que le résumé n'est pas écrit.
  const delib5 = reunionsLib.reunions("99001").find((r) => r.id === 5)!;
  assert.equal(delib5.nMontantsSurs, 1);
  assert.equal(delib5.analysee, false);
  assert.equal(etatLecture(delib5), "pas-analyse");
});

test("reunions(insee) filtre sur une seule commune", () => {
  const liste = reunionsLib.reunions("99002");
  assert.equal(liste.length, 1);
  assert.equal(liste[0].commune, "Petiteville");
  assert.equal(liste[0].dateSeance, null); // aucune date de séance publiée sur le site
});

test("pdfDe() ne renvoie rien pour une délibération sans PDF téléchargé", () => {
  assert.equal(reunionsLib.pdfDe(2), null);
  assert.equal(reunionsLib.pdfDe(1)?.titre, "Procès-verbal de la séance");
});

test("un chemin de PDF relatif se résout depuis la racine du dépôt, un absolu reste tel quel", () => {
  const racine = path.dirname(dossierTmp);
  assert.equal(reunionsLib.cheminPdf("data/deliberations/99001/a.pdf"),
    path.join(racine, "data", "deliberations", "99001", "a.pdf"));
  assert.equal(reunionsLib.pdfDe(1)?.cheminLocal, path.join(dossierTmp, "a.pdf"));
});

test("la progression de lecture se rapporte aux PDF archivés, pas aux actes seulement référencés", () => {
  const bourg = reunionsLib.communeMoissonnee("99001")!;
  assert.equal(bourg.nArchivees, 3);
  assert.equal(reunionsLib.progressionLecture(bourg), Math.round((bourg.nLues / 3) * 100));
  const petiteville = reunionsLib.communeMoissonnee("99002")!;
  assert.equal(petiteville.nArchivees, 0);
  assert.equal(reunionsLib.progressionLecture(petiteville), 0); // rien d'archivé : pas de division par zéro
});

test("les tags d'une collectivité restent les siens quand on ne lit qu'elle", () => {
  const seule = reunionsLib.reunions("99001", -1).find((r) => r.id === 1)!;
  const toutes = reunionsLib.reunions(undefined, -1).find((r) => r.id === 1)!;
  assert.deepEqual(seule.tags, toutes.tags);
});

test("les filtres portent sur toute la base, pas sur ses mille dernières lignes", () => {
  assert.equal(reunionsLib.reunionsFiltrees({}, 2).length, 2);
  assert.equal(reunionsLib.reunions(undefined, -1).length, 5);
});

test("alertesDe() ne renvoie que l'intitulé du point, jamais un contenu", () => {
  const alertes = reunionsLib.alertesDe(1);
  assert.deepEqual(alertes, ["SECOURS EXCEPTIONNEL"]);
});

test("communesMoissonnees() une ligne par commune, triée par nom", () => {
  const communes = reunionsLib.communesMoissonnees();
  assert.equal(communes.length, 3);
  // Bourg-Exemple, puis Métropole Exemple, puis Petiteville.
  assert.equal(communes[0].insee, "99001");
});

test("communesMoissonnees() : suivie=false quand la table `suivi` n'existe pas", () => {
  // La fixture ne cree pas cette table (ajoutee apres coup a scripts/base.py) :
  // une base plus ancienne doit degrader proprement, jamais planter la page.
  const parCode = new Map(reunionsLib.communesMoissonnees().map((c) => [c.insee, c]));
  assert.equal(parCode.get("99001")?.suivie, false);
});

test("le type distingue une commune d'un EPCI, sans que le dashboard refasse la règle", () => {
  const parCode = new Map(reunionsLib.communesMoissonnees().map((c) => [c.insee, c]));
  assert.equal(parCode.get("99001")?.type, "commune");
  assert.equal(parCode.get("900000001")?.type, "epci");
  // Un SIREN doit rester une adresse valide de fiche, au meme titre qu'un code INSEE.
  assert.ok(reunionsLib.codeCollectiviteValide("900000001"));
  assert.ok(reunionsLib.codeCollectiviteValide("99001"));
  assert.ok(reunionsLib.codeCollectiviteValide("2A004"));
  assert.ok(!reunionsLib.codeCollectiviteValide("abc"));
});

test("epciDeLaCommune() dit si l'agglo de rattachement est deja moissonnee", () => {
  const bourg = reunionsLib.epciDeLaCommune("99001");
  assert.equal(bourg?.nom, "Métropole Exemple");
  assert.equal(bourg?.connue, true); // la metropole a des deliberations dans la base

  const petiteville = reunionsLib.epciDeLaCommune("99002");
  assert.equal(petiteville?.nom, "Communauté de communes des Coteaux");
  assert.equal(petiteville?.connue, false); // nommee, mais pas de fiche a promettre

  assert.equal(reunionsLib.epciDeLaCommune("99999"), null);
});

test("la synthese et les points structures sont lus sans ecrire dans la base", () => {
  assert.equal(reunionsLib.syntheseDe(1)?.nombrePresents, 23);
  assert.equal(reunionsLib.pointsOrdreJourDe(1)[0].est_budget, 1);
});

test("le resume est la preuve qu'un agent a lu le document", () => {
  assert.equal(reunionsLib.syntheseDe(1)?.resume, "Le conseil a adopte le budget 2026.");
  // Delib 2 : PDF recupere mais jamais lu -> aucune synthese, donc aucune affirmation.
  assert.equal(reunionsLib.syntheseDe(2), null);
});

test("l'état de lecture affiché et l'état filtré sont le même vocabulaire", () => {
  const [bourg] = reunionsLib.reunions("99001");
  // Délibération 1 : PDF présent + synthèse écrite -> analysée.
  assert.equal(etatLecture(bourg), "analyse");
  // Délibération 2 : aucun PDF téléchargé.
  const [petiteville] = reunionsLib.reunions("99002");
  assert.equal(etatLecture(petiteville), "pas-telecharge");
  // Filtrer sur un état ne doit ramener que des lignes portant cet état.
  for (const etat of ["analyse", "pas-telecharge"] as const) {
    for (const r of reunionsLib.reunionsFiltrees({ etat })) {
      assert.equal(etatLecture(r), etat);
    }
  }
});

test("une date de séance s'affiche quand elle existe, et seulement alors", () => {
  // Collecte depuis le site officiel, sans date publiée : rien à afficher.
  const [petiteville] = reunionsLib.reunions("99002");
  assert.equal(petiteville.source, "site");
  assert.equal(petiteville.dateSeance, null);
  // La voie portail, elle, connaît la vraie date.
  const [bourg] = reunionsLib.reunions("99001");
  assert.equal(bourg.dateSeance, "2026-06-19");
});

test("reunionsFiltrees() combine ville, lecture, type, theme et dates", () => {
  const resultat = reunionsLib.reunionsFiltrees({
    insee: "99001",
    etat: "analyse",
    type: "Procès-verbal",
    theme: "Budget et fiscalité",
    signal: "Dépense détectée",
    du: "2026-01-01",
    au: "2026-12-31",
  });
  assert.equal(resultat.length, 1);
  assert.equal(resultat[0].id, 1);
});

test("la recherche porte aussi sur le résumé rédigé par l'agent", () => {
  // "2026" n'apparaît ni dans le titre, le numéro, le service ou la direction
  // de la délib 1 — seulement dans son résumé ("budget 2026").
  const parResume = reunionsLib.reunionsFiltrees({ q: "budget 2026" });
  assert.ok(parResume.some((r) => r.id === 1));
  // Une simple citation brute (montant, numéro de dossier) n'est pas un
  // résumé : elle ne doit pas se substituer à la lecture.
  assert.equal(reunionsLib.reunionsFiltrees({ q: "226444" }).length, 0);
});

test("la lecture d'un agent remplace le classement par motif, elle ne s'y ajoute pas", () => {
  // Délib 1 : lue par un agent. Son service dit « Subventions », mais l'agent a
  // lu le texte et n'a pas retenu ce sujet : le motif ne doit pas le rajouter.
  const [bourg] = reunionsLib.reunions("99001");
  assert.deepEqual(bourg.tags.filter((t) => t.categorie === "theme").map((t) => t.libelle),
    ["Budget et fiscalité"]);
  // Le type, lui, se déduit toujours de l'intitulé : aucun agent ne l'écrit.
  assert.ok(bourg.tags.some((t) => t.categorie === "type" && t.libelle === "Procès-verbal"));

  // Délib 2 : jamais lue. Le motif reste le seul classement disponible.
  const [petiteville] = reunionsLib.reunions("99002");
  assert.equal(petiteville.analysee, false);
  assert.ok(petiteville.tags.some((t) => t.categorie === "theme" && t.libelle === "Subventions"));
});

test.after(() => {
  reunionsLib.fermer();
  fs.rmSync(dossierTmp, { recursive: true, force: true });
});

test("une somme garde ses centimes en entier, un montant rond n'en invente pas", async () => {
  const { montant } = await import("../lib/format.ts");
  const espaces = (s: string) => s.replace(/\s/g, " ");
  assert.equal(espaces(montant(697155.5)), "697 155,50");
  assert.equal(espaces(montant(2348456)), "2 348 456");
  assert.equal(espaces(montant(21.6)), "21,60");
});
