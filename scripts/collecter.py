#!/usr/bin/env python3
"""Rejoue la collecte d'une collectivite deja reperee. Ne cherche rien.

  collecter.py --insee 13083            relit la page connue, reference, telecharge
  collecter.py --insee 13083 --a-blanc  montre ce qui serait ecrit, sans rien ecrire
  collecter.py --modele 13083           ecrit data/collecteurs/13083.py a adapter
  collecter.py --memoire 13083          imprime ce qu'on sait de cette ville
  collecter.py --selftest               controle, sans reseau

Ce script ne remplace pas l'agent, il le dispense de se repeter. Trouver ou une
collectivite publie ses actes demande de regarder une page et de juger : sur
Rognonas, huit rubriques du menu contenaient les mots « conseil », « municipal »
ou « actes », une seule listait des deliberations. Ce jugement se fait une fois,
avec un navigateur, et se depose dans `data/portails.yaml` sous forme de
recette. Relire ensuite la meme page est mecanique -- et doit l'etre, parce que
le mode `surveiller` repasse chaque semaine pour ne trouver, le plus souvent,
aucun acte nouveau.

Relire, et pas rejouer des URL memorisees : beaucoup de sites servent leurs PDF
depuis un CDN par des liens signes qui expirent (29 jours sur Rognonas). Les
adresses doivent etre reprises sur la page a chaque passage.

Deux facons de decrire une collectivite, cherchees dans cet ordre :

1. **Un collecteur dedie**, `data/collecteurs/<insee>.py`. Un module Python qui
   expose `actes(ctx)` et rend la liste des actes de la page. Il peut tout
   faire : pagination, formulaire de recherche, appel d'API, rendu JavaScript.
   C'est la voie normale des que le site sort de l'ordinaire.
2. **Une recette** dans `data/portails.yaml`, quand la page se lit bêtement :

       recette:
         rendu: http          # ou « navigateur » si la page est rendue en JS
         dans: "#contenu"     # facultatif : restreint a un conteneur
         attendu: 17          # actes trouves au dernier passage verifie

A cote du collecteur vit `data/memoire/<insee>.md` : ce qu'on a appris en
LISANT cette collectivite, et que le collecteur n'a pas a porter -- les pistes
essayees et ecartees, la structure de ses actes, ses pieges de qualification,
ses passages successifs. Ce script ne juge jamais de son contenu ; il la
signale (`--memoire <insee>` l'imprime), et journalise chaque passage sous
`## Journal automatique` -- un fait (date, comptes), pas un jugement. Si
aucune autre section n'existe malgre ce journal, il le crie sur stderr : c'est
la seule partie de cette exigence qu'un script peut faire respecter sans
compter sur personne pour lire une instruction.

`data/collecteurs/` et `data/memoire/` vivent dans `data/`, donc hors du
depot : ils decrivent les collectivites que VOUS suivez, ils ne concernent
personne d'autre. Corollaire pour les collecteurs : ce sont vos fichiers,
executes tels quels par ce script. N'y mettez que du code que vous avez lu.

Sans collecteur ni recette, ce script refuse : une collectivite non verifiee se
traite a l'agent, pas ici.
"""
import argparse
import datetime as dt
import html as html_mod
import hashlib
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from base import db, identifiant, relatif, sortie_utf8, DATA, PDF_DIR, RACINE, REGISTRE, SOURCES  # noqa: E402

COLLECTEURS = os.path.join(DATA, "collecteurs")
MEMOIRE = os.path.join(DATA, "memoire")
ATTENDU_INCONNU = None

UA = "france-transparence (lecture seule)"
PAUSE = 0.5  # secondes entre deux requetes vers un meme serveur municipal
TIMEOUT = 90

# Une date de seance, telle qu'elle apparait dans un nom de fichier ou un
# intitule de lien : 27072026, 27 07 2026, 27-07-2026. Le jour peut ne pas
# porter son zero (« PV Du 8042026 »). Jamais au milieu d'un nombre :
# « 124_2025 » (un numero d'acte) se lisait jour 1, mois 24.
# Ni suivie d'un chiffre : « 29062026101022 » est un horodatage de mise en
# ligne, pas une date de seance.
DATE = re.compile(r"(?<!\d)(\d{1,2})[ +/._-]?(\d{2})[ +/._-]?(20\d{2})(?!\d)")
# « PV du 08.04.26 » : annee sur deux chiffres, separateurs exiges -- sans
# eux, n'importe quel numero de six chiffres passerait pour une date.
# Ni suivie d'un autre groupe : « 26.06.29.01 » est une numerotation (annee,
# mois, jour, rang a Juvignac), que la lecture jour.mois.annee datait de 2029.
DATE_COURTE = re.compile(r"(?<!\d)(?<!\d[./_-])(\d{1,2})([./_-])(\d{2})\2(\d{2})(?![./_-]?\d)")
DATE_ISO = re.compile(r"(?<!\d)(20\d{2})([-_.]?)(\d{2})\2(\d{2})(?!\d)")
LIEN = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
# Un PDF peut etre declare hors d'un lien : visionneuse (`source=` de dFlip),
# `<embed src>`, `<object data>`, `<iframe src>`, `data-src`. Sans intitule :
# le titre vient alors du nom du fichier.
PDF_EMBARQUE = re.compile(r'\s(?:src|data|source|data-[\w-]+)=["\']([^"\']+?\.pdf(?:[?#][^"\']*)?)["\']', re.I)
BALISE = re.compile(r"<[^>]+>")
LIBELLES_MUETS = {"", "consulter", "télécharger", "telecharger", "voir", "lire", "ici",
                  "pdf", "ouvrir", "lien", "document", "en savoir plus", "cliquez ici",
                  "feuilleter", "visualiser", "afficher"}
# Ce que les CMS collent a un intitule : « (pdf - 30 Ko) », « En savoir plus ».
BRUIT_LIBELLE = re.compile(r"\(\s*(?:pdf\b|[\d.,]+\s*[kmg]o?\b)[^)]*\)|\ben savoir plus\b"
                           r"|\btélécharger\b|\b(?:la )?version pdf\b", re.I)


def _date_valide(annee, mois, jour):
    """AAAA-MM-JJ si la date existe, sinon None : une date impossible est un
    numero mal lu, et une date inventee vaut moins que pas de date. Une seance
    a plus de six mois d'ici n'existe pas non plus : on convoque un conseil
    quelques semaines avant, pas des annees."""
    try:
        d = dt.date(int(annee), int(mois), int(jour))
    except ValueError:
        return None
    return d.isoformat() if d <= dt.date.today() + dt.timedelta(days=183) else None


def date_num(texte):
    """La premiere date chiffree valide du texte, sinon None. Publique."""
    texte = texte or ""
    for m in DATE.finditer(texte):
        d = _date_valide(m.group(3), m.group(2), m.group(1))
        if d:
            return d
    for m in DATE_COURTE.finditer(texte):
        d = _date_valide("20" + m.group(4), m.group(3), m.group(1))
        if d:
            return d
    # Annee en tete : « 2026-03-15 », « 20260303_PV », et l'identifiant d'un
    # acte transmis au controle de legalite (@CTES), « 038-213802960-20240213-… ».
    for m in DATE_ISO.finditer(texte):
        d = _date_valide(m.group(1), m.group(3), m.group(4))
        if d:
            return d
    return None


def maintenant():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ registre
def recettes(chemin=REGISTRE):
    """Lit portails.yaml sans dependance YAML.

    Le fichier est ecrit par un agent et relu ici : deux niveaux
    d'indentation, des paires `cle: valeur`, et les blocs `cle: >` ou `cle: |`
    pour les textes longs -- `notes` en est toujours un. Rien de plus. Un vrai
    parseur YAML serait une dependance ajoutee pour un format qu'on maitrise
    de bout en bout. Si ce fichier devait un jour porter des listes ou des
    ancres, il vaudrait mieux passer a PyYAML que gonfler cette fonction.
    """
    if not os.path.exists(chemin):
        return {}
    out, courante, sous = {}, None, None
    bloc = None   # (cle, creux d'ouverture, [lignes], plie ?) quand on lit un `>` ou `|`
    lignes = open(chemin, encoding="utf-8").read().splitlines() + [""]
    for brute in lignes:
        ligne = brute.rstrip()
        creux = len(ligne) - len(ligne.lstrip()) if ligne.strip() else None

        # Un bloc continue tant que l'indentation reste superieure a la sienne.
        # C'est ce qui porte `notes`, et sans ca la valeur lue serait « > ».
        if bloc is not None:
            cle, ouverture, morceaux, plie = bloc
            if ligne.strip() and creux > ouverture:
                morceaux.append(ligne.strip())
                continue
            texte = (" " if plie else "\n").join(morceaux).strip()
            out[courante][cle] = texte
            bloc = None
            # la ligne courante n'appartient pas au bloc : elle se traite plus bas

        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        nu = ligne.strip()
        if creux == 0:
            courante = sous = None
            continue
        if creux == 2 and nu.endswith(":"):
            courante = nu[:-1].strip().strip('"\'')
            out[courante] = {}
            sous = None
            continue
        if courante is None or ":" not in nu:
            continue
        cle, _, valeur = nu.partition(":")
        cle, valeur = cle.strip(), valeur.strip()
        if creux == 4 and valeur in (">", "|", ">-", "|-"):
            bloc = (cle, creux, [], valeur.startswith(">"))
            continue
        valeur = valeur.strip('"\'')
        if creux == 4:
            sous = None
            if not valeur:
                sous = cle
                out[courante][cle] = {}
            else:
                out[courante][cle] = valeur
        elif creux >= 6 and sous:
            out[courante][sous][cle] = valeur
    return out


# ------------------------------------------------------------- lecture page
def _uri(url):
    """`/pyrénées-audoises/Liste des actes.pdf` tel qu'un site l'ecrit, en
    adresse que urllib accepte : il refuse tout caractere hors ASCII, et
    l'echec arrivait avant meme la requete. Ce qui est deja encode reste tel."""
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")


_TLS = {}   # hote -> contexte complete de son certificat intermediaire


def _contexte_complete(hote):
    """Un contexte TLS qui connait l'intermediaire que le serveur oublie d'envoyer.

    Beaucoup de petits sites servent une chaine incomplete : un navigateur va
    chercher l'intermediaire a l'adresse que porte le certificat (AIA), urllib
    non, et l'echec ressemble a un site mort. On fait comme le navigateur, sans
    rien relacher : l'intermediaire sert a construire la chaine, qui doit
    toujours remonter a une racine du systeme. D'ou le retrait de
    PARTIAL_CHAIN (actif par defaut depuis Python 3.13), qui sinon ferait de
    cet intermediaire telecharge une ancre de confiance."""
    import ssl
    if hote not in _TLS:
        feuille = ssl.PEM_cert_to_DER_cert(ssl.get_server_certificate((hote, 443), timeout=TIMEOUT))
        # Le champ AIA « caIssuers » (OID 1.3.6.1.5.5.7.48.2), puis l'URL en
        # IA5String : 0x86, sa longueur, ses octets. Lu par sa structure et non
        # par une extension : Let's Encrypt publie `http://yr1.i.lencr.org/`.
        aia = re.search(rb"\x2b\x06\x01\x05\x05\x07\x30\x02\x86(.)", feuille, re.S)
        if not aia or aia.group(1)[0] > 127:
            return None
        adresse = feuille[aia.end():aia.end() + aia.group(1)[0]].decode("ascii", "replace")
        time.sleep(PAUSE)
        with urllib.request.urlopen(adresse, timeout=TIMEOUT) as r:
            intermediaire = r.read(100_000)
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0)
        ctx.load_verify_locations(cadata=intermediaire if intermediaire[:1] == b"\x30"
                                  else intermediaire.decode())
        _TLS[hote] = ctx
    return _TLS[hote]


