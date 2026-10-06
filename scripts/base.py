#!/usr/bin/env python3
"""Cree et fait evoluer data/deliberations.db. Ne fait rien d'autre.

  base.py                      cree ou migre la base, puis resume son contenu
  base.py --db <chemin>        sur une autre base
  base.py --selftest           controle, sans reseau

Ce fichier est le **contrat de schema** entre l'agent qui remplit la base et le
tableau de bord qui la lit. Les deux dependent des memes noms de tables et de
colonnes : les ecrire ici, une fois, plutot que de laisser un agent les
re-deduire a chaque execution. Un schema qui derive casse le dashboard en
silence, sans qu'aucune requete n'echoue -- une colonne absente rend une
section vide, pas une erreur.

C'est aussi la seule chose de tout le pipeline qui ne se juge pas. Trouver le
site d'une commune, reconnaitre une page de deliberations, decider qu'un
montant est une depense votee : tout ca demande de regarder et de comprendre,
donc revient a l'agent (voir .claude/skills/france-transparence/SKILL.md).
Creer dix tables, non : c'est une suite d'instructions fixes, et un script la
rejoue a l'identique.

Aucun reseau, aucune dependance hors bibliotheque standard.
"""
import argparse
import os
import re
import sqlite3
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
DATA = os.path.join(RACINE, "data")
DB_DEFAUT = os.path.join(DATA, "deliberations.db")
PDF_DIR = os.path.join(DATA, "deliberations")
REGISTRE = os.path.join(DATA, "portails.yaml")

# `source` dit d'ou vient un acte, et surtout ce qu'on peut en croire :
#   portail : un portail de deliberations dedie. Numero, service, direction,
#             rapporteur et **vraie date de seance** sont publies.
#   site    : une page du site officiel. On n'a que le PDF et l'intitule de son
#             lien ; la date de seance est inconnue, et le dashboard affiche
#             « date non renseignee » plutot que d'inventer.
SOURCES = ("portail", "site")
# Natures qui ne sont jamais une decision financiere votee : un chiffre de
# debat, de comparaison ou d'estimation (invariant 9).
NATURES_NON_DECIDEES = {"Estimation de la part d'un tiers", "Estimation",
                        "Montant historique", "Montant de référence", "Montant mentionné"}


def relatif(chemin):
    """Chemin d'un PDF tel qu'il s'ecrit en base : relatif a la racine du
    depot, en `/`. Un chemin absolu cassait toute l'archive au premier
    deplacement du dossier. Hors du depot (fixture de test), reste absolu."""
    try:
        rel = os.path.relpath(os.path.abspath(chemin), RACINE)
    except ValueError:          # autre lecteur, sous Windows
        return os.path.abspath(chemin)
    return os.path.abspath(chemin) if rel.startswith("..") else rel.replace(os.sep, "/")


def identifiant(url):
    """L'identite d'un acte de site, faute d'identifiant publie par la source.

    Le chemin complet de son URL, pas le seul nom du fichier : un village
    publie `2023/pv.pdf` puis `2026/pv.pdf`, et le nom seul les confondait --
    le second ecrasait le premier en silence. Ni l'hote (www, http/https
    changent d'une refonte a l'autre) ni la query (les CDN y signent des liens
    qui expirent : elle change a chaque passage). Sauf quand le chemin n'est
    pas le document mais le script qui le sert (`/cms_viewFile.php?idtf=6993`) :
    c'est alors la query qui distingue un acte d'un autre."""
    import hashlib
    from urllib.parse import unquote, urlparse
    u = urlparse(url)
    cle = unquote(u.path) if u.path.lower().endswith(".pdf") else f"{unquote(u.path)}?{u.query}"
    return hashlib.sha256(cle.encode()).hexdigest()[:16]


def sortie_utf8():
    """Une console Windows en cp1252 fait planter un print() sur le premier
    caractere hors de sa table, et rend « B�thune » a l'agent qui lit."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

SCHEMA = """
-- Ce qu'on a deja trouve pour une collectivite : l'adresse ou ses actes sont
-- publies. Ecrit par l'agent apres une recherche reussie, pour que la
-- suivante parte directement du bon endroit. Copie de data/portails.yaml, qui
-- fait seul autorite : scripts/collecter.py la resynchronise a chaque passage.
CREATE TABLE IF NOT EXISTS portails (
  insee        TEXT PRIMARY KEY,
  nom          TEXT NOT NULL,
  type         TEXT NOT NULL CHECK (type IN ('portail','site')),
  url          TEXT,
  verifie_le   TEXT NOT NULL,
  notes        TEXT
);

-- Collectivites mises en SUIVI ACTIF (mode `surveiller`, tache planifiee),
-- par opposition a une consultation ponctuelle (`analyser`, `recuperer`,
-- `rattraper`). Pas de miroir yaml, a la difference de `portails` : ce choix
-- est personnel, il n'a pas vocation a etre partage. Une collectivite
-- absente d'ici n'a jamais ete mise en suivi -- elle a pu etre consultee
-- sans que ca l'y inscrive. Le dashboard le lit pour l'afficher ; l'agent le
-- lit avant toute demande qui ne nomme aucune collectivite (voir SKILL.md).
CREATE TABLE IF NOT EXISTS suivi (
  insee   TEXT PRIMARY KEY,
  actif   INTEGER NOT NULL CHECK (actif IN (0,1)),
  maj_le  TEXT NOT NULL
);

