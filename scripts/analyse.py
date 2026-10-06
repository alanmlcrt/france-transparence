#!/usr/bin/env python3
"""La plume de l'agent : ce qu'il a lu dans un PDF entre en base d'un bloc.

  analyse.py --a-lire <code>                     ce qui reste a lire, inachevees d'abord
  analyse.py --a-lire <code> --du 2026-03-01 --au 2026-03-31
  analyse.py --a-lire <code> --acte 26/172       un acte (numero ou id), meme deja lu
  analyse.py --ecrire scratch_analyse.json       ecrit une lecture (ou une liste)
  analyse.py --selftest                          controle, sans reseau

Ce script ne lit aucun PDF et ne juge de rien : tout ce qu'il ecrit, l'agent l'a
decide. Il existe pour trois raisons que des `python -c` en ligne ne tenaient
pas :

- **Une lecture s'ecrit en une transaction, resume compris** (invariant 6). Un
  statut `lu` sans `resume` est refuse : la deliberation a moitie faite, celle
  que le dashboard ne distingue pas d'une analyse complete, ne peut plus
  entrer en base.
- **Le texte passe par un fichier UTF-8**, pas par la ligne de commande : sous
  Windows, une chaine accentuee dans `python -c` traverse la page de code de la
  console et arrive mutilee (« B�thune ») -- d'ou des agents qui finissaient
  par ecrire sans accents.
- **Les vocabulaires fermes sont verifies avant d'ecrire**, pas decouverts sur
  une fiche publiee.

Reecrire une deliberation remplace sa lecture precedente : relancer le meme
fichier corrige, il ne duplique rien.

Format (un objet, ou une liste d'objets) :

  {"id": 12, "statut": "lu",
   "resume": "Deux a trois paragraphes...", "vote_global": "Adoptée à l'unanimité",
   "nombre_presents": 45,
   "points": [{"titre": "...", "decision": "...", "resultat_vote": "...", "est_budget": false}],
   "montants": [{"valeur": 603006.10, "suffixe": "HT", "phrase": "citation exacte",
                 "point": "26/172 Avenant", "nature": "Dépense",
                 "decision_financiere": 1, "verifie": 1, "retenu": 1,
                 "explication": "pourquoi ce role, depuis le PDF seul"}],
   "pieces": ["avenant", "convention"], "alertes": ["intitule du point sensible"],
   "themes": ["Commande publique"]}

`statut: "echec"` n'accepte que l'id : un PDF qui resiste n'a pas de synthese.
"""
import argparse
import json
import os
import re
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import db, sans_accent, sortie_utf8, NATURES_NON_DECIDEES, PIECES_CANONIQUES, RACINE  # noqa: E402

# Les trois dernieres sont des engagements votes qui ne sont pas des depenses :
# une garantie d'emprunt ne coute que si l'emprunteur defaille, une autorisation
# de programme ouvre une enveloppe pluriannuelle, un plafond borne une depense
# encore a chiffrer. Classees « Montant de reference », elles disparaissaient
# de la fiche alors qu'elles comptent parmi les decisions les plus lourdes d'un
# conseil (constate a Montceau-les-Mines : 697 155,50 € de garantie).
NATURES = ("Dépense", "Recette", "Recette abandonnée", "Financement par un tiers",
           "Estimation de la part d'un tiers", "Estimation", "Montant historique",
           "Montant de référence", "Montant mentionné",
           "Garantie d'emprunt", "Autorisation de programme", "Plafond voté")
PIECES = {"annexe", "arrêté", "avenant", "bail", "bilan", "CCAP", "CCTP", "charte",
          "consultation", "contrat", "convention", "délibération", "devis",
          "diagnostic", "étude", "facture", "marché", "notice", "offre",
          "plan de financement", "procès-verbal", "protocole", "rapport"}
THEMES = {"Budget et fiscalité", "Subventions", "Commande publique",
          "Urbanisme et foncier", "Mobilités et voirie", "Bâtiments et patrimoine",
          "Transition écologique", "Ressources humaines", "Éducation et jeunesse",
          "Culture", "Sports", "Solidarités et santé", "Sécurité", "Numérique",
          "Logement", "Eau et assainissement"}
TABLES_LECTURE = ("montants_extraits", "pieces_citees", "alertes_donnees_personnelles",
                  "points_ordre_jour", "syntheses_reunions")


