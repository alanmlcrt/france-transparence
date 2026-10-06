# Trouver où une collectivité publie, et ne plus avoir à le refaire

Ne sert qu'à une collectivité inconnue, au registre sans collecteur, ou dont
le collecteur a signalé un effondrement. Lire d'abord sa mémoire
(`collecter.py --memoire <code>`) si elle existe.

## Le site officiel

```bash
curl -s 'https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration/records?limit=10&select=nom,site_internet,adresse_courriel&where=code_insee_commune%3D%22<insee>%22%20and%20nom%20like%20%22Mairie%22'
```

Filtrer sur la fiche **« Mairie »** (`nom like "Mairie"`, comme ci-dessus) :
sans ce filtre, l'annuaire mêle les fiches de la gendarmerie, du CCAS, de
France Travail ou de l'Urssaf, et l'on prend vite leur site pour celui de la
commune (constaté pour Mende et Tours, dont la fiche « Mairie » donnait
pourtant `mende.fr` et `tours.fr`). Pour un EPCI, chercher `siren="<siren>"`.

Si la fiche « Mairie » n'a pas de `site_internet` :

- le domaine de son `adresse_courriel` est une piste (`mairie@gaillac-toulza.fr`),
  pas une preuve : souvent il ne sert que le courrier. L'ouvrir avant d'y croire ;
- le site de l'**EPCI** publie parfois les actes de ses communes (rubrique
  « publication des actes communaux ») ;
- sinon chercher sur le web. Les premiers résultats sont souvent des
  **agrégateurs** (politique.pappers.fr, collectivite.fr, la-mairie.com) : ils
  republient des copies, ce ne sont pas des sources ; on n'y collecte rien.

Un village sans site ni EPCI qui publie pour lui n'affiche ses actes qu'en
mairie, sur papier. C'est une réponse, pas un échec : le dire, et le noter
dans la mémoire. Dans les échantillons tirés au hasard, c'était le cas
d'environ un village sur deux.