def _ouvrir(url, donnees=None, entetes=None):
    """La seule porte vers le reseau : pause de politesse, adresse encodee,
    patience quand le serveur la demande (429/503 avec Retry-After, borne a 30
    secondes, deux fois au plus), et chaine TLS completee au besoin."""
    import ssl
    req = urllib.request.Request(_uri(url), donnees, {"User-Agent": UA, **(entetes or {})})
    for essai in range(3):
        time.sleep(PAUSE)
        try:
            ctx = _TLS.get(urllib.parse.urlparse(req.full_url).hostname)
            return urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
        except urllib.error.HTTPError as e:
            attente = e.headers.get("Retry-After", "")
            patient = e.code == 429 or (e.code == 503 and attente.isdigit())
            if not patient or essai == 2:
                raise
            time.sleep(min(int(attente) if attente.isdigit() else 10, 30))
        except urllib.error.URLError as e:
            hote = urllib.parse.urlparse(req.full_url).hostname
            if (not isinstance(e.reason, ssl.SSLCertVerificationError) or hote in _TLS
                    or not _contexte_complete(hote)):
                raise


def _decoder(octets, charset=None):
    """Le charset declare (en-tete, sinon balise meta) fait foi, avec
    remplacement d'un octet fautif : sur un site de La Reunion, un seul emoji
    tronque faisait relire toute la page en latin-1 (« PrÃ©vention »)."""
    m = re.search(rb'charset=["\']?([\w-]+)', octets[:4096])
    for encodage in (charset, m and m.group(1).decode("ascii", "ignore")):
        if encodage:
            try:
                return octets.decode(encodage, "replace")
            except LookupError:
                pass
    # Rien de declare : de l'UTF-8 si ses caracteres valides l'emportent sur
    # les octets fautifs, sinon du Windows-1252 (« caf\xe9 »).
    texte = octets.decode("utf-8", "replace")
    fautifs = texte.count("�")
    if not fautifs or sum(ord(c) > 127 for c in texte) > 2 * fautifs:
        return texte
    return octets.decode("cp1252", "replace")


def _page_http(url):
    with _ouvrir(url) as r:
        return _decoder(r.read(5_000_000), r.headers.get_content_charset())