def valider(a):
    """Liste des refus pour une lecture ; vide si elle peut s'ecrire."""
    refus = []
    if not isinstance(a.get("id"), int):
        return ["`id` entier manquant"]
    statut = a.get("statut", "lu")
    if statut == "echec":
        extra = set(a) - {"id", "statut"}
        return [f"echec : rien d'autre que l'id ({', '.join(sorted(extra))})"] if extra else []
    if statut != "lu":
        return [f"statut « {statut} » : lu ou echec"]
    if not (a.get("resume") or "").strip():
        refus.append("`resume` vide : une lecture sans resume est une analyse "
                     "partielle (invariant 6)")
    for i, m in enumerate(a.get("montants", [])):
        ou = f"montants[{i}]"
        if not isinstance(m.get("valeur"), (int, float)) or not (m.get("phrase") or "").strip():
            refus.append(f"{ou} : `valeur` numerique et `phrase` source obligatoires")
        nature = m.get("nature", "Montant mentionné")
        if nature not in NATURES:
            refus.append(f"{ou} : nature « {nature} » hors vocabulaire")
        for cle in ("decision_financiere", "verifie", "retenu"):
            if m.get(cle, 0) not in (0, 1):
                refus.append(f"{ou} : `{cle}` vaut 0 ou 1")
        if m.get("decision_financiere") == 1 and (nature in NATURES_NON_DECIDEES
                                                   or m.get("verifie") != 1):
            refus.append(f"{ou} : decision_financiere=1 exige une nature decidee et verifie=1")
        if m.get("verifie") == 1 and not (m.get("explication") or "").strip():
            refus.append(f"{ou} : un montant verifie porte son `explication`")
    for p in a.get("pieces", []):
        if PIECES_CANONIQUES.get(p.lower(), p) not in PIECES:
            refus.append(f"piece « {p} » hors vocabulaire")
    for t in a.get("themes", []):
        if t not in THEMES:
            refus.append(f"theme « {t} » hors vocabulaire")
    for i, p in enumerate(a.get("points", [])):
        if not (p.get("titre") or "").strip():
            refus.append(f"points[{i}] : `titre` obligatoire")
    return refus


def accents(a):
    """Le texte redige par l'agent, pas les citations du PDF, doit etre accentue."""
    textes = [("resume", a.get("resume")), ("vote_global", a.get("vote_global"))]
    textes += [(f"points[{i}]", f"{p.get('titre', '')} {p.get('decision') or ''}")
               for i, p in enumerate(a.get("points", []))]
    textes += [(f"montants[{i}].explication", m.get("explication"))
               for i, m in enumerate(a.get("montants", []))]
    return [(ou, mot) for ou, t in textes if (mot := sans_accent(t))]


def ecrire(con, a):
    """Remplace la lecture de la deliberation `a['id']`, en une transaction."""
    refus = valider(a)
    if not con.execute("SELECT 1 FROM deliberations WHERE id=?", (a.get("id"),)).fetchone():
        refus.append(f"aucune deliberation d'id {a.get('id')}")
    if refus:
        raise ValueError(f"#{a.get('id')} refuse, rien n'a ete ecrit :\n  - " + "\n  - ".join(refus))
    n = a["id"]
    with con:
        for table in TABLES_LECTURE:
            con.execute(f"DELETE FROM {table} WHERE deliberation_id=?", (n,))
        con.execute("DELETE FROM tags_automatiques WHERE deliberation_id=? "
                    "AND source='contenu'", (n,))
        statut = a.get("statut", "lu")
        con.execute("UPDATE deliberations SET statut_lecture=? WHERE id=?", (statut, n))
        if statut == "echec":
            return f"#{n} : lecture en echec, aucune synthese."
        for m in a.get("montants", []):
            con.execute(
                "INSERT INTO montants_extraits (deliberation_id,valeur,suffixe,phrase,"
                "point_ordre_jour,nature,decision_financiere,verifie,retenu,explication)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (n, m["valeur"], m.get("suffixe"), m["phrase"], m.get("point"),
                 m.get("nature", "Montant mentionné"), m.get("decision_financiere", 0),
                 m.get("verifie", 0), m.get("retenu", 0), m.get("explication")))
        for p in dict.fromkeys(PIECES_CANONIQUES.get(p.lower(), p) for p in a.get("pieces", [])):
            con.execute("INSERT INTO pieces_citees (deliberation_id,nature) VALUES (?,?)", (n, p))
        for point in a.get("alertes", []):
            con.execute("INSERT INTO alertes_donnees_personnelles (deliberation_id,"
                        "point_ordre_jour) VALUES (?,?)", (n, point))
        for t in dict.fromkeys(a.get("themes", [])):
            con.execute("INSERT OR IGNORE INTO tags_automatiques (deliberation_id,libelle,"
                        "categorie,source) VALUES (?,?,'theme','contenu')", (n, t))
        points = a.get("points", [])
        for ordre, p in enumerate(points, 1):
            con.execute("INSERT INTO points_ordre_jour (deliberation_id,ordre,titre,decision,"
                        "resultat_vote,est_budget) VALUES (?,?,?,?,?,?)",
                        (n, ordre, p["titre"], p.get("decision"), p.get("resultat_vote"),
                         1 if p.get("est_budget") else 0))
        con.execute("INSERT INTO syntheses_reunions (deliberation_id,nombre_presents,"
                    "vote_global,nombre_points,nombre_decisions,resume) VALUES (?,?,?,?,?,?)",
                    (n, a.get("nombre_presents"), a.get("vote_global"), len(points),
                     sum(1 for p in points if p.get("decision")), a["resume"].strip()))
    decides = sum(1 for m in a.get("montants", []) if m.get("decision_financiere") == 1
                  and m.get("retenu") == 1)
    return (f"#{n} ecrit : {len(a.get('montants', []))} montant(s) dont {decides} "
            f"affiche(s), {len(points)} point(s), {len(a.get('pieces', []))} piece(s), "
            f"resume {len(a['resume'])} car.")


