---
name: france-transparence
description: Surveiller, récupérer et analyser les délibérations, comptes rendus et actes signés d'une commune ou d'un EPCI français (grande ville ou village), archivés dans data/deliberations.db. À utiliser pour planifier le suivi d'une collectivité, télécharger ses derniers actes, analyser une délibération ou une période, repérer les pièces citées, documenter le bénéficiaire d'une subvention ou d'un marché, ou alimenter le tableau de bord « Réunions ».
arguments: mode
user_invocable: true
argument-hint: "[surveiller | recuperer | analyser | rattraper | contextualiser] <collectivité ou référence>"
license: MIT
---

# France Transparence

Recense les actes signés d'un conseil municipal ou communautaire : où la
collectivité les publie, ce que chacun décide, ce qu'il engage, et le PDF qui
le prouve. Résultat : `data/deliberations.db` (lue en lecture seule par le
dashboard) et `data/portails.yaml` (où chercher la prochaine fois).

Trouver où une collectivité publie et lire un PDF sont des jugements : c'est
toi, navigateur compris. Rejouer une collecte déjà comprise et écrire en base
sont mécaniques : ce sont les scripts. **Ne lis que la référence dont le mode a
besoin** (tableau ci-dessous) : c'est ce qui garde une passe hebdomadaire
courte.

## Modes

| L'utilisateur veut... | Mode | Ce qui se passe | À lire en plus |
|---|---|---|---|
| « surveille X », « suivi hebdo de X » | **surveiller** | Tâche planifiée + table `suivi` (ci-dessous). Rien d'autre dans la conversation. | — |
| « récupère les derniers actes », « sans analyser » | **recuperer** | Collecte et téléchargement, **aucune lecture** : les fiches restent « pas encore lu ». | `recherche.md` si inconnue |
| « analyse la 26/172 », « regarde ce PDF » | **analyser** | Lit un seul acte (`numero` ou `id`), même déjà lu. | `lecture.md` |
| « ce qui s'est passé en mars » | **rattraper** | Lit tous les actes téléchargés de la période. | `lecture.md` |
| « c'est quoi cette association ? » | **contextualiser** | Documente le bénéficiaire d'une dépense actée, hors chaîne de preuve. | `contexte.md` |

Sans mode précisé : la chaîne complète (collecter puis lire). En commande,
`/france-transparence <mode> <reste>` : le premier mot fixe le mode, le reste
se lit comme une demande ordinaire ; sans mode reconnu, traiter toute la
phrase comme une demande en français.

## Le déroulé

**1. Nom → code.** Tout est rangé par code INSEE (commune, 5 caractères, 2A/2B
en Corse) ou SIREN (EPCI, 9 chiffres). Le type s'en déduit en base (colonne
générée) : ne jamais l'écrire.

```bash
curl -s "https://geo.api.gouv.fr/communes?nom=<nom>&fields=nom,code,epci"
curl -s "https://geo.api.gouv.fr/epcis?nom=<nom>"
```