Ne garder qu'un domaine **au nom de la collectivité lui-même** (`tours.fr`,
`ville-tours.fr`), pas un domaine qui le contient pour un autre organisme
(`gretaformation.ac-orleans-tours.fr` n'est pas Tours). Un certificat TLS
émis pour un autre domaine donne le bon ; ne jamais désactiver la
vérification.

## La page des actes : au navigateur, jamais en `curl`

La **page** d'un site s'explore au navigateur. L'**API JSON** d'une plateforme
déjà repérée au navigateur, elle, se lit en GET (`curl` ou `page()`) : c'est
ce que font ses adaptateurs.

Beaucoup de sites (intercommunalités surtout) rendent leur navigation en
JavaScript : en HTTP simple, la page est vide de liens et la collecte conclut
à tort qu'il n'y a rien. Le skill `agent-browser`, s'il est disponible, évite
d'écrire un script ; sinon Playwright (`requirements.txt`) :

```python
# scratch_recherche.py — jetable
import sys
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding="utf-8")   # console Windows : « DÉMARCHES », pas « D�MARCHES »
with sync_playwright() as p:
    nav = p.chromium.launch()
    page = nav.new_page(user_agent="france-transparence (lecture seule)")
    page.goto("<url>", wait_until="networkidle")
    for a in page.query_selector_all("a"):
        if href := a.get_attribute("href"):
            print(f"{(a.inner_text() or '').strip()[:70]} -> {href}")
    nav.close()
```

Chercher, dans l'ordre : un lien vers délibérations, comptes rendus,
procès-verbaux, actes ou séances du conseil ; sinon le moteur de recherche du
site ; sinon `/deliberations`, `/conseil-municipal`, `/comptes-rendus`.
Un site qui ne liste ses actes que par un moteur de recherche se lit si ses
résultats répondent à une **URL GET** (paramètres dans l'adresse, comme un
lien) ; un formulaire qui n'accepte que l'envoi (POST) ne se soumet pas
depuis le navigateur. Seule exception : les adaptateurs de plateforme de
`collecter.py` (tableau ci-dessous), relus et limités à une recherche sans
effet.
**Lire la page, pas seulement filtrer ses liens** : « Bulletin municipal »
n'est pas une délibération, « Actes réglementaires » peut en être une, et les
procès-verbaux d'un conseil de quartier, des jeunes ou des aînés ne sont pas
ceux du conseil municipal.

Le site officiel renvoie souvent vers **un autre domaine de la même
collectivité** pour ses actes (`coray.fr` → `coray.bzh`,
`chateaugontier.fr` → `paysdechateaugontier.fr`) : le suivre, c'est la même
source. Un domaine tiers (prestataire, journal local) n'en est pas une.

**Quand le site résiste.** `collecter.py` attend lui-même quand un serveur
répond 429 (trop de requêtes) et complète une chaîne de certificats
incomplète, sans jamais désactiver la vérification. Si Python ne peut
toujours pas vérifier le certificat (racine trop récente pour son magasin),
`page()` relit la page au navigateur, qui la vérifie avec le sien ; les PDF de
ce site échouent alors au téléchargement et restent « pas téléchargés » : le
noter dans la mémoire. Un 429 qui persiste après ces attentes veut dire
« revenir plus tard » : arrêter ce site pour la session, explorer moins large
la fois suivante (quelques pages ciblées, pas un parcours de trente). Une page « nous vérifions
que vous n'êtes pas un robot » (protection anti-DDoS, souvent en 403 ou 418 :
constaté à Chinon et à Meaux)
**ne se contourne pas** : ni autre user-agent, ni navigateur maquillé. Chercher
la même source ailleurs (plateforme de publication, Mégalis, site de l'EPCI),
sinon le consigner dans la mémoire et le dire à l'utilisateur.

Une page vide d'actes ne veut pas dire « rien de publié ». Trois formes
reviennent d'une collectivité à l'autre :

- **Les actes un ou deux niveaux plus bas** : une page par année ou par
  séance (« Année 2026 », « Séance du 22 juin »). Le collecteur parcourt ces
  sous-pages.
- **Une plateforme de publication**, souvent en iframe : la page hôte n'a
  aucun lien, tout vit dans le cadre ou derrière un lien sortant. Lire
  l'adresse du cadre (`<iframe src>`, ou `page.frames` sous Playwright).
  `collecter.py` sait déjà lire les plateformes rencontrées, et le collecteur
  tient alors en une ligne (`return megalis("<siren>")`) :

  | Signe sur la page | Fonction | Ce qu'on obtient |
  |---|---|---|
  | iframe `publiact.fr/i/<uid>/1` | `publiact("<uid>")` | PDF, date lue dans le nom |
  | iframe `data.megalis.bretagne.bzh/?siren=<siren>` | `megalis("<siren>")` | délibérations avec **date de décision** : `type: portail` |
  | | | `publiact` ne lit par défaut que les dossiers « délibérations », « conseil », « procès-verbaux », « comptes rendus » (`dossiers=None` : tout) |
  | lien `drive.google.com/drive/folders/<id>` | `drive("<id>")` | PDF du dossier et de ses sous-dossiers |
  | lien `<ville>.dematdoc.eu/public/<n>?filters=…` | `dematdoc("<url complète>")` | actes avec **date de l'acte** et numéro : `type: portail` |
  | lien `www.saas-legalview.fr/public/legalview/<org>` | `legalview("<url>")` | thèmes « conseil », datés par leur séance |
  | portail open data `<ville>.opendatasoft.com`, `data.<ville>.fr` | `opendatasoft("<domaine>", "<jeu>")` | un jeu par série (`deliberations-2026`) : objet, numéro, **date de délibération** |

  Un portail **open data** se repère à un lien « données ouvertes » ou à un
  domaine `opendatasoft` ; ses jeux se listent par
  `https://<domaine>/api/explore/v2.1/catalog/datasets?select=dataset_id&limit=100`,
  et ceux qui nomment des délibérations ou procès-verbaux sont les bons (un
  jeu par année : un collecteur peut les enchaîner).
  Pour DematDoc, passer l'URL **avec son filtre** (`filters=…|Délibération
  Conseil municipal`) : sans lui, arrêtés et convocations arrivent avec les
  délibérations. Une plateforme nouvelle mérite sa fonction à côté des autres
  plutôt qu'un collecteur qui la redécouvre : d'autres collectivités
  l'utilisent. Si elle n'est lisible qu'en envoyant autre chose qu'une
  recherche (connexion, captcha, formulaire de demande — Oxyad,
  `publication.oxyadsaas.fr`, n'ouvre que sur un écran de connexion), elle
  ne se lit pas :
  le noter dans la mémoire et le dire à l'utilisateur.
- **Un script qui sert les PDF** (`/cms_viewFile.php?idtf=…&path=x.pdf`,
  `download.php?file=…`) : `actes_de_la_page` les reconnaît tant que le nom du
  PDF figure dans l'adresse. Elle reconnaît aussi les PDF déclarés hors lien
  (visionneuse `source="…pdf"`, `<embed>`, `<iframe src="…pdf">`).
- **Une page vide** : la rubrique existe mais rien n'y est publié (constaté sur
  une communauté de communes). Le dire, plutôt que conclure à un défaut de
  collecte.

## Le registre : `data/portails.yaml`

**Seulement une fois qu'on a vu des actes sur la page.** Une adresse supposée
est une source qui n'existe pas. `collecter.py` recopie cette entrée en base
(`portails`, `appartenances_epci`) à chaque passage : ne rien écrire en SQL.

```yaml
collectivites:
  "<code>":
    nom: "<Nom officiel>"
    type: site              # ou portail
    url: "<page qui liste les actes>"
    verifie_le: "AAAA-MM-JJ"
    epci_siren: "<SIREN>"   # commune seulement, depuis geo.api (champ epci)
    epci_nom: "<Nom de l'EPCI>"
    notes: >
      Ce qu'on y trouve et ce qu'on n'y trouve pas.
    collecteur: data/collecteurs/<code>.py
```

- **`portail`** : portail de délibérations dédié ; actes numérotés et **datés
  de leur vraie séance**, souvent avec service, direction et rapporteur.
- **`site`** : page du site officiel ou plateforme sans numéro d'acte ; le
  PDF et son intitulé, la date quand elle se lit. Aucune date de séance n'est
  inventée : sans date lisible, `date: None`.

Le critère est le **numéro d'acte** publié avec une vraie date de séance :
Mégalis, DematDoc et Opendatasoft le donnent (`portail`) ; Publiact,
LegalView, Drive et une page de site non (`site`), même quand la date de
séance se lit. Le dashboard affiche la date dans les deux cas.

Une **`recette`** (`rendu`, `dans`, `attendu`, voir l'en-tête du fichier)
suffit pour une page qui se lit telle quelle sans rien écarter ; dès qu'il
faut filtrer, paginer ou passer par une plateforme, écrire un collecteur.

Sans l'EPCI, la fiche d'une commune laisse croire que son conseil décide de
tout ce qui la concerne (transports, déchets, eau se votent à l'agglo).

## Le collecteur : `data/collecteurs/<code>.py`

C'est ce qui dispense de revenir : `collecter.py` le rejoue en une seconde.
Dans l'ordre :

1. l'entrée du **registre** d'abord : `--modele` y lit le nom et l'URL ;
2. `python scripts/collecter.py --modele <code>` écrit le squelette (n'écrase
   rien), à adapter ;
3. `--a-blanc` : comparer à ce qu'on a vu au navigateur, puis reporter son
   compte dans `ATTENDU` (garde-fou contre une page refaite) ;
4. la collecte réelle.

```python
from collecter import actes_de_la_page, date_fr, page, sans_convocations

URL = "..."
ATTENDU = 17   # le compte de --a-blanc le jour où le collecteur est écrit

def actes(ctx):
    return sans_convocations(actes_de_la_page(page(URL), URL))   # navigateur=True si JS
```

**Convocations et ordres du jour ne sont pas des actes** : rien n'y est voté,
et gardés, ils prennent les places de `--limite` devant les procès-verbaux.
`sans_convocations()` les écarte ; l'appliquer aussi à la sortie d'un
adaptateur de plateforme.

`actes()` rend `[{titre, fichier, date, url}]`, plus, sur un portail,
`numero`, `service`, `direction`, `rapporteur` et `doc_id` (identifiant stable
de l'acte). `actes_de_la_page` lit les dates numériques du nom de fichier ou
du lien (`date_num`) ; `date_fr("séance du 1er juillet 2026")` les dates en
toutes lettres, abréviations comprises (`28fev2024`). Les deux refusent une
date impossible et un horodatage de mise en ligne : sans date lisible, la
date reste vide ; de même quand le nom du fichier et l'intitulé du lien
donnent deux dates différentes. Si le collecteur sait lequel fait foi sur ce
site (un intitulé « Séance du 12 mars » contre un nom de fichier horodaté),
il le dit dans sa docstring et reporte cette date-là. Une date de séance portée par un titre de section, et non
par chaque lien, est au collecteur de la reporter sur les PDF de la section.
Sans `doc_id`, un acte est identifié par le chemin de son URL : deux `pv.pdf`
de dossiers différents restent deux actes, et une même adresse réutilisée
pour une autre séance devient un document distinct (le script le signale).
Pagination, formulaire, API, rendu JS : écrire la mécanique nécessaire.

- **Docstring** : pourquoi cette page, ce qui a fait hésiter, les pièges.
  Sans ça, le réparer après une refonte revient à tout refaire.
- Vérifier avec `--a-blanc` : ne garder le collecteur que s'il retrouve
  exactement les actes vus au navigateur.
- Grande ville : `--limite N` référence tout mais n'archive que les N plus
  récents (Paris publie des recueils de 300 à 500 pages).

## La mémoire : `data/memoire/<code>.md`

À compléter **à chaque passage**. Ce que le collecteur ne dit pas :

- **ce qui a été essayé et écarté, avec la raison** (le plus précieux) ;
- comment se lisent ses actes : structure, formule de vote, décisions non
  votées ;
- ses pièges de qualification (montant sollicité pris pour une recette
  acquise, annuité qui double un total, plafond de marché pris pour une
  dépense) ;
- les données personnelles qu'elle publie, et sous quelle forme ;
- ce qui reste à lire.

Ne pas recopier le contenu des actes : la base le porte. Le
`## Journal automatique` est écrit par `collecter.py` ; ne pas l'éditer.