PAGES = re.compile(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)|/Count\s+(\d+)[^>]*?/Type\s*/Pages\b")
FLUX = re.compile(rb"stream\r?\n(.*?)endstream", re.S)


def pages(chemin):
    """Nombre de pages d'un PDF, sans dependance ; None si illisible.

    Sert a decouper la lecture a l'avance : l'outil Read lit un long PDF par
    tranches, et un recueil de 400 pages ne se decouvre pas a la page 20. Le
    compte est dans l'arbre /Pages, en clair ou dans un flux compresse
    (PDF 1.5+) : le plus grand est celui de la racine."""
    try:
        with open(os.path.join(RACINE, chemin), "rb") as f:
            octets = f.read()
    except OSError:
        return None
    comptes = [int(a or b) for a, b in PAGES.findall(octets)]
    if not comptes:
        for flux in FLUX.findall(octets):
            try:
                comptes += [int(a or b) for a, b in PAGES.findall(zlib.decompress(flux))]
            except zlib.error:
                continue
    return max(comptes) if comptes else None


def a_lire(con, code, du=None, au=None, acte=None):
    """Lignes (id, date, numero, titre, pdf) a lire pour une collectivite.

    Sans `acte` : les deliberations archivees sans resume, celles qui ont deja
    des montants (analyse inachevee) en tete, puis les plus recentes : c'est
    ce qu'on veut lire d'abord. Avec `acte` : cet acte seul, meme deja lu --
    une relecture demandee."""
    sql = ("SELECT d.id, COALESCE(s.date_seance, substr(d.moissonnee_le,1,10)) jour, "
           "d.numero, d.titre, d.pdf_chemin_local pdf, "
           "EXISTS(SELECT 1 FROM montants_extraits m WHERE m.deliberation_id=d.id) entame "
           "FROM deliberations d LEFT JOIN seances s ON s.id=d.seance_id WHERE d.insee=? ")
    params = [code]
    if acte:
        sql += "AND (d.numero=? OR CAST(d.id AS TEXT)=?) "
        params += [acte, acte]
    else:
        sql += ("AND d.pdf_chemin_local IS NOT NULL AND d.statut_lecture<>'echec' "
                "AND NOT EXISTS (SELECT 1 FROM syntheses_reunions y WHERE "
                "y.deliberation_id=d.id AND y.resume IS NOT NULL) ")
    if du:
        sql += "AND jour >= ? "
        params.append(du)
    if au:
        sql += "AND jour <= ? "
        params.append(au)
    return con.execute(sql + "ORDER BY entame DESC, jour DESC, d.id DESC", params).fetchall()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db")
    p.add_argument("--a-lire", dest="a_lire", metavar="CODE")
    p.add_argument("--du")
    p.add_argument("--au")
    p.add_argument("--acte", help="numero ou id d'un acte precis")
    p.add_argument("--ecrire", metavar="FICHIER.json")
    a = p.parse_args()
    con = db(a.db) if a.db else db()
    if a.a_lire:
        lignes = a_lire(con, a.a_lire, a.du, a.au, a.acte)
        etats = dict(con.execute("SELECT statut_lecture, COUNT(*) FROM deliberations "
                                 "WHERE insee=? GROUP BY 1", (a.a_lire,)).fetchall())
        print(f"{a.a_lire} : {sum(etats.values())} acte(s) {etats} -- {len(lignes)} a lire")
        for r in lignes:
            marque = " [INACHEVEE]" if r["entame"] else ""
            n = pages(r["pdf"]) if r["pdf"] else None
            print(f"{r['id']}\t{r['jour']}\t{r['numero'] or '-'}\t{r['titre'][:70]}"
                  f"\t{r['pdf'] or 'pas de PDF'}\t{n or '?'} p.{marque}")
        return
    if not a.ecrire:
        p.error("--a-lire ou --ecrire")
    with open(a.ecrire, encoding="utf-8") as f:
        lectures = json.load(f)
    code = 0
    for lecture in lectures if isinstance(lectures, list) else [lectures]:
        try:
            print(ecrire(con, lecture))
        except ValueError as refus:
            print(refus, file=sys.stderr)
            code = 1
            continue
        for ou, mot in accents(lecture):
            print(f"  ACCENT : {ou} contient « {mot} » -- corriger le fichier et relancer.",
                  file=sys.stderr)
    sys.exit(code)