-- Rattachement d'une commune a son intercommunalite, releve sur geo.api.gouv.fr
-- au moment de la collecte. `epci_siren` est la meme cle que `insee` cote EPCI :
-- la fiche de l'agglo est donc atteignable depuis celle de la commune, que
-- cette agglo soit deja suivie ou pas encore.
CREATE TABLE IF NOT EXISTS appartenances_epci (
  insee        TEXT PRIMARY KEY,
  epci_siren   TEXT NOT NULL,
  epci_nom     TEXT NOT NULL,
  releve_le    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seances (
  id             INTEGER PRIMARY KEY,
  insee          TEXT NOT NULL,
  date_seance    TEXT NOT NULL CHECK (date(date_seance) IS date_seance),
  source         TEXT NOT NULL CHECK (source IN ('portail','site')),
  moissonnee_le  TEXT NOT NULL,
  UNIQUE (insee, date_seance, source)
);
CREATE INDEX IF NOT EXISTS idx_seances_insee ON seances(insee);

CREATE TABLE IF NOT EXISTS deliberations (
  id                    INTEGER PRIMARY KEY,
  seance_id             INTEGER REFERENCES seances(id),
  insee                 TEXT NOT NULL,
  commune               TEXT,
  numero                TEXT,
  titre                 TEXT NOT NULL,
  service               TEXT,
  direction             TEXT,
  rapporteur            TEXT,
  source                TEXT NOT NULL CHECK (source IN ('portail','site')),
  doc_id_source         TEXT NOT NULL,
  pdf_url               TEXT,
  pdf_chemin_local      TEXT,
  pdf_empreinte_sha256  TEXT,
  -- 'brut' : reference, PDF pas encore telecharge ou pas encore lu.
  -- 'lu'   : l'agent a lu le PDF en entier.
  -- 'echec': PDF illisible ; ne jamais presenter de synthese partielle.
  statut_lecture        TEXT NOT NULL DEFAULT 'brut'
                        CHECK (statut_lecture IN ('brut','lu','echec')),
  moissonnee_le         TEXT NOT NULL,
  -- Une collectivite est identifiee par un code INSEE (commune, 5 caracteres)
  -- ou par un SIREN (EPCI, 9 chiffres). Colonne generee: la regle vit ici seule,
  -- rien a backfiller ni a repasser dans chaque INSERT.
  type_collectivite     TEXT GENERATED ALWAYS AS
                        (CASE WHEN length(insee)=9 THEN 'epci' ELSE 'commune' END) VIRTUAL,
  UNIQUE (insee, source, doc_id_source)
);
CREATE INDEX IF NOT EXISTS idx_delib_insee ON deliberations(insee);
CREATE INDEX IF NOT EXISTS idx_delib_statut ON deliberations(statut_lecture);

CREATE TABLE IF NOT EXISTS montants_extraits (
  id                INTEGER PRIMARY KEY,
  deliberation_id   INTEGER NOT NULL REFERENCES deliberations(id),
  valeur            REAL NOT NULL,
  suffixe           TEXT,
  phrase            TEXT NOT NULL,
  point_ordre_jour  TEXT,
  nature            TEXT NOT NULL DEFAULT 'Montant mentionné',
  decision_financiere INTEGER NOT NULL DEFAULT 0 CHECK (decision_financiere IN (0,1)),
  verifie           INTEGER NOT NULL DEFAULT 0 CHECK (verifie IN (0,1)),
  retenu            INTEGER NOT NULL DEFAULT 0 CHECK (retenu IN (0,1)),
  explication       TEXT
);
CREATE INDEX IF NOT EXISTS idx_montants_delib ON montants_extraits(deliberation_id);

CREATE TABLE IF NOT EXISTS pieces_citees (
  id                INTEGER PRIMARY KEY,
  deliberation_id   INTEGER NOT NULL REFERENCES deliberations(id),
  nature            TEXT NOT NULL,
  statut            TEXT NOT NULL DEFAULT 'reperee'
                    CHECK (statut IN ('reperee','demandee','obtenue','ecartee'))
);
CREATE INDEX IF NOT EXISTS idx_pieces_delib ON pieces_citees(deliberation_id);

-- Jamais le contenu du passage, seulement le point de l'ordre du jour ou
-- l'agent qui a lu le PDF a repere un signal de donnees personnelles.
CREATE TABLE IF NOT EXISTS alertes_donnees_personnelles (
  id                INTEGER PRIMARY KEY,
  deliberation_id   INTEGER NOT NULL REFERENCES deliberations(id),
  point_ordre_jour  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags_automatiques (
  id                INTEGER PRIMARY KEY,
  deliberation_id   INTEGER NOT NULL REFERENCES deliberations(id),
  libelle           TEXT NOT NULL,
  categorie         TEXT NOT NULL CHECK (categorie IN ('type','theme','signal')),
  source            TEXT NOT NULL DEFAULT 'contenu'
                    CHECK (source IN ('metadonnees','contenu')),
  UNIQUE (deliberation_id, libelle)
);
CREATE INDEX IF NOT EXISTS idx_tags_delib ON tags_automatiques(deliberation_id);

CREATE TABLE IF NOT EXISTS points_ordre_jour (
  id                INTEGER PRIMARY KEY,
  deliberation_id   INTEGER NOT NULL REFERENCES deliberations(id),
  ordre             INTEGER NOT NULL,
  titre             TEXT NOT NULL,
  decision          TEXT,
  resultat_vote     TEXT,
  est_budget        INTEGER NOT NULL DEFAULT 0 CHECK (est_budget IN (0,1)),
  UNIQUE (deliberation_id, ordre)
);
CREATE INDEX IF NOT EXISTS idx_points_delib ON points_ordre_jour(deliberation_id);

CREATE TABLE IF NOT EXISTS syntheses_reunions (
  deliberation_id   INTEGER PRIMARY KEY REFERENCES deliberations(id),
  nombre_presents   INTEGER,
  vote_global       TEXT,
  nombre_points     INTEGER NOT NULL DEFAULT 0,
  nombre_decisions  INTEGER NOT NULL DEFAULT 0,
  -- Quelques phrases en francais courant : de quoi parle l'acte, ce qui a ete
  -- decide, ce que ca engage. Ecrit par l'agent qui a lu le PDF, jamais
  -- assemble a partir de mots-cles. L'existence d'une ligne ici vaut preuve
  -- qu'une lecture a eu lieu : sans elle, le dashboard dit "pas encore lu"
  -- plutot que d'afficher des fragments de tableau comme un ordre du jour.
  resume            TEXT
);
"""

# Une piece citee designe un TYPE de document, pas une occurrence : « annexes »
# et « annexe » sont la meme chose, « arrete » n'est qu'un « arrêté » dont
# l'extraction a perdu l'accent. Vocabulaire ferme, repris tel quel dans
# lecture.md (skill) et verifie par analyse.py avant toute ecriture.
PIECES_CANONIQUES = {
    "annexes": "annexe",
    "arrete": "arrêté", "arrête": "arrêté", "arretes": "arrêté", "arrêtés": "arrêté",
    "marche": "marché", "marches": "marché", "marchés": "marché",
    "etude": "étude", "etudes": "étude", "études": "étude",
    "factures": "facture", "facture acquittée": "facture", "facture acquittee": "facture",
    "contrat de prestation": "contrat", "contrats": "contrat",
    "conventions": "convention", "avenants": "avenant", "devis ": "devis",
    "rapports": "rapport", "bilans": "bilan", "offres": "offre",
    "délibérations": "délibération", "deliberation": "délibération",
    "procès-verbaux": "procès-verbal", "proces-verbal": "procès-verbal",
    "cctp": "CCTP", "ccap": "CCAP",
}


def _colonnes(con, table, generees=False):
    # table_xinfo, pas table_info : ce dernier masque les colonnes generees.
    pragma = "table_xinfo" if generees else "table_info"
    return {r["name"] for r in con.execute(f"PRAGMA {pragma}({table})")}


def _migrer(con):
    """Rattrape une base creee par une version anterieure. Additif et repetable."""
    colonnes_montants = _colonnes(con, "montants_extraits")
    for nom, definition in (
        ("point_ordre_jour", "TEXT"),
        ("nature", "TEXT NOT NULL DEFAULT 'Montant mentionné'"),
        ("decision_financiere", "INTEGER NOT NULL DEFAULT 0 CHECK (decision_financiere IN (0,1))"),
        ("verifie", "INTEGER NOT NULL DEFAULT 0 CHECK (verifie IN (0,1))"),
        ("retenu", "INTEGER NOT NULL DEFAULT 0 CHECK (retenu IN (0,1))"),
        ("explication", "TEXT"),
    ):
        if nom not in colonnes_montants:
            con.execute(f"ALTER TABLE montants_extraits ADD COLUMN {nom} {definition}")
    if "resume" not in _colonnes(con, "syntheses_reunions"):
        con.execute("ALTER TABLE syntheses_reunions ADD COLUMN resume TEXT")
    if "type_collectivite" not in _colonnes(con, "deliberations", generees=True):
        con.execute("ALTER TABLE deliberations ADD COLUMN type_collectivite TEXT "
                    "GENERATED ALWAYS AS (CASE WHEN length(insee)=9 THEN 'epci' "
                    "ELSE 'commune' END) VIRTUAL")
    # Une citation prouve l'existence d'une piece, jamais son absence dans le
    # dossier publie. L'ancien signal derive etait donc trompeur.
    con.execute("DELETE FROM tags_automatiques WHERE libelle='Annexe potentiellement manquante'")
    # `demande_id` etait le vestige d'un suivi de demandes de pieces jamais
    # construit : colonne jamais ecrite, jamais lue.
    if "demande_id" in _colonnes(con, "pieces_citees"):
        con.execute("ALTER TABLE pieces_citees DROP COLUMN demande_id")
        con.commit()  # sans ça le DDL reste dans la transaction et se perd
    # Normalisation des pieces citees, une seule fois : l'index unique qui suit
    # sert aussi de marqueur « deja fait » et empeche les doublons de revenir.
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='index' "
                       "AND name='idx_pieces_unique'").fetchone():
        for variante, canonique in PIECES_CANONIQUES.items():
            con.execute("UPDATE pieces_citees SET nature=? WHERE lower(nature)=?",
                        (canonique, variante))
        con.execute("DELETE FROM pieces_citees WHERE id NOT IN "
                    "(SELECT MIN(id) FROM pieces_citees GROUP BY deliberation_id, nature)")
        con.execute("CREATE UNIQUE INDEX idx_pieces_unique "
                    "ON pieces_citees(deliberation_id, nature)")
        con.commit()
    # `confiance` ('sur'/'probable') notait la fiabilite d'un detecteur par
    # expressions regulieres, remplace par le jugement d'un agent : plus jamais
    # relue. Sa presence marque une base d'avant l'agent. Purger d'abord les
    # candidats que ce detecteur y a laisses -- sans `explication`, personne n'a
    # qualifie la ligne -- puis retirer la colonne, ce qui desamorce ce bloc.
    if "confiance" in _colonnes(con, "montants_extraits"):
        efface = con.execute("DELETE FROM montants_extraits "
                             "WHERE explication IS NULL").rowcount
        con.execute("ALTER TABLE montants_extraits DROP COLUMN confiance")
        con.commit()
        if efface:
            print(f"migration : {efface} candidat(s) non qualifie(s) supprime(s).",
                  file=sys.stderr)
    # Deux vocabulaires nommaient les scripts disparus plutot que la realite :
    # la source ('webdelib' designait un produit, 'site_communal' une voie de
    # collecte scriptee) et le statut de lecture ('depouille', du verbe
    # depouiller). Ce qu'ils distinguent reste vrai : un portail donne la vraie
    # date de seance, une page de site non ; un PDF lu n'est pas un PDF
    # seulement reference. Un CHECK etant fige a la creation de la table, les
    # renommer impose de reconstruire la table.
    if "statut_depouillement" in _colonnes(con, "deliberations"):
        _reconstruire(con, "deliberations",
                      renommages={"statut_depouillement": "statut_lecture"},
                      mappages={"source": {"webdelib": "portail",
                                           "site_communal": "site"},
                                "statut_lecture": {"depouille": "lu"}})
    # Une date impossible (« 2026-14-00 ») est un numero d'acte mal lu par un
    # detecteur de dates : le CHECK la refuse desormais. Une base anterieure
    # n'a pas ce CHECK ; ses seances invalides partent avant la reconstruction.
    sql = con.execute("SELECT sql FROM sqlite_master WHERE type='table' "
                      "AND name='seances'").fetchone()
    if sql and "date(date_seance)" not in sql["sql"]:
        invalides = "SELECT id FROM seances WHERE date(date_seance) IS NOT date_seance"
        con.execute(f"UPDATE deliberations SET seance_id=NULL WHERE seance_id IN ({invalides})")
        con.execute(f"DELETE FROM seances WHERE id IN ({invalides})")
        _reconstruire(con, "seances", renommages={},
                      mappages={"source": {"webdelib": "portail", "site_communal": "site"}})
    # `seances.source` et `portails.type` portent le meme vocabulaire et le
    # meme CHECK a reecrire. Oublier `portails` ne se voit pas a la lecture :
    # ca ne casse qu'au premier enregistrement d'une collectivite.
    for table, colonne in (("seances", "source"), ("portails", "type")):
        sql = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                          (table,)).fetchone()
        if sql and "site_communal" in sql["sql"]:
            _reconstruire(con, table, renommages={},
                          mappages={colonne: {"webdelib": "portail",
                                              "site_communal": "site"}})
    # Le collecteur scripte, supprime depuis, datait la « seance » d'un site
    # communal du jour ou il passait : une date fausse, que le dashboard
    # masquait en bloc pour cette source. Il n'affiche plus que ce qu'un agent
    # a reellement lu, donc ces dates inventees doivent partir, sinon elles
    # remontent a l'ecran. Elles se reconnaissent a leur signature : date de
    # seance egale au jour de collecte. Une vraie seance collectee le jour
    # meme y ressemblerait, mais perdre une date vaut mieux qu'en afficher
    # des dizaines de fausses.
    fantomes = [r["id"] for r in con.execute(
        "SELECT id FROM seances WHERE source='site' "
        "AND date_seance = substr(moissonnee_le, 1, 10)")]
    if fantomes:
        marques = ",".join("?" * len(fantomes))
        con.execute(f"UPDATE deliberations SET seance_id=NULL "
                    f"WHERE seance_id IN ({marques})", fantomes)
        con.execute(f"DELETE FROM seances WHERE id IN ({marques})", fantomes)
        con.commit()
        print(f"migration : {len(fantomes)} seance(s) datee(s) du jour de collecte "
              f"supprimee(s) — date inventee, jamais publiee.", file=sys.stderr)
    # Invariant 9 : une decision financiere exige une preuve verifiee et une
    # nature decidee. Des lignes ecrites avant analyse.py le violaient ; les
    # masquer est la reponse du doute, jamais les promouvoir.
    marques = ",".join("?" * len(NATURES_NON_DECIDEES))
    n = con.execute(f"UPDATE montants_extraits SET decision_financiere=0 "
                    f"WHERE decision_financiere=1 AND (verifie=0 OR nature IN ({marques}))",
                    sorted(NATURES_NON_DECIDEES)).rowcount
    if n:
        print(f"migration : {n} montant(s) « decide(s) » sans preuve verifiee, masque(s).",
              file=sys.stderr)
    # `lu` sans resume n'est pas une lecture (invariant 6) : l'ancien pipeline
    # marquait lu tout PDF parcouru. Revenir a `brut` rend ces actes a la file
    # de lecture ; leurs montants restent, signales comme inacheves.
    n = con.execute("UPDATE deliberations SET statut_lecture='brut' WHERE statut_lecture='lu' "
                    "AND NOT EXISTS (SELECT 1 FROM syntheses_reunions s WHERE "
                    "s.deliberation_id=deliberations.id AND s.resume IS NOT NULL)").rowcount
    if n:
        print(f"migration : {n} acte(s) « lu(s) » sans resume, rendu(s) a la lecture.",
              file=sys.stderr)
    # L'identite d'un acte de site etait l'empreinte du seul nom de fichier ;
    # c'est desormais celle du chemin (voir identifiant()). Seules les lignes
    # qui portent encore l'ancienne empreinte changent : un identifiant publie
    # par un portail ou fixe par un collecteur ne lui ressemble pas. Une fois.
    if con.execute("PRAGMA user_version").fetchone()[0] < 1:
        import hashlib
        from urllib.parse import unquote, urlparse
        for r in con.execute("SELECT id, doc_id_source d, pdf_url u FROM deliberations "
                             "WHERE pdf_url IS NOT NULL").fetchall():
            nom = unquote(urlparse(r["u"]).path).rsplit("/", 1)[-1]
            if r["d"] == hashlib.sha256(nom.encode()).hexdigest()[:16]:
                con.execute("UPDATE deliberations SET doc_id_source=? WHERE id=?",
                            (identifiant(r["u"]), r["id"]))
        con.execute("PRAGMA user_version=1")
    # Les premiers passages notaient des chemins absolus : les rendre relatifs
    # a la racine, sinon deplacer le depot rend toute l'archive introuvable.
    for r in con.execute("SELECT id, pdf_chemin_local p FROM deliberations "
                         "WHERE pdf_chemin_local LIKE '/%' OR pdf_chemin_local LIKE '_:%'").fetchall():
        if os.path.isabs(r["p"]) and relatif(r["p"]) != os.path.abspath(r["p"]):
            con.execute("UPDATE deliberations SET pdf_chemin_local=? WHERE id=?",
                        (relatif(r["p"]), r["id"]))
    con.commit()
    return con


def _definition(table):
    """Le CREATE TABLE de SCHEMA, qui fait seul autorite sur la forme cible."""
    debut = SCHEMA.index(f"CREATE TABLE IF NOT EXISTS {table} (")
    fin = SCHEMA.index("\n);", debut) + len("\n)")
    return SCHEMA[debut:fin]


def _reconstruire(con, table, renommages, mappages):
    """Recree `table` telle que SCHEMA la decrit, en y reversant les donnees.

    SQLite ne sait ni renommer une valeur dans un CHECK ni relacher une
    contrainte : il faut une table neuve. La definition cible est lue dans
    SCHEMA plutot que rafistolee a partir de l'ancienne, sinon une base migree
    et une base neuve divergent au premier oubli.
    """
    anciennes = _colonnes(con, table)
    cible = _definition(table).replace(f"IF NOT EXISTS {table} (", f"{table}__neuve (")
    con.execute("PRAGMA foreign_keys=OFF")
    con.executescript(f"{cible};")
    # Colonnes reellement transferables : presentes des deux cotes, et jamais
    # une colonne generee (SQLite refuse qu'on y insere quoi que ce soit).
    generees = _colonnes(con, f"{table}__neuve", generees=True) - _colonnes(con, f"{table}__neuve")
    gardees, projection = [], []
    for neuve in _colonnes(con, f"{table}__neuve"):
        if neuve in generees:
            continue
        ancienne = next((a for a, n in renommages.items() if n == neuve), neuve)
        if ancienne not in anciennes:
            continue
        gardees.append(f'"{neuve}"')
        table_valeurs = mappages.get(neuve)
        if table_valeurs:
            cas = " ".join(f"WHEN '{av}' THEN '{ap}'" for av, ap in table_valeurs.items())
            projection.append(f'CASE "{ancienne}" {cas} ELSE "{ancienne}" END')
        else:
            projection.append(f'"{ancienne}"')
    con.executescript(
        f'INSERT INTO {table}__neuve ({", ".join(gardees)}) '
        f'SELECT {", ".join(projection)} FROM {table};\n'
        f"DROP TABLE {table};\n"
        f"ALTER TABLE {table}__neuve RENAME TO {table};")
    # Les index de la table sont tombes avec elle. db() rejoue SCHEMA en
    # entier juste apres la migration, ce qui les recree : ne pas les remonter
    # ici, une autre table peut encore porter son ancien nom de colonne.
    con.commit()
    con.execute("PRAGMA foreign_keys=ON")
    print(f"migration : vocabulaire normalise sur {table}.", file=sys.stderr)


def _tables_seules(schema):
    """SCHEMA prive de ses index, qui tiennent chacun sur une ligne.

    Un index porte sur une colonne : impossible de le creer avant que la
    migration ait renomme cette colonne sur une base ancienne. Les tables, si :
    toutes en IF NOT EXISTS, elles ne touchent pas a l'existant.
    """
    return "\n".join(l for l in schema.splitlines()
                     if not l.startswith("CREATE INDEX"))


def db(path=DB_DEFAUT):
    """Ouvre la base en ecriture, la cree et la migre au besoin."""
    dossier = os.path.dirname(os.path.abspath(path))
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(_tables_seules(SCHEMA))
    _migrer(con)
    con.executescript(SCHEMA)  # les index, une fois les colonnes a leur nom
    con.commit()
    return con


# Formes qui portent TOUJOURS un accent quelle que soit leur conjugaison ou
# leur genre (la racine elle-meme est accentuee) -- sert a detecter le texte
# qu'un agent a redige sans ses accents (arrive quand un outil de
# recherche/remplacement ou une sortie terminal mal encodee laisse passer du
# texte). Volontairement etroit : un mot comme "adopte" ou "autorise" a une
# forme correcte sans accent (present, infinitif), donc n'y figure pas seul --
# seules ses formes feminines/plurielles non-ambigues y sont, avec les
# racines toujours accentuees. Pas exhaustif : completer au fil des cas trouves.
MOTS_ACCENTUES = [
    "deliberation", "deliberations", "depense", "depenses", "decide",
    "decision", "decisions", "majorite", "unanimite", "evenementiel",
    "operatoire", "definitive", "definitif", "regionale", "regionales",
    "excedent", "excedents", "differentes", "different", "differente",
    "supplementaire", "supplementaires", "exterieur", "exterieure",
    "exterieurs", "financiere", "financieres", "generale", "generales",
    "precedente", "precedentes", "precis", "precise", "precises",
    "chiffree", "chiffrees", "annee", "annees", "regie", "repete",
    "repetee", "eventuel", "eventuelle", "reduit", "adoptee", "autorisee",
    "votee", "approuvee", "attribuee",
]
# Formes ambigues (present correct sans accent, participe fautif avec) --
# seulement fautives suivies de cette preposition precise.
PHRASES_ACCENTUEES = ["adopte a", "conditionne a"]


def mots_sans_accent(con):
    """Renvoie, par table.colonne#id, le texte visible du dashboard qui
    contient un mot ou une phrase de MOTS_ACCENTUES/PHRASES_ACCENTUEES tel
    quel (donc sans accent). Ne regarde que les colonnes affichees telles
    quelles a l'utilisateur : un faux positif ici coute un badge ou une phrase
    illisibles."""
    cibles = [
        ("montants_extraits", "explication",
         "verifie=1 AND retenu=1 AND decision_financiere=1"),
        ("syntheses_reunions", "resume", "1=1"),
        ("syntheses_reunions", "vote_global", "1=1"),
        ("points_ordre_jour", "titre", "1=1"),
        ("points_ordre_jour", "decision", "1=1"),
    ]
    trouves = []
    for table, colonne, condition in cibles:
        for r in con.execute(
                f'SELECT rowid AS rid, "{colonne}" v FROM "{table}" WHERE {condition} '
                f'AND "{colonne}" IS NOT NULL'):
            mot = sans_accent(r["v"])
            if mot:
                trouves.append((table, colonne, r["rid"], mot, r["v"]))
    return trouves


_MOTIFS_ACCENTS = [re.compile(r"\b" + m + r"\b") for m in MOTS_ACCENTUES] + [
    re.compile(r"\b" + p.replace(" ", r"\s+") + r"\b") for p in PHRASES_ACCENTUEES]


def sans_accent(texte):
    """Le premier mot de `texte` qui aurait du porter un accent, sinon None.
    Sert apres coup (--verifier-accents) et avant ecriture (analyse.py)."""
    bas = (texte or "").lower()
    for motif in _MOTIFS_ACCENTS:
        m = motif.search(bas)
        if m:
            return m.group(0)
    return None


def resume(con):
    compte = lambda t: con.execute(f'SELECT COUNT(*) n FROM "{t}"').fetchone()["n"]  # noqa: E731
    lues = con.execute(
        "SELECT COUNT(*) n FROM deliberations d WHERE EXISTS "
        "(SELECT 1 FROM syntheses_reunions s WHERE s.deliberation_id=d.id "
        " AND s.resume IS NOT NULL)").fetchone()["n"]
    suivies = con.execute(
        "SELECT COUNT(*) n FROM suivi WHERE actif=1").fetchone()["n"]
    texte = (f"{compte('portails')} collectivite(s) reperee(s), {suivies} en suivi actif, "
             f"{compte('deliberations')} acte(s) reference(s), {lues} lu(s) et resume(s), "
             f"{compte('montants_extraits')} montant(s) qualifie(s).")
    orphelines = inachevees(con)
    if orphelines:
        texte += (f"\nATTENTION : {len(orphelines)} deliberation(s) ont des montants "
                  "qualifies sans resume (invariant 6) : a reprendre avec "
                  "`python scripts/analyse.py --a-lire <code>`.")
    return texte


def inachevees(con):
    """Deliberations aux montants qualifies mais sans resume : l'analyse
    partielle que le dashboard ne distingue pas d'une analyse complete."""
    return [r[0] for r in con.execute(
        "SELECT DISTINCT m.deliberation_id FROM montants_extraits m WHERE NOT EXISTS "
        "(SELECT 1 FROM syntheses_reunions s WHERE s.deliberation_id=m.deliberation_id "
        " AND s.resume IS NOT NULL)")]


def main():
    sortie_utf8()
    p = argparse.ArgumentParser(description="Cree ou migre la base de deliberations.")
    p.add_argument("--db", default=DB_DEFAUT)
    p.add_argument("--verifier-accents", action="store_true",
                    help="liste le texte affiche au dashboard qui semble ecrit sans accents")
    a = p.parse_args()
    con = db(a.db)
    if a.verifier_accents:
        trouves = mots_sans_accent(con)
        if not trouves:
            print("Aucun texte suspect : pas de mot sans accent detecte.")
        else:
            print(f"{len(trouves)} ligne(s) a relire :")
            for table, colonne, rowid, mot, texte in trouves:
                print(f"- {table}.{colonne} #{rowid} (« {mot} ») : {texte[:120]}")
        return
    print(f"Base prete : {a.db}")
    print(resume(con))
    if not con.execute("SELECT 1 FROM deliberations LIMIT 1").fetchone():
        print("Base vide : demandez a l'agent de suivre une collectivite "
              "(skill france-transparence).")


def _selftest():
    import tempfile
    dossier = tempfile.mkdtemp(prefix="ft_base_")
    chemin = os.path.join(dossier, "t.db")
    try:
        con = db(chemin)
        tables = {r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "deliberations" in tables and "syntheses_reunions" in tables, tables
        # La colonne generee doit trancher commune / EPCI sans qu'on l'ecrive.
        for insee, attendu in (("99001", "commune"), ("900000001", "epci")):
            con.execute(
                "INSERT INTO deliberations (insee, titre, source, doc_id_source, "
                "moissonnee_le) VALUES (?, 'x', 'site', ?, 'now')", (insee, insee))
            vu = con.execute("SELECT type_collectivite t FROM deliberations "
                             "WHERE insee=?", (insee,)).fetchone()["t"]
            assert vu == attendu, (insee, vu, attendu)
        # Le vocabulaire de source est ferme : 'webdelib' n'existe plus.
        try:
            con.execute("INSERT INTO deliberations (insee, titre, source, doc_id_source,"
                        " moissonnee_le) VALUES ('12345','x','webdelib','z','now')")
            raise AssertionError("une source hors vocabulaire a ete acceptee")
        except sqlite3.IntegrityError:
            pass
        # Rejouer la migration sur une base deja a jour ne doit rien casser.
        con.commit()
        con.close()
        con = db(chemin)
        assert con.execute("SELECT COUNT(*) n FROM deliberations").fetchone()["n"] == 2
        # L'ancienne identite (empreinte du nom seul) devient celle du chemin ;
        # un identifiant publie par un portail ne bouge pas.
        import hashlib
        ancien = hashlib.sha256(b"pv du 3.pdf").hexdigest()[:16]
        url = "https://x.fr/2023/pv%20du%203.pdf?Signature=a"
        con.execute("INSERT INTO deliberations (insee,titre,source,doc_id_source,pdf_url,"
                    "moissonnee_le) VALUES ('99001','pv','site',?,?,'now')", (ancien, url))
        con.execute("INSERT INTO deliberations (insee,titre,source,doc_id_source,pdf_url,"
                    "moissonnee_le) VALUES ('99001','acte','portail','4412',?,'now')", (url,))
        con.execute("PRAGMA user_version=0")
        con.commit()
        con.close()
        con = db(chemin)
        ids = {r[0] for r in con.execute("SELECT doc_id_source FROM deliberations")}
        assert identifiant(url) in ids and "4412" in ids and ancien not in ids, ids
        assert identifiant(url) == identifiant("http://www.x.fr/2023/pv%20du%203.pdf")
        assert identifiant(url) != identifiant("https://x.fr/2026/pv%20du%203.pdf")
        con.execute("DELETE FROM deliberations WHERE pdf_url IS NOT NULL")
        con.commit()
        con.close()

        # Une base a l'ancien vocabulaire doit etre reecrite, donnees comprises.
        vieux = os.path.join(dossier, "v.db")
        v = sqlite3.connect(vieux)
        v.executescript("""
            CREATE TABLE portails (insee TEXT PRIMARY KEY, nom TEXT NOT NULL,
              type TEXT NOT NULL CHECK (type IN ('webdelib','site_communal')),
              url TEXT, verifie_le TEXT NOT NULL, notes TEXT);
            INSERT INTO portails (insee,nom,type,url,verifie_le)
              VALUES ('99001','Bourg','site_communal','https://x.fr','2026-01-01');
            CREATE TABLE seances (id INTEGER PRIMARY KEY, insee TEXT, date_seance TEXT,
              source TEXT CHECK (source IN ('webdelib','site_communal')), moissonnee_le TEXT);
            INSERT INTO seances VALUES (7,'99001','2026-14-00','site_communal','x');
            INSERT INTO seances VALUES (8,'99001','2026-02-03','webdelib','x');
            CREATE TABLE deliberations (id INTEGER PRIMARY KEY, insee TEXT NOT NULL,
              titre TEXT NOT NULL,
              source TEXT NOT NULL CHECK (source IN ('webdelib','site_communal')),
              doc_id_source TEXT NOT NULL, moissonnee_le TEXT NOT NULL,
              statut_depouillement TEXT NOT NULL DEFAULT 'brut');
            INSERT INTO deliberations (insee,titre,source,doc_id_source,moissonnee_le)
              VALUES ('99001','Acte','webdelib','a','now');
        """)
        v.commit()
        v.close()
        con = db(vieux)
        vu = con.execute("SELECT source FROM deliberations").fetchone()["source"]
        assert vu == "portail", vu
        # Une date impossible (numero d'acte mal lu) part ; la vraie reste, et
        # le CHECK refuse desormais d'en reecrire une.
        vu = [tuple(r) for r in con.execute("SELECT date_seance, source FROM seances")]
        assert vu == [("2026-02-03", "portail")], vu
        try:
            con.execute("INSERT INTO seances (insee,date_seance,source,moissonnee_le)"
                        " VALUES ('99001','2026-02-30','site','x')")
            raise AssertionError("une date impossible a ete acceptee")
        except sqlite3.IntegrityError:
            pass
        con.execute("DELETE FROM seances")
        # `portails.type` porte le meme vocabulaire et doit suivre, sinon rien
        # ne casse a la lecture et tout casse au premier enregistrement.
        vu = con.execute("SELECT type FROM portails").fetchone()["type"]
        assert vu == "site", vu
        con.execute("INSERT OR REPLACE INTO portails (insee,nom,type,url,verifie_le)"
                    " VALUES ('99002','Autre','portail','https://y.fr','2026-01-01')")
        # Une seance datee du jour de sa collecte est une date inventee par
        # l'ancien collecteur : elle doit disparaitre, sans emporter l'acte.
        con.execute("INSERT INTO seances (id,insee,date_seance,source,moissonnee_le)"
                    " VALUES (1,'99001','2026-03-04','site','2026-03-04T10:00:00Z')")
        con.execute("INSERT INTO seances (id,insee,date_seance,source,moissonnee_le)"
                    " VALUES (2,'99001','2026-05-09','site','2026-06-01T10:00:00Z')")
        con.execute("UPDATE deliberations SET seance_id=1")
        con.commit()
        con.close()
        con = db(vieux)
        restantes = [r["date_seance"] for r in con.execute("SELECT date_seance FROM seances")]
        assert restantes == ["2026-05-09"], restantes
        assert con.execute("SELECT seance_id FROM deliberations").fetchone()[0] is None
        assert con.execute("SELECT COUNT(*) n FROM deliberations").fetchone()["n"] == 1
        con.close()

        # mots_sans_accent : ne signale que le texte reellement affiche
        # (montant retenu), pas un candidat ecarte ni une forme ambigue.
        con = db(chemin)
        con.execute("INSERT INTO seances (id,insee,date_seance,source,moissonnee_le)"
                    " VALUES (10,'99001','2026-01-01','portail','now')")
        con.execute("INSERT INTO deliberations (id,insee,titre,source,doc_id_source,"
                    "moissonnee_le,seance_id) VALUES (10,'99001','Acte accents','portail',"
                    "'a10','now',10)")
        con.execute("INSERT INTO montants_extraits (deliberation_id,valeur,phrase,nature,"
                    "decision_financiere,explication,verifie,retenu) VALUES (10,100,'p',"
                    "'Depense',1,'IMPUTER la depense sur ce point','1','1')")
        con.execute("INSERT INTO montants_extraits (deliberation_id,valeur,phrase,nature,"
                    "decision_financiere,explication,verifie,retenu) VALUES (10,200,'p',"
                    "'Depense ecartee',1,'un point qui contient depense mais ecarte','1','0')")
        assert any(t == "explication" and rid for (_, t, rid, *_ ) in mots_sans_accent(con)), \
            "un montant reellement affiche avec explication non accentuee doit etre signale"
        assert len(mots_sans_accent(con)) == 1, "le montant ecarte (retenu=0) ne doit pas compter"
        con.execute("UPDATE montants_extraits SET explication='IMPUTER la dépense sur ce point'"
                    " WHERE deliberation_id=10 AND retenu='1'")
        assert mots_sans_accent(con) == [], "une explication correctement accentuee ne doit rien signaler"
        con.execute("INSERT INTO montants_extraits (deliberation_id,valeur,phrase,nature,"
                    "decision_financiere,explication,verifie,retenu) VALUES (10,300,'p',"
                    "'Depense',1,'Autoriser le maire a signer ce point, il adopte ce choix','1','1')")
        assert mots_sans_accent(con) == [], (
            "'adopte' et 'autoriser' seuls ont une forme correcte sans accent "
            "(present, infinitif) : ne pas les signaler a tort")
        con.close()
        # Un chemin absolu sous la racine devient relatif ; hors racine, il reste.
        con = db(chemin)
        dedans = os.path.join(PDF_DIR, "99001", "x.pdf")
        con.execute("UPDATE deliberations SET pdf_chemin_local=? WHERE insee='99001'", (dedans,))
        con.execute("UPDATE deliberations SET pdf_chemin_local=? WHERE insee='900000001'",
                    (os.path.join(dossier, "y.pdf"),))
        con.execute("INSERT INTO montants_extraits (deliberation_id,valeur,phrase) "
                    "SELECT id, 1, 'p' FROM deliberations WHERE insee='99001'")
        con.commit()
        con.close()
        con = db(chemin)
        chemins = sorted(r[0] for r in con.execute(
            "SELECT pdf_chemin_local FROM deliberations WHERE pdf_chemin_local IS NOT NULL"))
        assert "data/deliberations/99001/x.pdf" in chemins, chemins
        assert os.path.join(dossier, "y.pdf") in chemins, chemins
        # Des montants sans resume se voient dans le resume de la base.
        assert len(inachevees(con)) == 1 and "ATTENTION" in resume(con)
        # Invariants 6 et 9 rattrapes a l'ouverture : une estimation « decidee »
        # est masquee, un `lu` sans resume rendu a la lecture.
        con.execute("INSERT INTO montants_extraits (deliberation_id,valeur,phrase,nature,"
                    "decision_financiere,verifie) VALUES (1,5,'p','Estimation',1,1)")
        con.execute("UPDATE deliberations SET statut_lecture='lu'")
        con.commit()
        con.close()
        con = db(chemin)
        assert con.execute("SELECT MAX(decision_financiere) FROM montants_extraits").fetchone()[0] == 0
        assert {r[0] for r in con.execute("SELECT statut_lecture FROM deliberations")} == {"brut"}
        con.close()
    finally:
        import shutil
        shutil.rmtree(dossier, ignore_errors=True)
    # Les deux copies du skill sont des miroirs : une divergence fait lire a
    # Codex d'autres regles qu'a Claude Code.
    import filecmp
    a, b = (os.path.join(RACINE, d, "skills", "france-transparence") for d in (".claude", ".agents"))
    ecart = filecmp.dircmp(a, b)
    assert not (ecart.left_only or ecart.right_only or ecart.diff_files),         f"skill france-transparence : .claude et .agents divergent ({ecart.diff_files or ecart.left_only or ecart.right_only})"
    print("selftest ok")


if __name__ == "__main__":
    sortie_utf8()
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