def _page_navigateur(url):
    """Repli pour les sites dont la navigation est rendue en JavaScript."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("rendu: navigateur demande mais playwright est absent. "
                 "python -m pip install -r requirements.txt")
    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page(user_agent=UA)
        page.goto(url, wait_until="networkidle", timeout=60_000)
        time.sleep(0.8)
        html = page.content()
        nav.close()
    return html


def page(url, navigateur=False):
    """La page, lue en HTTP simple ou rendue par un navigateur.

    Publique : c'est ce qu'un collecteur dedie importe pour ne pas redire la
    mecanique HTTP, la pause de politesse et le decodage.

    Un certificat que Python ne sait pas verifier meme complete (racine trop
    recente pour son magasin : « ISRG Root YR » de Let's Encrypt en 2026) se
    relit au navigateur, qui le verifie avec le sien. Rien n'est relache ;
    les PDF d'un tel site, eux, restent « pas telecharges ».
    """
    import ssl
    if navigateur:
        return _page_navigateur(url)
    try:
        return _page_http(url)
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        print(f"certificat non verifiable par Python, lecture au navigateur : {url}",
              file=sys.stderr)
        return _page_navigateur(url)


def _restreindre(html, selecteur):
    """Garde le fragment porteur des actes, quand la recette en nomme un.

    Volontairement grossier : `#id` ou `.classe`, du debut de la balise a la
    fin du document. On ne cherche pas la balise fermante correspondante, ce
    qui demanderait un vrai parseur ; couper apres suffit a ecarter un menu
    place avant le contenu, qui est le cas courant.
    """
    if not selecteur:
        return html
    attribut = "id" if selecteur.startswith("#") else "class"
    valeur = selecteur[1:]
    m = re.search(rf'<[^>]+{attribut}=["\'][^"\']*\b{re.escape(valeur)}\b', html, re.I)
    return html[m.start():] if m else html


MOIS = {m: i for i, noms in enumerate((
    ("janvier", "janv"), ("fevrier", "février", "fevr", "févr", "fev", "fév"),
    ("mars",), ("avril", "avr"), ("mai",), ("juin",), ("juillet", "juil"),
    ("aout", "août"), ("septembre", "sept"), ("octobre", "oct"),
    ("novembre", "nov"), ("decembre", "décembre", "dec", "déc")), 1) for m in noms}
# Les noms longs d'abord : « fev » ne doit pas manger le debut de « fevrier ».
# Espaces ou tirets facultatifs, annee courte admise : « 28fev2024 », « 16 décembre 24 ».
DATE_FR = re.compile(r"(?<!\d)(\d{1,2})(?:er)?[\s_-]*("
                     + "|".join(sorted(MOIS, key=len, reverse=True))
                     + r")\.?[\s_-]*((?:20)?\d{2})(?!\d)", re.I)


def date_fr(texte):
    """« Séance du 1er juillet 2026 » -> 2026-07-01, sinon None.

    Publique : la moitie des sites datent leurs seances en toutes lettres, et
    chaque collecteur reecrivait sa table des mois.
    """
    for m in DATE_FR.finditer(texte or ""):
        annee = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        d = _date_valide(annee, MOIS[m.group(2).lower()], m.group(1))
        if d:
            return d
    return None


def _fichier_pdf(url):
    """Le nom du PDF que designe ce lien, sinon None.

    Soit le chemin finit en .pdf, soit un script le sert et le nomme dans la
    query (`/cms_viewFile.php?idtf=6993&path=Liste.pdf`, `download.php?file=`) :
    constate sur une agglomeration ou la page entiere passait pour vide."""
    u = urllib.parse.urlparse(url)
    if u.path.lower().endswith(".pdf"):
        return urllib.parse.unquote(u.path.rsplit("/", 1)[-1])
    for valeurs in urllib.parse.parse_qs(u.query).values():
        for v in valeurs:
            if v.lower().endswith(".pdf"):
                return v.replace("\\", "/").rsplit("/", 1)[-1]
    return None


def publiact(uid, dossiers=("délib", "deliber", "conseil", "procès", "proces", "compte")):
    """Les actes d'une collectivite publies sur Publiact, plateforme commune a
    de nombreuses collectivites. Leur site n'en montre qu'une iframe
    (`https://publiact.fr/i/<uid>/1`) rendue en JavaScript, sans un seul lien :
    lue en HTML, la page parait vide. L'iframe interroge une API JSON publique,
    qu'on lit directement. La date affichee par Publiact est celle de la mise
    en ligne, jamais celle de la seance : seule celle du nom du fichier compte.

    Publiact range les documents en dossiers (« Délibérations », « Arrêtés »,
    « Décisions »…) : a Divonne-les-Bains, 4 137 documents dont 743
    deliberations. Seuls les dossiers dont le nom contient l'un des
    `dossiers` sont lus, sous-dossiers compris ; `dossiers=None` lit tout. Si
    aucun dossier ne correspond, tout est lu, et le script le dit.
    """
    import json
    base = f"https://publiact.fr/api/v1/public/integrations/uid/{uid}"
    filtre = {}
    if dossiers:
        racines = [f for t in json.loads(page(f"{base}/folders")) for f in t.get("children") or []]
        ids = [f["id"] for f in racines if any(m in f["name"].lower() for m in dossiers)]
        if ids:
            filtre = {f"filters[folderIds][{i}]": x for i, x in enumerate(ids)}
        else:
            print(f"publiact {uid} : aucun dossier ne correspond a {dossiers}, tout est lu "
                  f"({', '.join(f['name'] for f in racines)}).", file=sys.stderr)
    out, n = [], 0
    while True:
        q = urllib.parse.urlencode({**filtre, "muiModels[pagination][pageSize]": 100,
                                    "muiModels[pagination][page]": n})
        d = json.loads(page(f"{base}/documents?{q}"))
        for r in d["rows"]:
            nom = r["namePublic"]
            titre = nom[:-4] if nom.lower().endswith(".pdf") else nom
            out.append({"titre": titre, "fichier": nom, "doc_id": f"publiact-{r['id']}",
                        "date": date_num(titre) or date_fr(titre),
                        "url": f"https://publiact.fr/api/v1/public/documents/{r['id']}/download/inline"})
        n += 1
        if not d["rows"] or len(out) >= d["count"]:
            return out


def megalis(siren, types=(1,)):
    """Les actes d'une collectivite bretonne, depuis l'open data de Megalis.

    Le site communal n'en montre qu'une iframe (`data.megalis.bretagne.bzh/
    ?siren=…`) rendue en JavaScript ; derriere, une API GET publique rend chaque
    acte transmis au controle de legalite avec sa **date de decision**, son
    objet et un PDF a adresse stable -- une source de qualite `portail`.
    `types` : 1 = deliberations (defaut) ; l'iframe d'une commune nomme les
    siens (`types_actes=2,3,6,72` : arretes et autres). Les annexes ne sont pas
    des actes : elles ne sont pas reprises.
    """
    import json
    api = "https://data-publication.megalis.bretagne.bzh/mq_apis/actes/v1/search?"
    out, vus, suite = [], set(), None
    while True:
        q = {"query": "", "siren": siren, "types_actes": ",".join(map(str, types)), "lignes": 100}
        if suite:
            q["page_suivante"] = suite
        d = json.loads(page(api + urllib.parse.urlencode(q)))
        for r in d["resultats"]:
            if r["id"] in vus:
                continue
            vus.add(r["id"])
            out.append({"titre": " ".join(r["objet"].split()), "doc_id": f"megalis-{r['id']}",
                        "fichier": r["url"].rsplit("/", 1)[-1], "url": r["url"],
                        "date": (r.get("date_acte") or "")[:10] or None})
        suite = d.get("page_suivante")
        if not d["resultats"] or not suite or len(vus) >= d["nb_resultats"]:
            return out


def _post_json(url, donnees):
    """Une recherche publique qui ne s'interroge qu'en POST. Reservee aux
    adaptateurs de plateforme de ce fichier, relus : le corps est un filtre de
    lecture, sans effet sur la source. Le navigateur de l'agent, lui, ne
    soumet toujours rien (AGENTS.md, invariant 4)."""
    import json
    with _ouvrir(url, json.dumps(donnees).encode(), {"Content-Type": "application/json"}) as r:
        return json.load(r)


def dematdoc(url_publique):
    """Les actes d'une collectivite publies sur DematDoc (`<ville>.dematdoc.eu`).

    `url_publique` est l'adresse que montre le site, filtre compris :
    `https://dax.dematdoc.eu/public/14?filters=14|121|Délibération Conseil municipal`.
    L'application est en JavaScript ; elle interroge une API qui n'accepte que
    le POST, pour une simple recherche (autorise par l'utilisateur le
    2026-10-01, voir _post_json). 100 documents par reponse, la suite par
    `get-documents-lazy` ; les actes archives (fin d'affichage passee) restent
    publics et sont repris. Les champs sont propres a chaque client : la date
    de l'acte se cherche parmi les champs de date qui ne sont pas des dates
    d'affichage. La version biffee (anonymisee) est preferee quand elle existe.
    """
    u = urllib.parse.urlparse(url_publique)
    hote = f"{u.scheme}://{u.netloc}"
    doctype = u.path.rstrip("/").rsplit("/", 1)[-1]
    filtre = urllib.parse.parse_qs(u.query).get("filters", [None])[0]
    out, vus = [], set()
    for archive in (False, True):
        d = _post_json(f"{hote}/api/public/get-documents/{doctype}",
                       {"filters": {"params": {"archive": archive}, "indexfields": [], "document": []},
                        "filtersURL": filtre})
        while True:
            for doc in d["documents"]:
                if doc["id"] in vus:
                    continue
                vus.add(doc["id"])
                v = {k: str((x or {}).get("displayValue") or "").strip()
                     for k, x in (doc.get("values") or {}).items()}
                dates = [re.match(r"(\d{4})-(\d{2})-(\d{2})", v[k]) for k in v
                         if "DATE" in k and not k.startswith("CI_DATE")]
                date = next((_date_valide(*m.groups()) for m in dates if m), None)
                out.append({"titre": v.get("OBJET") or doc["name"], "doc_id": f"dematdoc-{doc['id']}",
                            "fichier": (doc.get("bifferPath") or doc["path"]).rsplit("/", 1)[-1],
                            "url": hote + (doc.get("bifferPath") or doc["path"]),
                            "numero": next((v[k] for k in v if k.startswith("NUMERO") and v[k]), None),
                            "date": date or date_num(doc["name"]) or date_fr(doc["name"])})
            if not d.get("nextDocsIds"):
                break
            d = _post_json(f"{hote}/api/public/get-documents-lazy", d["nextDocsIds"])
    return out


def legalview(url_publique, themes=("conseil",)):
    """Les actes d'une collectivite sur LegalView (affichage legal numerique,
    `www.saas-legalview.fr/public/legalview/<organisation>`).

    Application JavaScript ; derriere, une API GET publique range les
    documents en themes (« Conseil Municipal » > « Conseil municipal
    28/09/2026 »). On ne garde que les themes dont le nom contient l'un des
    `themes` (arretes et avis de marche restent dehors), sous-themes compris.
    La date de seance se lit dans le nom du theme, sinon dans le titre ; la
    date de publication n'en est jamais une. Le PDF est servi sous `/api` :
    sans ce prefixe, l'adresse repond 200... avec une page HTML.
    """
    import json
    u = urllib.parse.urlparse(url_publique)
    hote, org = f"{u.scheme}://{u.netloc}", u.path.rstrip("/").rsplit("/", 1)[-1]
    api = f"{hote}/api/public/legalview/org/{org}"

    def retenus(noeuds, garde=False):
        for n in noeuds:
            dedans = garde or any(t in n["name"].lower() for t in themes)
            if dedans:
                yield n
            yield from retenus(n.get("children") or [], dedans)

    out = []
    for theme in retenus(json.loads(page(f"{api}/themes-tree"))["themes"]):
        seance = date_num(theme["name"]) or date_fr(theme["name"])
        n = 1
        while True:
            d = json.loads(page(f"{api}/theme/{theme['_id']}?page={n}&limit=100"))
            for doc in d["documents"]:
                titre = " ".join(doc["title"].split())
                out.append({"titre": titre, "doc_id": f"legalview-{doc['_id']}",
                            "fichier": doc["filePath"].rsplit("/", 1)[-1],
                            "url": f"{hote}/api/{doc['filePath'].lstrip('/')}",
                            "date": seance or date_num(titre) or date_fr(titre)})
            if not d["pagination"].get("hasMore"):
                break
            n += 1
    return out


def opendatasoft(domaine, jeu):
    """Les actes publies en open data sur un portail Opendatasoft
    (`<ville>.opendatasoft.com` ou `data.<ville>.fr`), un jeu de donnees par
    serie (`deliberations-2026`, `proces-verbaux-conseils-municipaux-…`).

    Chaque enregistrement porte un PDF joint, mais les noms de champs sont
    propres a chaque jeu : on les reconnait par leur role. Le titre est le
    premier champ objet/titre/intitule ; la date, le premier champ « date »
    qui n'est ni une transmission en prefecture, ni une publication, ni un
    affichage (a Cachan, `delib_date` et non `pref_date`) ; le numero, un
    champ « num ». Un enregistrement sans PDF n'est pas un acte collecte.
    """
    import json
    lignes = json.loads(page(f"https://{domaine}/api/explore/v2.1/catalog/datasets/"
                             f"{jeu}/exports/json"))
    out = []
    for r in lignes:
        pdf = next((v for v in r.values() if isinstance(v, dict) and v.get("url")
                    and str(v.get("format", "")).lower() == "pdf"), None)
        if not pdf:
            continue
        titre = next((str(v) for k, v in r.items() if v and re.search(r"objet|titre|intitul", k, re.I)),
                     pdf.get("filename") or "")
        dates = [str(v) for k, v in r.items() if v and "date" in k.lower()
                 and not re.search(r"pref|transm|publi|affich|recep|ar_|mise", k, re.I)]
        d_champ = next((d for d in map(lambda v: date_num(v) or date_fr(v), dates) if d), None)
        d_titre = date_num(titre) or date_fr(titre)
        # Champ et titre en desaccord (PV de Cachan : champ du 27, seance du
        # 26) : aucune date ne gagne.
        out.append({"titre": " ".join(titre.split()), "doc_id": f"ods-{pdf['id']}",
                    "fichier": pdf.get("filename") or pdf["id"], "url": pdf["url"],
                    "numero": next((str(v) for k, v in r.items() if v and "num" in k.lower()), None),
                    "date": None if d_champ and d_titre and d_champ != d_titre
                    else d_champ or d_titre})
    return out


DRIVE_ENTREE = re.compile(r'<a href="([^"]+)"[^>]*>.*?flip-entry-title">([^<]+)<', re.S)


def drive(dossier):
    """Les PDF d'un dossier Google Drive public, sous-dossiers compris.

    Des villages publient leurs actes la, faute de site qui sache les heberger.
    L'interface de Drive est en JavaScript, mais sa vue integrable
    (`embeddedfolderview`) est du HTML simple : un lien par fichier ou dossier.
    Les dossiers par annee sont parcourus. Le telechargement passe par
    `uc?export=download` ; au-dela de ~100 Mo, Drive repond une page HTML
    d'avertissement, que la verification %PDF de _telecharger refuse.
    """
    out, a_voir, vus = [], [dossier], set()
    while a_voir:
        d = a_voir.pop(0)
        if d in vus:
            continue
        vus.add(d)
        html = page(f"https://drive.google.com/embeddedfolderview?id={d}")
        for lien, nom in DRIVE_ENTREE.findall(html):
            nom = html_mod.unescape(nom).strip()
            if m := re.search(r"/folders/([\w-]+)", lien):
                a_voir.append(m.group(1))
            elif (m := re.search(r"/file/d/([\w-]+)", lien)) and nom.lower().endswith(".pdf"):
                titre = nom[:-4]
                out.append({"titre": titre, "fichier": nom, "doc_id": f"drive-{m.group(1)}",
                            "date": date_num(titre) or date_fr(titre),
                            "url": f"https://drive.google.com/uc?export=download&id={m.group(1)}"})
    return out


HORS_ACTE = re.compile(r"convoc|ordres? du jour|(?:^|[\s_.-])o\.?d\.?j(?:$|[\s_.-])|^\s*oj\b", re.I)


def sans_convocations(actes):
    """Les actes, convocations et ordres du jour ecartes.

    Ils annoncent une seance, ils ne la prouvent pas : rien n'y est vote. Les
    garder coute deux fois -- ils prennent les places de `--limite`, triee par
    date, devant les proces-verbaux qu'on veut archiver, puis encombrent la
    file de lecture. Les deux premiers collecteurs ecrits par un agent seul
    reecrivaient chacun ce filtre."""
    return [a for a in actes if not HORS_ACTE.search(f"{a['titre']} {a.get('fichier', '')}")]


def actes_de_la_page(html, base_url):
    """Les PDF cites par la page : (titre, date, url), dedoublonnes.

    La date se lit dans le nom du fichier, sinon dans l'intitule du lien.
    JAMAIS dans l'URL entiere : les liens signes d'un CDN portent un parametre
    `Expires` de dix chiffres ou le motif de date trouve son compte et rend
    une date absurde.
    """
    out, vus = [], set()
    for href, dedans in LIEN.findall(html) + [(s, "") for s in PDF_EMBARQUE.findall(html)]:
        # `&amp;` dans un href est du HTML, pas de l'URL.
        url = urllib.parse.urljoin(base_url, html_mod.unescape(href.strip()))
        fichier = _fichier_pdf(url)
        if not fichier:
            continue
        # Un meme document peut etre lie deux fois ; deux documents peuvent
        # porter le meme nom dans deux dossiers. C'est identifiant() qui tranche.
        cle = identifiant(url)
        if cle in vus:
            continue
        vus.add(cle)
        # Le HTML brut porte ses entites : `d&eacute;lib&eacute;rations`
        # deviendrait un titre tel quel, la ou un navigateur rendait le
        # texte. Les balises sautent d'abord, les entites ensuite.
        etiquette = " ".join(BRUIT_LIBELLE.sub(
            " ", html_mod.unescape(BALISE.sub(" ", dedans))).split())
        # « Consulter », « Télécharger » : un bouton, pas un titre. Le nom du
        # fichier en dit alors davantage.
        if etiquette.lower().strip(" .:>»") in LIBELLES_MUETS:
            etiquette = ""
        nom = fichier[:-4].replace("+", " ").replace("_", " ")
        titre = etiquette or nom
        # Fichier et intitule datent chacun ; s'ils se contredisent, aucune
        # date ne gagne (`2026-02-01-refacturation.pdf` intitule
        # « délibération-20260205-01 ») : dans le doute, l'absence s'affiche.
        d_fichier = date_num(fichier.replace("+", " "))
        d_lien = date_num(etiquette) or date_fr(etiquette)
        date = (None if d_fichier and d_lien and d_fichier != d_lien
                else d_fichier or d_lien or date_fr(nom))
        out.append({"titre": titre, "fichier": fichier, "date": date, "url": url})
    return out


# ------------------------------------------------------ collecteur dedie
def chemin_collecteur(insee):
    return os.path.join(COLLECTEURS, f"{insee}.py")


def chemin_memoire(insee):
    """Ce qu'on sait de cette collectivite, au-dela de la facon de la collecter.

    Le collecteur dit comment aller chercher. La memoire dit ce qu'on a appris
    en lisant : ce qui a ete essaye et ecarte, la structure de ses actes, ses
    pieges. Ce script ne la lit pas -- il ne juge de rien -- mais il la
    signale, parce qu'un agent qui collecte sans elle refait des impasses.
    """
    return os.path.join(MEMOIRE, f"{insee}.md")


MARQUEUR_JOURNAL = "## Journal automatique"
JOURNAL_MAX = 10


def journaliser_passage(insee, trouves, nouveaux, telecharges, n_echecs):
    """Consigne un passage dans data/memoire/<insee>.md, meme si personne ne l'ouvre.

    Ce que cette fonction ecrit est purement factuel -- une date, des comptes
    -- jamais un jugement : dire qu'un document merite une alerte ou qu'une
    piste est une impasse reste le travail de l'agent (voir SKILL.md). Mais la
    trace d'un passage, elle, n'a pas besoin d'un agent pour exister, et
    l'ecrire ici garantit qu'elle existe TOUJOURS, y compris quand personne ne
    complete le reste du carnet.

    Rend True quand la memoire n'a jamais recu d'analyse d'agent (aucune
    section au-dela du journal) malgre AU MOINS UN PASSAGE ANTERIEUR : c'est
    le signal que le skill l'exige et que main() fait remonter bruyamment. Au
    tout premier passage, la memoire s'ecrit apres la lecture (etape 5 du
    skill) : l'alerte y inquietait sans raison.
    """
    chemin = chemin_memoire(insee)
    # Heure locale, decalage affiche : la base garde l'UTC, mais ce journal
    # se lit par un humain, qui prenait « 15:30 » pour son heure.
    horodatage = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M (UTC%z)")
    ligne = (f"- {horodatage} — {trouves} acte(s) vu(s), {nouveaux} nouveau(x), "
            f"{telecharges} PDF, {n_echecs} echec(s).")
    if os.path.exists(chemin):
        texte = open(chemin, encoding="utf-8").read()
    else:
        entete = ("_Mémoire pas encore rédigée par un agent : structure "
                 "des actes, pièges de qualification, pistes écartées. "
                 "Voir le skill, recherche.md « La mémoire », avant "
                 "d'écrire ici._")
        texte = f"# {insee}\n\n{entete}\n\n{MARQUEUR_JOURNAL}\n"
    if MARQUEUR_JOURNAL not in texte:
        texte = texte.rstrip("\n") + f"\n\n{MARQUEUR_JOURNAL}\n"
    os.makedirs(MEMOIRE, exist_ok=True)   # absent d'un depot fraichement clone
    tete, _, queue = texte.partition(MARQUEUR_JOURNAL)
    lignes = queue.lstrip("\n").split("\n")
    n = 0
    while n < len(lignes) and lignes[n].startswith("- "):
        n += 1
    # Le plus recent en tete du journal : c'est ce qu'on veut voir d'abord.
    # Plafonne : l'agent relit ce fichier a chaque passage, et un an de suivi
    # hebdomadaire y empilerait cinquante lignes sans rien lui apprendre --
    # l'historique complet est en base (`moissonnee_le`). Seules les lignes du
    # journal sont touchees ; ce qu'un agent a ecrit apres reste intact.
    passages = [ligne] + lignes[:n][:JOURNAL_MAX - 1]
    texte = tete + MARQUEUR_JOURNAL + "\n" + "\n".join(passages + lignes[n:])
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write(texte)
    sections = re.findall(r"^## (.+)$", texte, re.M)
    narrative = [s for s in sections if s.strip() != MARQUEUR_JOURNAL[3:].strip()]
    return not narrative and len(passages) > 1


def lire_suivi(con):
    """{insee: bool} depuis la table `suivi`. Rien d'enregistre -> {}.

    En base plutot que dans un fichier a part : c'est ce qui permet au
    dashboard de l'afficher sans parser un yaml, avec la meme lecture seule
    que le reste. Pas de miroir dans data/portails.yaml -- ce choix est
    personnel, contrairement a l'adresse d'un portail."""
    return {r["insee"]: bool(r["actif"]) for r in con.execute("SELECT insee, actif FROM suivi")}


def ecrire_suivi(con, insee, valeur):
    """Marque une collectivite suivie ou non. Un ON CONFLICT vaut mieux qu'un
    lire-puis-reecrire : une seule ligne, pas de risque de piler deux etats."""
    con.execute(
        "INSERT INTO suivi (insee, actif, maj_le) VALUES (?,?,?) "
        "ON CONFLICT(insee) DO UPDATE SET actif=excluded.actif, maj_le=excluded.maj_le",
        (insee, 1 if valeur else 0, maintenant()))
    con.commit()


def etat(con, registre):
    """Une ligne par collectivite connue (registre, suivi ou actes en base).

    Ce qu'il faut savoir avant une passe planifiee, en une commande : une
    collectivite suivie sans collecteur fait echouer sa tache chaque semaine
    sans que personne ne le voie (constate : Lille, seule suivie, n'en avait
    pas)."""
    suivi = lire_suivi(con)
    stats = {r["insee"]: r for r in con.execute(
        "SELECT d.insee, COUNT(*) actes, MAX(d.moissonnee_le) dernier, "
        "SUM(d.pdf_chemin_local IS NOT NULL AND d.statut_lecture<>'echec' AND NOT EXISTS "
        "  (SELECT 1 FROM syntheses_reunions s WHERE s.deliberation_id=d.id)) a_lire, "
        "SUM(EXISTS (SELECT 1 FROM montants_extraits m WHERE m.deliberation_id=d.id) "
        "  AND NOT EXISTS (SELECT 1 FROM syntheses_reunions s WHERE s.deliberation_id=d.id)) inach, "
        "MAX(d.commune) nom FROM deliberations d GROUP BY d.insee")}
    codes = sorted(set(registre) | set(suivi) | set(stats))
    return [{"code": c, "nom": (registre.get(c) or {}).get("nom") or (stats[c]["nom"] if c in stats else c),
             "suivi": suivi.get(c, False), "collecteur": os.path.exists(chemin_collecteur(c)),
             "dernier": stats[c]["dernier"][:16].replace("T", " ") if c in stats else None,
             "actes": stats[c]["actes"] if c in stats else 0,
             "a_lire": stats[c]["a_lire"] or 0 if c in stats else 0,
             "inachevees": stats[c]["inach"] or 0 if c in stats else 0} for c in codes]


def charger_collecteur(insee):
    """Le module `data/collecteurs/<insee>.py`, ou None s'il n'existe pas."""
    chemin = chemin_collecteur(insee)
    if not os.path.exists(chemin):
        return None
    import importlib.util
    # Le collecteur fait `from collecter import ...` : sans cette ligne, Python
    # relirait ce fichier une seconde fois sous le nom `collecter`, puisqu'il
    # tourne ici sous le nom `__main__`. Deux copies du meme module, deux jeux
    # de constantes, et un doute inutile sur laquelle repond.
    sys.modules.setdefault("collecter", sys.modules[__name__])
    spec = importlib.util.spec_from_file_location(f"collecteur_{insee}", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "actes"):
        sys.exit(f"{chemin} n'expose pas de fonction actes(ctx).")
    return module


MODELE = '''"""Collecteur pour {nom} ({insee}).