def _selftest():
    import tempfile
    import shutil
    dossier = tempfile.mkdtemp(prefix="ft_analyse_")
    try:
        con = db(os.path.join(dossier, "t.db"))
        con.execute("INSERT INTO deliberations (id,insee,titre,source,doc_id_source,"
                    "pdf_chemin_local,moissonnee_le) VALUES (7,'99001','Budget','site','a',"
                    "'data/x.pdf','2026-03-01T00:00:00Z')")
        con.commit()
        assert [r["id"] for r in a_lire(con, "99001")] == [7]
        # Les plus recentes d'abord.
        con.execute("INSERT INTO deliberations (id,insee,titre,source,doc_id_source,"
                    "pdf_chemin_local,moissonnee_le) VALUES (8,'99001','PV','site','b',"
                    "'data/y.pdf','2026-09-01T00:00:00Z')")
        assert [r["id"] for r in a_lire(con, "99001")] == [8, 7]
        con.execute("DELETE FROM deliberations WHERE id=8")
        con.commit()
        lecture = {"id": 7, "resume": "Le conseil a voté le budget.",
                   "vote_global": "Adoptée à l'unanimité",
                   "points": [{"titre": "Budget primitif", "decision": "Adopté"}],
                   "montants": [{"valeur": 1000, "phrase": "p", "nature": "Dépense",
                                 "decision_financiere": 1, "verifie": 1, "retenu": 1,
                                 "explication": "Vote explicite."}],
                   "pieces": ["annexes", "annexe"], "themes": ["Budget et fiscalité"]}
        assert ecrire(con, lecture).startswith("#7 ecrit")
        # Rejouer remplace, ne duplique pas ; les variantes de piece fusionnent.
        ecrire(con, lecture)
        assert con.execute("SELECT COUNT(*) FROM montants_extraits").fetchone()[0] == 1
        assert [r[0] for r in con.execute("SELECT nature FROM pieces_citees")] == ["annexe"]
        assert con.execute("SELECT statut_lecture FROM deliberations").fetchone()[0] == "lu"
        assert a_lire(con, "99001") == [] and len(a_lire(con, "99001", acte="7")) == 1
        # Refus : lu sans resume, vocabulaire hors liste, estimation « decidee ».
        for mauvais in ({"id": 7, "resume": " "},
                        {"id": 7, "resume": "r", "pieces": ["pv"]},
                        {"id": 7, "resume": "r", "montants": [{"valeur": 1, "phrase": "p",
                         "nature": "Estimation", "decision_financiere": 1, "verifie": 1,
                         "explication": "e"}]},
                        {"id": 8, "resume": "r"}):
            try:
                ecrire(con, mauvais)
                raise AssertionError(f"accepte a tort : {mauvais}")
            except ValueError:
                pass
        # Un refus n'a rien efface de la lecture precedente.
        assert con.execute("SELECT COUNT(*) FROM syntheses_reunions").fetchone()[0] == 1
        assert accents({"resume": "La deliberation est adoptée."}) == [("resume", "deliberation")]
        assert accents(lecture) == []
        # Le compte de pages, en clair ou dans un flux compresse.
        plat = os.path.join(dossier, "p.pdf")
        with open(plat, "wb") as f:
            f.write(b"<< /Type /Pages /Kids [3 0 R] /Count 12 >>")
        assert pages(plat) == 12
        with open(plat, "wb") as f:
            f.write(b"stream\n" + zlib.compress(b"<</Count 7/Type/Pages>>") + b"endstream")
        assert pages(plat) == 7 and pages(os.path.join(dossier, "absent.pdf")) is None
        # Un echec efface toute synthese partielle.
        ecrire(con, {"id": 7, "statut": "echec"})
        assert con.execute("SELECT COUNT(*) FROM syntheses_reunions").fetchone()[0] == 0
        con.close()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    print("selftest ok")


if __name__ == "__main__":
    sortie_utf8()
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