Plusieurs communes portent le même nom (`nom=Paris` renvoie Parisot d'abord) :
demander laquelle plutôt que choisir.

**2. Mémoire, avant toute requête vers le site.** La règle la plus utile, et la
plus oubliée : elle porte les pistes déjà écartées, qui coûtent plus cher à
refaire que toute la collecte.

```bash
python scripts/collecter.py --memoire <code>
```

Elle peut dire que la source est **close** : « 0 nouveau » n'y est alors pas
une absence d'actualité.

**3. Collecter.** Si `data/collecteurs/<code>.py` existe, tout est déjà compris :
ne rouvre pas de navigateur.

```bash
python scripts/collecter.py --insee <code>             # référence, télécharge, journalise
python scripts/collecter.py --insee <code> --limite 6  # grande ville : n'archive que les 6 plus récents
python scripts/collecter.py --insee <code> --a-blanc   # montre sans rien écrire
```

Le script synchronise aussi `data/portails.yaml` vers la base. **« 0 nouveau »
et aucune lecture demandée : la passe est finie**, sans charger `lecture.md`.
S'il s'arrête
sur un **effondrement du nombre d'actes**, ne force pas : le site a été refait,
rouvre la page et corrige le collecteur (`recherche.md`). Collectivité
inconnue, ou au registre sans collecteur : **lire `recherche.md`**.

**4. Lire** (sauf `recuperer`) : **lire `lecture.md`**, puis

```bash
python scripts/analyse.py --a-lire <code>                        # à lire : inachevées, puis les plus récentes
python scripts/analyse.py --a-lire <code> --du AAAA-MM-JJ --au AAAA-MM-JJ
python scripts/analyse.py --a-lire <code> --acte <numero|id>
python scripts/analyse.py --ecrire scratch_analyse.json          # une lecture, d'un bloc
```

La liste donne le nombre de pages : un long PDF se lit par tranches prévues
d'avance. Une délibération, du PDF au résumé, avant la suivante. Si le budget de la
session s'épuise, s'arrêter **avant** d'en entamer une nouvelle.

**5. Mémoire, après.** Compléter `data/memoire/<code>.md` avec ce qui ne se
redevine pas (voir `recherche.md`, « La mémoire »). `collecter.py` y journalise
seul chaque passage et crie si aucune analyse d'agent n'y figure.

## Suivi actif et consultation ponctuelle

```bash
python scripts/collecter.py --etat               # bilan : suivi, collecteur, à lire
python scripts/collecter.py --suivi <code>:on    # entre en suivi actif
python scripts/collecter.py --suivi <code>:off   # en sort
python scripts/collecter.py --suivi-liste        # codes suivis, un par ligne
```

La table `suivi` seule dit qu'une collectivité est **suivie** ; des actes en
base, une mémoire ou une entrée au registre ne le disent pas. **Une demande
qui ne nomme aucune collectivité** (« mets à jour mes communes ») ne porte que
sur `--suivi-liste`, traitée une par une, jamais en parallèle ; liste vide :
le dire et s'arrêter.

**surveiller** : créer la tâche avec le skill `schedule` (« france-transparence :
suivre <nom> », hebdomadaire), puis `--suivi <code>:on`. Chaque passage
planifié rejoue `--suivi <code>:on` (sans effet si déjà fait), lit la mémoire,
lance le collecteur et lit les nouveaux actes, sans sous-agents. **Arrêter** :
`--suivi <code>:off`, et dire à l'utilisateur d'annuler la tâche planifiée —
ce sont deux systèmes séparés. Avant de planifier, `--etat` doit montrer un
collecteur pour ce code : sinon la tâche échouera chaque semaine.

## Éthique, non négociable

- **À la demande, pour une collectivité nommée** (ou suivie). Jamais de
  balayage de toutes les communes, ni de tâche multi-communes.
- **Politesse réseau** : une demi-seconde entre deux requêtes vers un même
  serveur, navigateur compris ; jamais de collecte parallèle sur une même
  collectivité.
- **Lecture seule** : aucun formulaire, aucun bouton d'envoi, aucun espace
  privé ; une bannière de cookies se refuse (non-essentiel). Une recherche
  publique en POST ne passe que par un adaptateur de `collecter.py`
  (`recherche.md`), jamais par le navigateur.
- **Données personnelles** : un point sensible (aide nominative, adresse,
  situation individuelle) devient une alerte portant son seul intitulé,
  jamais son contenu.
- **Rien d'inventé** : une URL non ouverte n'est pas une source, une date non
  publiée n'est pas une date de séance, un montant sans phrase de preuve n'est
  pas une dépense. Dans le doute, l'absence s'affiche.

## Après une commande : proposer la suite

Proposer deux ou trois suites concrètes, tirées de ce que le passage a révélé
(nommer collectivité, date, numéro) :

- après `recuperer` : lire ce qui vient d'arriver ; aller chercher des séances
  plus anciennes ; `surveiller` si la cadence le justifie ;
- après `analyser`/`rattraper` : lire les actes `brut` restants ;
  `contextualiser` un bénéficiaire cité ; signaler un procès-verbal pas encore
  publié ;
- après `surveiller` : signaler si l'EPCI de communes suivies ne l'est pas ;
- après `contextualiser` : signaler un bénéficiaire récurrent.

Un refus ou un silence clôt la commande.

## Voir le résultat

`npm run dev` à la racine (`FT_DELIB_DB=/chemin/vers.db` pour une autre base),
puis `/reunions`.