Ecrit apres avoir regarde {url} et compris comment elle liste les actes.
Ne pas y remettre de recherche : si la page change au point que ce fichier ne
marche plus, c'est a l'agent de la rouvrir et de le reecrire.
"""
from collecter import actes_de_la_page, date_fr, date_num, page, sans_convocations, ATTENDU_INCONNU
# Plateformes deja lues : publiact, megalis, drive, dematdoc, legalview, opendatasoft

URL = "{url}"
ATTENDU = {attendu}   # le compte que donne `--a-blanc` le jour ou ce collecteur est ecrit


def actes(ctx):
    """Rend [{{titre, fichier, date, url}}, ...] pour tous les actes publies.

    Facultatif, sur un portail : numero, service, direction, rapporteur, et
    doc_id (identifiant stable de l'acte chez la source, sinon le fichier).
    date_fr("Seance du 1er juillet 2026") lit une date en toutes lettres.
    """
    html = page(URL)                    # page(URL, navigateur=True) si rendu JS
    return sans_convocations(actes_de_la_page(html, URL))
'''


# ---------------------------------------------------------------- ecriture
def _telecharger(url, chemin):
    """En flux vers un .part renomme a la fin : un recueil de 8 Mo ne passe
    pas par la memoire, et une coupure (Ctrl+C compris) ne laisse jamais un
    PDF tronque sous son vrai nom."""
    partiel = chemin + ".part"
    try:
        with _ouvrir(url) as r, open(partiel, "wb") as f:
            shutil.copyfileobj(r, f)
        # Un script de telechargement repond volontiers 200 avec une page
        # d'erreur HTML : archivee sous un nom .pdf, elle passerait pour la
        # preuve d'un acte. La signature %PDF tient dans le premier kilo-octet.
        with open(partiel, "rb") as f:
            if b"%PDF" not in f.read(1024):
                raise ValueError("ce n'est pas un PDF")
        os.replace(partiel, chemin)
    finally:
        if os.path.exists(partiel):
            os.unlink(partiel)


def _empreinte(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def synchroniser_registre(con, insee, entree):
    """Recopie l'entree de portails.yaml dans les tables que lit le dashboard.

    Le yaml fait seul autorite : l'agent n'ecrit qu'a un endroit, et la table
    `portails` ne peut plus diverger de lui (constate : trois lignes en base
    pour quatre collectivites au registre, et un nom au mauvais encodage).
    """
    if not entree.get("nom"):
        return
    con.execute("INSERT OR REPLACE INTO portails (insee,nom,type,url,verifie_le,notes)"
                " VALUES (?,?,?,?,?,?)",
                (insee, entree["nom"],
                 entree.get("type") if entree.get("type") in SOURCES else "site",
                 entree.get("url"), entree.get("verifie_le") or maintenant()[:10],
                 entree.get("notes")))
    if entree.get("epci_siren") and entree.get("epci_nom"):
        con.execute("INSERT OR REPLACE INTO appartenances_epci "
                    "(insee,epci_siren,epci_nom,releve_le) VALUES (?,?,?,?)",
                    (insee, entree["epci_siren"], entree["epci_nom"],
                     entree.get("verifie_le") or maintenant()[:10]))
    con.commit()


def _doc_id(con, insee, source, a):
    """L'identite d'un acte sans identifiant publie : son chemin (identifiant()).

    Sauf quand une autre seance a deja ete enregistree a la meme adresse :
    certains sites ecrasent chaque mois le meme fichier (Bethune :
    `user_upload/LISTE_DES_DELIBERATIONS_POUR_PUBLICATION_SITE_VILLE.pdf`).
    C'est alors un autre document, qui doit avoir sa ligne et sa propre copie
    archivee -- sinon l'archive de juin servirait de preuve a la seance de
    septembre. Le dire, car une date simplement corrigee y ressemble.
    """
    base = identifiant(a["url"])
    if not a.get("date"):
        return base
    connu = con.execute(
        "SELECT s.date_seance d FROM deliberations x LEFT JOIN seances s ON s.id=x.seance_id "
        "WHERE x.insee=? AND x.source=? AND x.doc_id_source=?", (insee, source, base)).fetchone()
    if not connu or not connu["d"] or connu["d"] == a["date"]:
        return base
    distinct = f"{base}-{a['date']}"
    if con.execute("SELECT 1 FROM deliberations WHERE insee=? AND source=? AND doc_id_source=?",
                   (insee, source, distinct)).fetchone():
        return distinct
    print(f"meme adresse, autre seance ({connu['d']} puis {a['date']}) : "
          f"enregistre comme un document distinct -- {a['titre'][:50]}", file=sys.stderr)
    return distinct


def enregistrer(con, insee, nom, actes, telecharger=True, limite=None, source="site"):
    """Ecrit les actes manquants. Rejouable : rien n'est duplique.

    `limite` borne les TELECHARGEMENTS, pas le referencement : tous les actes
    entrent en base avec leur URL, seuls les `limite` plus recents sont
    archives. Une grande ville publie des recueils de plusieurs mega-octets par
    seance, et tout aspirer d'un coup coute des gigaoctets pour des documents
    que personne ne lira. Les autres restent « pas telecharge » sur le
    dashboard, et un passage ulterieur les prendra.
    """
    if limite is not None:
        # Les plus recents d'abord : ce sont ceux qu'on veut lire.
        rang = {id(x): i for i, x in enumerate(
            sorted(actes, key=lambda x: x["date"] or "", reverse=True))}
        a_archiver = {id(x) for x in actes if rang[id(x)] < limite}
    else:
        a_archiver = None
    horodatage = maintenant()
    dossier = os.path.join(PDF_DIR, insee)
    os.makedirs(dossier, exist_ok=True)
    nouveaux = telecharges = 0
    echecs = []
    for a in actes:
        seance_id = None
        if a["date"]:
            con.execute("INSERT OR IGNORE INTO seances (insee,date_seance,source,"
                        "moissonnee_le) VALUES (?,?,?,?)",
                        (insee, a["date"], source, horodatage))
            seance_id = con.execute(
                "SELECT id FROM seances WHERE insee=? AND date_seance=? AND source=?",
                (insee, a["date"], source)).fetchone()["id"]
        doc_id = str(a.get("doc_id") or _doc_id(con, insee, source, a))
        avant = con.total_changes
        con.execute(
            "INSERT OR IGNORE INTO deliberations (seance_id,insee,commune,numero,titre,"
            "service,direction,rapporteur,source,doc_id_source,pdf_url,moissonnee_le)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (seance_id, insee, nom, a.get("numero"), a["titre"], a.get("service"),
             a.get("direction"), a.get("rapporteur"), source, doc_id, a["url"], horodatage))
        neuf = con.total_changes - avant
        nouveaux += neuf
        # L'URL est reprise a chaque passage : sur un CDN signe, celle qui est
        # en base a pu expirer entre-temps.
        # Titre, numero, seance et URL se relisent sur la source a chaque
        # passage : un collecteur corrige ce qu'un passage plus fruste avait
        # mal lu (dix actes de la MEL intitules « Deliberations »). Ce que la
        # page ne donne pas (None) ne remplace jamais une valeur connue.
        con.execute("UPDATE deliberations SET pdf_url=?, titre=?, "
                    "numero=COALESCE(?,numero), seance_id=COALESCE(?,seance_id), "
                    "service=COALESCE(?,service), direction=COALESCE(?,direction), "
                    "rapporteur=COALESCE(?,rapporteur) "
                    "WHERE insee=? AND source=? AND doc_id_source=?",
                    (a["url"], a["titre"], a.get("numero"), seance_id, a.get("service"),
                     a.get("direction"), a.get("rapporteur"), insee, source, doc_id))
        if not telecharger or (a_archiver is not None and id(a) not in a_archiver):
            continue
        # Deja archive et deja note : rien a relire ni a retelecharger, quel
        # que soit le nom du fichier (les premiers passages en utilisaient
        # d'autres). Recalculer l'empreinte a chaque passage relisait tout
        # l'historique -- le gigaoctet a Paris.
        note = con.execute("SELECT pdf_chemin_local p FROM deliberations WHERE insee=? "
                           "AND source=? AND doc_id_source=?", (insee, source, doc_id)).fetchone()
        if note and note["p"] and os.path.exists(os.path.join(RACINE, note["p"])):
            continue
        chemin = os.path.join(dossier, f"{doc_id}.pdf")
        if not os.path.exists(chemin):
            # Un lien mort sur un site municipal est banal : une page garde des
            # annees de liens et tous ne survivent pas aux refontes. Il ne doit
            # pas emporter la collecte entiere. L'acte reste reference avec son
            # URL, simplement sans copie archivee, et le dashboard l'affiche
            # « pas telecharge ».
            try:
                _telecharger(a["url"], chemin)
            except Exception as souci:
                echecs.append((a["titre"], type(souci).__name__, str(souci)[:60]))
                continue
            telecharges += 1
        con.execute(
            "UPDATE deliberations SET pdf_chemin_local=?, pdf_empreinte_sha256=?"
            " WHERE insee=? AND source=? AND doc_id_source=?",
            (relatif(chemin), _empreinte(chemin), insee, source, doc_id))
    con.commit()
    return nouveaux, telecharges, echecs


def verdict_ecart(trouves, attendu):
    """Une recette perimee doit se voir. Renvoie None si tout va bien.

    Un site refait ne provoque pas d'erreur : la page repond, les liens ont
    change de place, et la collecte rend zero acte. Sans ce controle, une
    surveillance hebdomadaire continuerait d'annoncer « rien de neuf »
    pendant des mois. Le seuil est volontairement large : une page qui perd
    la moitie de ses actes a ete refaite, une qui en gagne n'a rien de
    suspect.
    """
    if attendu is None:
        return None
    if trouves == 0 and attendu > 0:
        return (f"0 acte trouve alors que le dernier passage en voyait {attendu}. "
                "La page a probablement ete refaite.")
    if attendu >= 4 and trouves * 2 < attendu:
        return (f"{trouves} acte(s) trouve(s) contre {attendu} au dernier passage. "
                "Chute inexpliquee.")
    return None


# -------------------------------------------------------------------- CLI
def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--insee")
    p.add_argument("--db")
    p.add_argument("--registre", default=REGISTRE)
    p.add_argument("--a-blanc", action="store_true", dest="a_blanc",
                   help="montre ce qui serait ecrit, sans rien ecrire")
    p.add_argument("--limite", type=int, metavar="N",
                   help="ne telecharge que les N actes les plus recents "
                        "(tous restent references)")
    p.add_argument("--forcer", action="store_true",
                   help="ecrit meme si le nombre d'actes s'est effondre")
    p.add_argument("--modele", metavar="INSEE",
                   help="imprime un collecteur dedie a adapter, puis s'arrete")
    p.add_argument("--memoire", metavar="INSEE",
                   help="imprime la memoire de cette collectivite, puis s'arrete")
    p.add_argument("--suivi", metavar="INSEE:on|off",
                   help="marque (ou demarque) une collectivite en suivi actif, "
                        "puis s'arrete")
    p.add_argument("--etat", action="store_true",
                   help="bilan de chaque collectivite connue : suivi, collecteur, "
                        "dernier acte ajoute, actes a lire -- puis s'arrete")
    p.add_argument("--suivi-liste", action="store_true",
                   help="liste les codes des collectivites en suivi actif "
                        "(un par ligne), puis s'arrete")
    a = p.parse_args()

    if a.suivi:
        insee, _, bascule = a.suivi.partition(":")
        if bascule not in ("on", "off"):
            sys.exit("--suivi attend INSEE:on ou INSEE:off")
        con = db(a.db) if a.db else db()
        ecrire_suivi(con, insee, bascule == "on")
        print(f"{insee} : suivi {'actif' if bascule == 'on' else 'arrete'}.")
        if bascule == "off":
            print("Le suivi ecrit ici n'arrete pas une tache planifiee "
                  "existante : annuler aussi le `/schedule` correspondant, "
                  "sinon la collecte continuera de tourner.", file=sys.stderr)
        return

    if a.etat:
        con = db(a.db) if a.db else db()
        lignes = etat(con, recettes(a.registre))
        print("code       suivi  collecteur  dernier ajout     actes  a lire  inachevees  nom")
        for l in lignes:
            print(f"{l['code']:<10} {'oui' if l['suivi'] else '-':<6} "
                  f"{'oui' if l['collecteur'] else 'NON':<11} {l['dernier'] or 'jamais':<17} "
                  f"{l['actes']:>5}  {l['a_lire']:>6}  {l['inachevees']:>10}  {l['nom']}")
        for l in lignes:
            if l["suivi"] and not l["collecteur"]:
                print(f"PROBLEME : {l['code']} est suivie mais sans collecteur : la tache "
                      "planifiee echouera. Voir le skill, recherche.md.", file=sys.stderr)
        return

    if a.suivi_liste:
        con = db(a.db) if a.db else db()
        for insee, actif in sorted(lire_suivi(con).items()):
            if actif:
                print(insee)
        return

    if a.memoire:
        chemin = chemin_memoire(a.memoire)
        if not os.path.exists(chemin):
            # Pas une erreur : la premiere fois, c'est la reponse attendue.
            print(f"aucune memoire pour {a.memoire} : collectivite jamais traitee.")
            return
        sys.stdout.write(open(chemin, encoding="utf-8").read())
        return
    if not a.insee and not a.modele:
        p.error("--insee est requis")
    registre = recettes(a.registre)
    if a.modele:
        e = registre.get(a.modele) or {}
        texte = MODELE.format(insee=a.modele, nom=e.get("nom") or a.modele,
                              url=e.get("url") or "https://exemple.fr/deliberations",
                              attendu=(e.get("recette") or {}).get("attendu")
                              or "ATTENDU_INCONNU")
        # Ecrit par le script, pas par une redirection : `>` sous PowerShell 5
        # produit de l'UTF-16, que Python refuse ensuite d'importer.
        cible = chemin_collecteur(a.modele)
        if os.path.exists(cible):
            sys.exit(f"{cible} existe deja : rien n'a ete ecrase.")
        os.makedirs(COLLECTEURS, exist_ok=True)
        with open(cible, "w", encoding="utf-8", newline="\n") as f:
            f.write(texte)
        print(f"squelette ecrit : {relatif(cible)} -- a adapter au site.")
        if not e:
            print(f"{a.modele} n'est pas encore dans {a.registre} : le squelette porte "
                  "une URL d'exemple et le code pour nom. Ecrire d'abord l'entree du "
                  "registre (skill, recherche.md), puis relancer --modele sur un "
                  "fichier supprime, ou corriger URL a la main.", file=sys.stderr)
        return
    entree = registre.get(a.insee) or {}
    nom = entree.get("nom") or a.insee
    url = entree.get("url")
    if not entree.get("nom"):
        print(f"ATTENTION : {a.insee} n'a pas de nom dans {a.registre} -- le "
              f"code sert de nom faute de mieux, et c'est ce qui sera ecrit "
              f"dans deliberations.commune pour tous les actes de ce passage. "
              f"Ajouter l'entree dans {a.registre} (skill, "
              "recherche.md « Le registre ») puis relancer pour corriger.",
              file=sys.stderr)

    # 1. Un collecteur dedie prend la main sur tout le reste.
    module = charger_collecteur(a.insee)
    if module is not None:
        trouves = module.actes({"insee": a.insee, "nom": nom, "url": url})
        attendu = getattr(module, "ATTENDU", None)
        origine = chemin_collecteur(a.insee)
    else:
        # 2. Sinon la recette du registre, pour les pages qui se lisent betement.
        if not entree:
            sys.exit(f"{a.insee} n'est ni dans {a.registre}, ni dans "
                     f"{COLLECTEURS}. Cette collectivite n'a pas encore ete "
                     "reperee : passer par l'agent (skill france-transparence), "
                     "qui trouvera ou elle publie.")
        recette = entree.get("recette") or {}
        if not recette:
            sys.exit(f"{a.insee} est repere mais sans moyen de rejouer sa "
                     f"collecte. Ecrire {chemin_collecteur(a.insee)} "
                     f"(`--modele {a.insee}` en donne un squelette) ou une "
                     "`recette` dans le registre.")
        if not url:
            sys.exit(f"{a.insee} n'a pas d'url dans le registre.")
        html = _restreindre(page(url, recette.get("rendu") == "navigateur"),
                            recette.get("dans"))
        trouves = actes_de_la_page(html, url)
        attendu = recette.get("attendu")
        origine = f"{a.registre} (recette)"

    actes = trouves
    souci = verdict_ecart(len(actes), int(attendu) if attendu else None)
    if souci and not a.forcer:
        sys.exit(f"ARRET : {souci}\nRien n'a ete ecrit. Faire re-verifier la page "
                 f"par l'agent ({url}), puis corriger la recette. "
                 "`--forcer` passe outre.")

    memoire = chemin_memoire(a.insee)
    if os.path.exists(memoire):
        print(f"memoire de cette collectivite : {memoire}", file=sys.stderr)
    else:
        print(f"aucune memoire pour {a.insee} : elle sera creee, a completer "
              "apres lecture.", file=sys.stderr)

    if a.a_blanc:
        print(f"{nom} ({a.insee}) : {len(actes)} acte(s), via {origine}")
        for x in actes:
            print(f"  {x['date'] or '    ?     '}  {x['titre'][:66]}")
        return

    con = db(a.db) if a.db else db()
    synchroniser_registre(con, a.insee, entree)
    source = entree.get("type") if entree.get("type") in SOURCES else "site"
    nouveaux, telecharges, echecs = enregistrer(con, a.insee, nom, actes,
                                                limite=a.limite, source=source)
    print(f"{nom} ({a.insee}) : {len(actes)} acte(s) sur la page, "
          f"{nouveaux} nouveau(x), {telecharges} PDF telecharge(s). "
          f"[{os.path.basename(origine)}]")
    if echecs:
        print(f"{len(echecs)} PDF injoignable(s), reference(s) sans copie archivee :",
              file=sys.stderr)
        for titre, genre, detail in echecs:
            print(f"  {titre[:58]} — {genre} {detail}", file=sys.stderr)
    if nouveaux:
        print("Les nouveaux actes restent a lire : statut 'brut' tant qu'un agent "
              "n'a pas ecrit leur synthese.")

    # Le passage se consigne toujours, meme sans agent pour le lire : c'est un
    # fait (date, comptes), pas un jugement. Si aucune analyse d'agent n'existe
    # encore malgre ce passage, le dire fort -- le skill exige cette memoire,
    # et rien d'autre que ce message ne rend son absence visible.
    if journaliser_passage(a.insee, len(actes), nouveaux, telecharges, len(echecs)):
        print(f"\nATTENTION : {memoire} ne contient toujours aucune analyse "
              "d'agent (impasses, pieges de qualification, structure des actes) "
              "malgre au moins un passage enregistre. Le skill l'exige a chaque "
              "collecte : la completer maintenant, voir le skill, recherche.md "
              "« La memoire ».", file=sys.stderr)

    # Rappel doux, pas un blocage : une collecte n'inscrit personne en suivi
    # actif toute seule (table `suivi`). Sans ce rappel, une commune juste
    # consultee une fois se confondrait avec une commune suivie des qu'elle a
    # des actes en base -- exactement ce que le skill s'interdit.
    if not lire_suivi(con).get(a.insee):
        print(f"\n{a.insee} n'est pas marquee en suivi actif (table `suivi`) : "
              "cette collecte reste une consultation ponctuelle. "
              f"`--suivi {a.insee}:on` l'y inscrit si un suivi regulier est voulu.",
              file=sys.stderr)


def _selftest():
    base = "https://exemple.fr/deliberations"
    html = """
    <nav><a href="/revues-municipales">Revues Municipales</a></nav>
    <div id="contenu">
      <a href="/f/PV+du+CM+DU+11022026+approuve.pdf"></a>
      <a href="/f/liste.pdf?Expires=1792587900&Signature=abc">Liste des
         d&eacute;lib&eacute;rations du 27 07 2026</a>
      <a href="/f/PV+Du+8042026+APPROUVE.pdf">PV</a>
      <a href="/f/PV+du+CM+DU+11022026+approuve.pdf">doublon</a>
      <a href="/page.html">Pas un PDF</a>
    </div>
    """
    actes = actes_de_la_page(html, base)
    assert len(actes) == 3, [a["fichier"] for a in actes]
    par_date = {a["date"] for a in actes}
    # Date lue dans le nom du fichier, jour sans zero compris.
    assert "2026-02-11" in par_date and "2026-04-08" in par_date, par_date
    # Date lue dans l'etiquette quand le nom de fichier n'en porte pas, et
    # surtout PAS dans le parametre Expires du CDN, qui donnerait 7452-37-89.
    assert "2026-07-27" in par_date, par_date
    # Un lien sans texte prend le nom de son fichier pour titre, les `+` de
    # l'URL rendus en espaces -- `unquote` ne les traduit pas, lui.
    muet = [a for a in actes if a["fichier"].startswith("PV+du+CM")][0]
    assert muet["titre"] == "PV du CM DU 11022026 approuve", muet["titre"]
    # Les entites HTML sont rendues, pas conservees telles quelles.
    liste = [a for a in actes if a["fichier"] == "liste.pdf"][0]
    assert liste["titre"] == "Liste des délibérations du 27 07 2026", liste["titre"]
    assert liste["url"].startswith("https://exemple.fr/f/liste.pdf?"), liste["url"]

    # Dates en toutes lettres, « 1er » compris ; rien d'invente sinon.
    assert date_fr("Séance du 1er juillet 2026") == "2026-07-01"
    assert date_fr("Conseil du 3 Décembre 2025") == "2025-12-03"
    assert date_fr("Bulletin municipal") is None
    # Formats vus sur des agglos : mois abrege colle, annee courte.
    assert date_fr("bureau 28fev2024 liste") == "2024-02-28"
    assert date_fr("Délibérations Bureau 31 janv 2024") == "2024-01-31"
    assert date_fr("Conseil 16 décembre 24") == "2024-12-16"
    assert date_fr("Conseil 25mars2024") == "2024-03-25"
    assert date_fr("CR-CC-27-JUILLET-2020") == "2020-07-27"
    # Un numero d'acte colle a l'annee n'est pas une date (CC Pays de Mormal).
    mormal = actes_de_la_page('<a href="/f/124_2025-Approbation-du-pv-cc-151025.pdf">'
                              'Approbation du procès verbal du 15 octobre 2025 En savoir plus</a>', base)
    assert mormal[0]["date"] == "2025-10-15", mormal
    assert mormal[0]["titre"] == "Approbation du procès verbal du 15 octobre 2025", mormal
    assert date_num("PV-du-08.04.26-tampon") == "2026-04-08"
    assert date_num("01_cr cm 26_05_20") == "2020-05-26"
    assert date_num("Deliberation 123456") is None
    assert date_num("31 02 2026") is None              # 31 fevrier : refuse
    assert date_num("Delib.-N°-26.06.29.01-Approbation-CFU") is None   # numerotation
    assert date_num("Delib.-N°-25.03.03.11-Convention") is None
    assert date_num("PV du 12.03.2099") is None        # seance dans 70 ans : refusee
    # Annee en tete, et identifiant @CTES ; un horodatage de 14 chiffres n'en est pas une.
    assert date_num("20260303_ListeDeliberations") == "2026-03-03"
    assert date_num("Compte-rendu-CA-2026-06-24") == "2026-06-24"
    assert date_num("99_bu-038-213802960-20240213-ca_2023-bf-1-1") == "2024-02-13"
    assert date_num("pv CM-29062026101022") is None
    # Un PDF servi par un script : nomme dans la query, `&amp;` decode, et
    # chaque `idtf` est un acte distinct malgre le chemin commun.
    servis = actes_de_la_page(
        '<a href="/cms_viewFile.php?idtf=6993&amp;path=Liste-CC.pdf">27 janvier 2026</a>'
        '<a href="/cms_viewFile.php?idtf=7114&amp;path=20260303_Liste.pdf">03 mars 2026</a>'
        '<a href="/cms_viewFile.php?idtf=7114&amp;path=20260303_Liste.pdf">doublon</a>'
        '<a href="/index.php?page=contact">Contact</a>', base)
    assert [(a["fichier"], a["date"]) for a in servis] == [
        ("Liste-CC.pdf", "2026-01-27"), ("20260303_Liste.pdf", "2026-03-03")], servis
    assert servis[0]["url"] == "https://exemple.fr/cms_viewFile.php?idtf=6993&path=Liste-CC.pdf"
    tri = [{"titre": t, "fichier": f} for t, f in (
        ("Convocation CM 08 04 26", "c.pdf"), ("ODJ CM 2026-04-08", "o.pdf"),
        ("Ordre du jour", "x.pdf"), ("Liste", "cm-odj-12.pdf"),
        ("Procès-verbal du 8 avril", "pv.pdf"), ("Liste des délibérations", "liste.pdf"),
        ("Budget : Méthode de calcul", "odjective.pdf"))]
    assert [a["titre"] for a in sans_convocations(tri)] == [
        "Procès-verbal du 8 avril", "Liste des délibérations", "Budget : Méthode de calcul"], tri
    contradiction = actes_de_la_page('<a href="/2026-02-01-refacturation.pdf">'
                                     'délibération-20260205-01</a>', base)
    assert contradiction[0]["date"] is None, contradiction
    # PDF declares hors lien ; un PDF a la fois lie et embarque ne compte qu'une fois.
    embarques = actes_de_la_page(
        '<div class="_df_book" source="/up/PV-CM-12-03-2026.pdf"></div>'
        '<embed src="/up/liste_du_12_03_2026.pdf" type="application/pdf">'
        '<a href="/up/PV-CM-12-03-2026.pdf">PV du 12 mars</a><img src="/logo.png">', base)
    assert [(a["fichier"], a["titre"]) for a in embarques] == [
        ("PV-CM-12-03-2026.pdf", "PV du 12 mars"), ("liste_du_12_03_2026.pdf", "liste du 12 03 2026")], embarques
    taille = actes_de_la_page('<a href="/f/a.pdf">Procès verbal (pdf - 2.13 Mo)</a>', base)
    assert taille[0]["titre"] == "Procès verbal", taille
    poids = actes_de_la_page('<a href="/a.pdf">Compte-rendu du 17/09/2026 (967 Ko)</a>'
                             '<a href="/PV_du_2_mai_2026.pdf">Télécharger la version pdf</a>', base)
    assert [x["titre"] for x in poids] == ["Compte-rendu du 17/09/2026", "PV du 2 mai 2026"], poids
    # Un bouton « Consulter » n'est pas un titre ; la date vit alors dans le fichier.
    bouton = actes_de_la_page('<a href="/f/Compte_rendu_du_22_mars_2026.pdf">Consulter</a>', base)
    assert bouton[0]["titre"] == "Compte rendu du 22 mars 2026", bouton
    assert bouton[0]["date"] == "2026-03-22", bouton

    # Restreindre a un conteneur ecarte le menu place avant.
    assert "revues-municipales" not in _restreindre(html, "#contenu")
    assert "revues-municipales" in _restreindre(html, None)

    # Le garde-fou : une page refaite ne doit pas passer pour une page vide.
    assert verdict_ecart(17, 17) is None
    assert verdict_ecart(19, 17) is None          # une seance de plus, normal
    assert verdict_ecart(0, 17) is not None       # page refaite
    assert verdict_ecart(3, 17) is not None       # effondrement
    assert verdict_ecart(0, None) is None         # sans attendu, on ne juge pas
    assert verdict_ecart(1, 2) is None            # trop peu d'actes pour juger

    # Lecture du registre, sans dependance YAML.
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as f:
        f.write("\n".join((
            "# commentaire",
            "collectivites:",
            '  "13083":',
            '    nom: "Rognonas"',
            "    type: site",
            '    url: "https://exemple.fr/d"',
            "    notes: >",
            "      Corpus clos depuis mai 2022.",
            "      Les actes courants sont ailleurs.",
            "    recette:",
            "      rendu: http",
            "      attendu: 17",
            '  "99001":',
            '    nom: "Autre"',
            "")))
        chemin = f.name
    try:
        r = recettes(chemin)
        assert set(r) == {"13083", "99001"}, list(r)
        assert r["13083"]["nom"] == "Rognonas"
        assert r["13083"]["recette"] == {"rendu": "http", "attendu": "17"}
        assert r["99001"].get("recette") is None
        # Un bloc `>` doit etre lu en entier, pas rendu comme « > ». C'est la
        # que vit ce qu'un agent doit savoir avant de conclure « rien de neuf ».
        assert r["13083"]["notes"] == (
            "Corpus clos depuis mai 2022. Les actes courants sont ailleurs."
        ), repr(r["13083"]["notes"])
        # Et la cle qui suit le bloc doit rester lisible.
        assert r["13083"]["recette"]["attendu"] == "17"
    finally:
        os.unlink(chemin)
    # `--limite` borne les telechargements, jamais le referencement.
    import tempfile as _tmp

    class _Faux:
        total_changes = 0
        def execute(self, *a, **k): return self
        def fetchone(self): return {"id": 1, "p": None, "d": None}
        def commit(self): pass
    faux = [{"titre": f"a{i}", "fichier": f"{i}.pdf", "date": f"2026-0{i}-01",
             "url": f"https://x/{i}.pdf"} for i in (1, 2, 3)]
    vus = []
    global _telecharger, PDF_DIR
    vrai_telecharger, vrai_pdf_dir = _telecharger, PDF_DIR

    def _sans_reseau(url, chemin):
        vus.append(url)
        open(chemin, "wb").close()

    _telecharger = _sans_reseau
    PDF_DIR = _tmp.mkdtemp(prefix="ft_pdf_")
    try:
        _, n, echecs = enregistrer(_Faux(), "99001", "Bourg", faux, limite=2)
        assert n == 2 and echecs == [], (n, echecs)
        # Les deux plus recents, pas les deux premiers de la liste.
        assert sorted(u[-5] for u in vus) == ["2", "3"], vus

        # Un lien mort est signale et n'interrompt pas les autres.
        def _un_sur_deux(url, chemin):
            if url.endswith("2.pdf"):
                raise OSError("404")
            open(chemin, "wb").close()
        _telecharger = _un_sur_deux
        PDF_DIR = _tmp.mkdtemp(prefix="ft_pdf2_")
        _, n, echecs = enregistrer(_Faux(), "99001", "Bourg", faux)
        assert n == 2, n
        assert len(echecs) == 1 and echecs[0][1] == "OSError", echecs
    finally:
        _telecharger = vrai_telecharger
        import shutil
        shutil.rmtree(PDF_DIR, ignore_errors=True)
        PDF_DIR = vrai_pdf_dir

    # Un collecteur dedie est charge depuis data/collecteurs/, prime sur la
    # recette, et doit exposer actes(). Verifie sur un dossier jetable.
    global COLLECTEURS
    vrai = COLLECTEURS
    COLLECTEURS = _tmp.mkdtemp(prefix="ft_coll_")
    try:
        assert charger_collecteur("99001") is None
        with open(chemin_collecteur("99001"), "w", encoding="utf-8") as f:
            f.write("\n".join((
                "ATTENDU = 2",
                "def actes(ctx):",
                "    return [{'titre': ctx['nom'], 'fichier': 'a.pdf',",
                "             'date': None, 'url': 'https://x/a.pdf'}]",
            )))
        m = charger_collecteur("99001")
        assert m.ATTENDU == 2
        assert m.actes({"nom": "Bourg"})[0]["titre"] == "Bourg"
        # Un collecteur qui n'expose pas actes() doit etre refuse, pas ignore.
        with open(chemin_collecteur("99002"), "w", encoding="utf-8") as f:
            f.write("ATTENDU = 1\n")
        try:
            charger_collecteur("99002")
            raise AssertionError("un collecteur sans actes() a ete accepte")
        except SystemExit:
            pass
    finally:
        import shutil
        shutil.rmtree(COLLECTEURS, ignore_errors=True)
        COLLECTEURS = vrai

    # Le journal se cree tout seul, meme sans memoire prealable, et signale
    # l'absence d'analyse d'agent -- c'est la partie que le skill peut faire
    # respecter sans compter sur personne pour lire une instruction.
    global MEMOIRE
    vrai_memoire = MEMOIRE
    MEMOIRE = os.path.join(_tmp.mkdtemp(prefix="ft_mem_"), "memoire")  # absent, comme au clone
    try:
        vide = journaliser_passage("99001", 17, 3, 2, 1)
        assert vide is False, "premier passage : la memoire s'ecrit apres la lecture, pas d'alerte"
        assert "(UTC" in open(chemin_memoire("99001"), encoding="utf-8").read(), "decalage affiche"
        texte = open(chemin_memoire("99001"), encoding="utf-8").read()
        assert MARQUEUR_JOURNAL in texte
        assert "3 nouveau(x)" in texte and "1 echec(s)" in texte

        # Un deuxieme passage s'empile au-dessus du premier (le plus recent en
        # tete), sans effacer le journal existant.
        vide2 = journaliser_passage("99001", 18, 1, 1, 0)
        assert vide2 is True, "deuxieme passage sans memoire redigee : alerte"
        texte = open(chemin_memoire("99001"), encoding="utf-8").read()
        assert texte.count("acte(s) vu(s)") == 2

        # Des qu'un agent a ecrit une section narrative, l'alerte s'eteint,
        # meme si le journal continue de s'empiler au-dessus.
        with open(chemin_memoire("99001"), "a", encoding="utf-8") as f:
            f.write("\n## Ce qui a été essayé\n\nDéjà exploré : rien à signaler.\n")
        vide3 = journaliser_passage("99001", 18, 0, 0, 0)
        assert vide3 is False, "une analyse existe, plus d'alerte a emettre"
        for _ in range(JOURNAL_MAX + 3):
            journaliser_passage("99001", 18, 0, 0, 0)
        texte = open(chemin_memoire("99001"), encoding="utf-8").read()
        assert texte.count("acte(s) vu(s)") == JOURNAL_MAX, "journal plafonne"
        assert "Déjà exploré : rien à signaler." in texte, "la note de l'agent survit"
    finally:
        import shutil
        shutil.rmtree(MEMOIRE, ignore_errors=True)
        MEMOIRE = vrai_memoire

    # Table `suivi` : vide -> {} ; ecrire_suivi() est ce qui fait la
    # difference entre "jamais suivie" et "suivie puis retiree" (false
    # explicite, pas une absence qu'on pourrait confondre avec "jamais
    # regardee").
    dossier_suivi = _tmp.mkdtemp(prefix="ft_suivi_")
    con = db(os.path.join(dossier_suivi, "t.db"))
    try:
        assert lire_suivi(con) == {}
        ecrire_suivi(con, "59350", True)
        assert lire_suivi(con) == {"59350": True}
        ecrire_suivi(con, "84035", False)
        assert lire_suivi(con) == {"59350": True, "84035": False}
        # Retirer une collectivite du suivi laisse une trace explicite
        # (false), pas une ligne effacee : la distinction avec "jamais
        # regardee" doit rester lisible en base.
        ecrire_suivi(con, "59350", False)
        assert lire_suivi(con) == {"59350": False, "84035": False}
        # --etat : une collectivite suivie sans collecteur se voit.
        ecrire_suivi(con, "99009", True)
        ligne = [l for l in etat(con, {}) if l["code"] == "99009"][0]
        assert ligne["suivi"] and not ligne["collecteur"] and ligne["actes"] == 0, ligne

        # Le registre est recopie en base : le yaml fait seul autorite.
        synchroniser_registre(con, "99001", {
            "nom": "Bourg", "type": "portail", "url": "https://x.fr",
            "verifie_le": "2026-09-01", "notes": "Béthune accentué",
            "epci_siren": "900000001", "epci_nom": "Agglo"})
        p = con.execute("SELECT type, notes FROM portails WHERE insee='99001'").fetchone()
        assert (p["type"], p["notes"]) == ("portail", "Béthune accentué"), dict(p)
        assert con.execute("SELECT epci_siren FROM appartenances_epci "
                           "WHERE insee='99001'").fetchone()[0] == "900000001"

        # Un portail garde sa source et ses metadonnees ; le chemin archive est
        # relatif, et un second passage ne relit pas le PDF deja note.
        vrai_pdf_dir, vrai_tel = PDF_DIR, _telecharger
        PDF_DIR = _tmp.mkdtemp(prefix="ft_pdf3_")
        _telecharger = lambda url, chemin: open(chemin, "wb").close()  # noqa: E731
        try:
            acte = [{"titre": "Budget", "fichier": "b.pdf", "date": "2026-03-01",
                     "url": "https://x/b.pdf", "numero": "26/1", "rapporteur": "Mme X",
                     "doc_id": "4412"}]
            assert enregistrer(con, "99001", "Bourg", acte, source="portail")[:2] == (1, 1)
            d = con.execute("SELECT d.source, d.numero, d.rapporteur, s.source s "
                            "FROM deliberations d JOIN seances s ON s.id=d.seance_id "
                            "WHERE d.doc_id_source='4412'").fetchone()
            assert tuple(d) == ("portail", "26/1", "Mme X", "portail"), tuple(d)
            assert enregistrer(con, "99001", "Bourg", acte, source="portail")[:2] == (0, 0)

            # Meme nom, deux dossiers : deux actes, pas un qui ecrase l'autre.
            deux = actes_de_la_page('<a href="/2023/pv.pdf">PV 2023</a>'
                                    '<a href="/2026/pv.pdf">PV 2026</a>'
                                    '<a href="/2026/pv.pdf">doublon</a>', "https://x.fr/")
            assert len(deux) == 2, deux
            assert enregistrer(con, "99003", "Hameau", deux)[:2] == (2, 2)
            # Le lien signe d'un CDN change a chaque passage : meme acte.
            signe = [dict(deux[0], url="https://cdn.x.fr/2023/pv.pdf?Expires=9&Signature=z")]
            assert enregistrer(con, "99003", "Hameau", signe)[:2] == (0, 0)
            # Meme adresse, autre seance : le fichier a ete ecrase par le site.
            # Nouvelle ligne et nouvelle copie ; l'ancienne garde sa preuve.
            liste = {"titre": "Liste", "fichier": "liste.pdf", "url": "https://x.fr/u/liste.pdf"}
            assert enregistrer(con, "99003", "Hameau", [dict(liste, date="2026-06-30")])[:2] == (1, 1)
            assert enregistrer(con, "99003", "Hameau", [dict(liste, date="2026-09-22")])[:2] == (1, 1)
            assert enregistrer(con, "99003", "Hameau", [dict(liste, date="2026-09-22")])[:2] == (0, 0)
            vu = [tuple(r) for r in con.execute(
                "SELECT s.date_seance, d.pdf_chemin_local IS NOT NULL FROM deliberations d "
                "JOIN seances s ON s.id=d.seance_id WHERE d.titre='Liste' ORDER BY 1")]
            assert vu == [("2026-06-30", 1), ("2026-09-22", 1)], vu
        finally:
            shutil.rmtree(PDF_DIR, ignore_errors=True)
            PDF_DIR, _telecharger = vrai_pdf_dir, vrai_tel
    finally:
        con.close()
        import shutil
        shutil.rmtree(dossier_suivi, ignore_errors=True)

    # Adaptateurs de plateformes, sans reseau : page() rend des reponses figees.
    global page
    vraie_page = page
    import json
    reponses = {
        "/folders": [json.dumps([{"id": "ACTES", "children": [
            {"id": 951, "name": "Délibérations"}, {"id": 953, "name": "Arrêtés"}]}])],
        "publiact.fr": [json.dumps({"count": 2, "rows": [
            {"id": 11, "namePublic": "PV 30.06.2026.pdf"}, {"id": 12, "namePublic": "Liste.pdf"}]})],
        "megalis": [json.dumps({"nb_resultats": 3, "page_suivante": "p2", "resultats": [
                        {"id": "a", "objet": "Budget  primitif", "date_acte": "2026-03-04T00:00:00Z",
                         "url": "https://m/x/1.pdf", "annexes": [{"url": "https://m/x/an.pdf"}]}]}),
                    json.dumps({"nb_resultats": 3, "page_suivante": None, "resultats": [
                        {"id": "a", "objet": "Budget primitif", "date_acte": "2026-03-04T00:00:00Z",
                         "url": "https://m/x/1.pdf", "annexes": []},
                        {"id": "b", "objet": "Subvention", "date_acte": None,
                         "url": "https://m/x/2.pdf", "annexes": []}]})],
        "id=racine": ['<div><a href="https://drive.google.com/drive/folders/sous1"><div '
                      'class="flip-entry-title">2026</div></a><a href="https://drive.google.com/'
                      'file/d/F1/view"><div class="flip-entry-title">PV CM 08.04.26.pdf</div></a>'
                      '<a href="https://drive.google.com/file/d/F9/view"><div '
                      'class="flip-entry-title">photo.jpg</div></a></div>'],
        "id=sous1": ['<a href="https://drive.google.com/file/d/F2/view"><div '
                     'class="flip-entry-title">Liste d&#39;actes.pdf</div></a>'],
    }
    vus_publiact = []

    def _fige(url, navigateur=False):
        if "publiact" in url:
            vus_publiact.append(url)
        return next(v for k, v in reponses.items() if k in url).pop(0)
    page = _fige
    try:
        p = publiact("uid")
        assert "folderIds%5D%5B0%5D=951" in vus_publiact[-1] and "953" not in vus_publiact[-1], vus_publiact
        assert [(a["doc_id"], a["date"], a["titre"]) for a in p] == [
            ("publiact-11", "2026-06-30", "PV 30.06.2026"), ("publiact-12", None, "Liste")], p
        assert p[0]["url"].endswith("/documents/11/download/inline")
        m = megalis("200085876")
        assert [(a["doc_id"], a["date"], a["titre"]) for a in m] == [
            ("megalis-a", "2026-03-04", "Budget primitif"), ("megalis-b", None, "Subvention")], m
        d = drive("racine")
        assert [(a["doc_id"], a["date"], a["titre"]) for a in d] == [
            ("drive-F1", "2026-04-08", "PV CM 08.04.26"), ("drive-F2", None, "Liste d'actes")], d
    finally:
        page = vraie_page

    # LegalView : seuls les themes « conseil » et leurs enfants ; date de la
    # seance tiree du theme ; `filePath` avec ou sans `/` initial.
    arbre = {"themes": [
        {"_id": "cm", "name": "Conseil Municipal", "children": [
            {"_id": "s1", "name": "Conseil municipal 28/09/2026", "children": []}]},
        {"_id": "ar", "name": "Arrêtés", "children": []}]}
    docs = {"cm": [], "s1": [{"_id": "d1", "title": "Liste  délibérations",
                              "filePath": "/uploads/x/1-liste.pdf"},
                             {"_id": "d2", "title": "PV", "filePath": "uploads/x/2-pv.pdf"}]}
    vus_lv = []

    def _faux_lv(url, navigateur=False):
        vus_lv.append(url.rsplit("/", 1)[-1])
        if url.endswith("themes-tree"):
            return json.dumps(arbre)
        theme = url.rsplit("/theme/", 1)[1].split("?")[0]
        return json.dumps({"documents": docs[theme], "pagination": {"hasMore": False}})
    page = _faux_lv
    try:
        lv = legalview("https://www.saas-legalview.fr/public/legalview/mairie-x")
        assert [(a["doc_id"], a["titre"], a["date"], a["url"]) for a in lv] == [
            ("legalview-d1", "Liste délibérations", "2026-09-28",
             "https://www.saas-legalview.fr/api/uploads/x/1-liste.pdf"),
            ("legalview-d2", "PV", "2026-09-28", "https://www.saas-legalview.fr/api/uploads/x/2-pv.pdf")], lv
        assert not any(v.startswith("ar") for v in vus_lv), vus_lv     # arretes non lus
    finally:
        page = vraie_page

    # Opendatasoft : champs reconnus par leur role, date de prefecture ecartee,
    # enregistrement sans PDF ignore, desaccord champ/titre -> pas de date.
    lignes_ods = [
        {"delib_num": 26130, "delib_date": 21032026, "pref_date": 24032026,
         "delib_objet": "FIXATION NOMBRE ADJOINTS",
         "fichier": {"id": "f1", "filename": "26_1_30.pdf", "format": "pdf", "url": "https://o/f1"}},
        {"titre": "CR CONSEIL 26_05_20", "date": "27_05_20",
         "fichier": {"id": "f2", "filename": "cr.pdf", "format": "pdf", "url": "https://o/f2"}},
        {"titre": "Sans piece jointe", "date": "2026-01-01"}]
    page = lambda url, navigateur=False: json.dumps(lignes_ods)  # noqa: E731
    try:
        o = opendatasoft("cachan.opendatasoft.com", "deliberations-2026")
        assert [(a["doc_id"], a["titre"], a["date"], a["numero"]) for a in o] == [
            ("ods-f1", "FIXATION NOMBRE ADJOINTS", "2026-03-21", "26130"),
            ("ods-f2", "CR CONSEIL 26_05_20", None, None)], o
    finally:
        page = vraie_page

    # DematDoc : premiere page, suite paresseuse, archives ; date d'acte et non
    # date d'affichage ; version biffee preferee.
    global _post_json
    vrai_post, appels = _post_json, []

    def _doc(i, **valeurs):
        return {"id": i, "name": f"Délibération DEL{i} du 2026-01-0{i}", "path": f"/repository/{i}.pdf",
                "bifferPath": "/repository/b2.pdf" if i == 2 else None,
                "values": {k: {"displayValue": x} for k, x in valeurs.items()}}

    def _faux_post(url, donnees):
        appels.append(url.rsplit("/api/public/", 1)[-1])
        if url.endswith("lazy"):
            return {"documents": [_doc(2, OBJET="Budget", DATEACTE="2026-02-03")], "nextDocsIds": []}
        if donnees["filters"]["params"]["archive"]:
            return {"documents": [_doc(3)], "nextDocsIds": []}
        return {"documents": [_doc(1, OBJET="Tarifs", NUMEROACTE="DEL1", DATEACTE="2026-01-15",
                                   CI_DATE_DEBUT_AFFICHAGE_PUBLIC="2026-01-20")], "nextDocsIds": [2]}
    _post_json = _faux_post
    try:
        d = dematdoc("https://dax.dematdoc.eu/public/14?filters=14|121|D%C3%A9lib%C3%A9ration")
        assert [(a["doc_id"], a["titre"], a["date"], a["numero"]) for a in d] == [
            ("dematdoc-1", "Tarifs", "2026-01-15", "DEL1"),
            ("dematdoc-2", "Budget", "2026-02-03", None),
            ("dematdoc-3", "Délibération DEL3 du 2026-01-03", "2026-01-03", None)], d
        assert d[1]["url"] == "https://dax.dematdoc.eu/repository/b2.pdf", d[1]
        assert appels == ["get-documents/14", "get-documents-lazy", "get-documents/14"], appels
    finally:
        _post_json = vrai_post

    # Couche reseau. Adresse avec accents et espaces encodee, sans double encodage.
    assert _uri("https://x.fr/pyrénées/Liste des actes.pdf") == \
        "https://x.fr/pyr%C3%A9n%C3%A9es/Liste%20des%20actes.pdf"
    assert _uri("https://x.fr/a%20b.pdf?x=1&y=2") == "https://x.fr/a%20b.pdf?x=1&y=2"
    # Un octet fautif ne fait pas relire toute la page en latin-1.
    tronque = "Prévention ".encode() + b"\xf0\x9f" + "Remise des clés".encode()
    assert "Prévention" in _decoder(tronque, "utf-8") and "clés" in _decoder(tronque)
    assert _decoder("café".encode("cp1252")) == "café"
    # 429 : on attend ce que le serveur demande, puis on reessaie.
    import email.message
    vrai_urlopen, vrai_sleep, attentes, refus = urllib.request.urlopen, time.sleep, [], [1, 1]

    def _trop_vite(req, timeout=None, context=None):
        if refus:
            refus.pop()
            entetes = email.message.Message()
            entetes["Retry-After"] = "2"
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many", entetes, None)
        return "reponse"
    urllib.request.urlopen, time.sleep = _trop_vite, attentes.append
    try:
        assert _ouvrir("https://x.fr/") == "reponse"
        assert attentes == [PAUSE, 2, PAUSE, 2, PAUSE], attentes
        attentes.clear()

        def _absent(req, timeout=None, context=None):
            raise urllib.error.HTTPError(req.full_url, 404, "Absent", email.message.Message(), None)
        urllib.request.urlopen = _absent
        try:
            _ouvrir("https://x.fr/")
            raise AssertionError("un 404 a ete reessaye")
        except urllib.error.HTTPError:
            assert attentes == [PAUSE], attentes
    finally:
        urllib.request.urlopen, time.sleep = vrai_urlopen, vrai_sleep

    # Une page d'erreur servie en 200 n'est pas archivee comme un PDF.
    dossier = _tmp.mkdtemp(prefix="ft_dl_")
    try:
        for nom, octets in (("ok.bin", b"%PDF-1.7 ..."), ("ko.bin", b"<html>404</html>")):
            with open(os.path.join(dossier, nom), "wb") as f:
                f.write(octets)
        source = urllib.parse.urljoin("file:", urllib.request.pathname2url(dossier)) + "/"
        _telecharger(source + "ok.bin", os.path.join(dossier, "ok.pdf"))
        assert os.path.exists(os.path.join(dossier, "ok.pdf"))
        try:
            _telecharger(source + "ko.bin", os.path.join(dossier, "ko.pdf"))
            raise AssertionError("une page HTML a ete archivee comme PDF")
        except ValueError:
            pass
        assert not os.path.exists(os.path.join(dossier, "ko.pdf"))
        assert not os.path.exists(os.path.join(dossier, "ko.pdf.part"))
    finally:
        shutil.rmtree(dossier, ignore_errors=True)

    print("selftest ok")


if __name__ == "__main__":
    sortie_utf8()
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
