# France Transparence

Code source : [github.com/alanmlcrt/france-transparence](https://github.com/alanmlcrt/france-transparence/tree/main)

Votre conseil municipal vote toute l'année. Il décide de subventions, de marchés
publics, de travaux, d'embauches, de tarifs. Tout est publié : les actes signés
sont en ligne, en PDF, sur le site de la mairie ou sur un portail dédié.

Presque personne ne les lit. Ils sont écrits pour l'administration, dans une
langue qui suppose qu'on connaît déjà le dossier, et une seule décision renvoie
souvent à une pile d'autres documents.

France Transparence récupère ces documents et les rend lisibles. Pour chaque
acte : de quoi il s'agit, ce qui a été décidé, ce que ça engage, et le PDF signé
qui le prouve. Ça fonctionne pour un village de 400 habitants comme pour une
métropole.

## Le principe

L'outil ne cherche pas à accumuler des fichiers. Une archive de PDF que
personne n'ouvre ne vaut pas mieux que le site de la mairie.

Chaque fiche commence donc par un résumé en français courant, écrit pour
quelqu'un qui n'a jamais ouvert une délibération de sa vie. Et aucun chiffre n'y
apparaît sans la phrase du document qui l'établit. Si une somme est présentée
comme une dépense votée, c'est qu'une phrase précise le dit et qu'un vote l'a
couverte.

Tant qu'un document n'a pas été lu, la fiche affiche « pas encore lu ». Elle
n'invente rien pour combler le vide, et ne présente jamais des fragments comme
une analyse.

## Comment ça marche

Le travail se fait en trois temps, et il vaut la peine de savoir lequel fait
quoi :

| Étape | Ce qu'elle produit |
|---|---|
| Recherche | L'adresse où la collectivité publie ses actes, notée pour les fois suivantes |
| Collecte | La liste des actes et leurs PDF téléchargés |
| Lecture | Le résumé, les montants qualifiés, les pièces citées, l'ordre du jour |

**La recherche et la lecture ne sont pas des scripts** : c'est le choix
central du projet. Un agent ouvre le site de la commune dans un vrai
navigateur, cherche où sont les délibérations, puis lit chaque document.
Décider qu'un chiffre est une dépense votée plutôt qu'une estimation citée
en débat demande de suivre un raisonnement, pas d'appliquer une règle.

Une fois qu'on sait où regarder, la collecte devient mécanique. L'agent
écrit donc un petit collecteur Python pour cette commune, dans
`data/collecteurs/<code>.py`, que `scripts/collecter.py` rejoue en une
seconde les fois suivantes : plus besoin de refaire la recherche chaque
semaine, on relit directement la page connue, sans navigateur.

À côté du collecteur, l'agent tient un carnet par commune dans
`data/memoire/`, où il note ce qu'il a compris en lisant : les pistes qu'il a
explorées sans succès, la façon dont cette commune rédige ses actes, ce qui
reste à lire. Grâce à ce carnet, une deuxième demande sur la même commune
part de plus haut que la première, au lieu de repartir de zéro.

Ni les collecteurs ni ces carnets ne sont versionnés : ils décrivent les
communes que vous suivez, pas celles d'un autre. Si le site est refait et que le compte d'actes
s'effondre, le collecteur s'arrête au lieu d'annoncer « rien de neuf », et
l'agent reprend la main pour le réécrire.

## Installation

```bash
git clone https://github.com/alanmlcrt/france-transparence.git "France Transparence"
cd "France Transparence"
python -m pip install -r requirements.txt   # Playwright
python -m playwright install chromium       # le navigateur lui-même
npm run install-dashboard                   # dépendances du tableau de bord
```

Playwright sert à l'agent pour ouvrir les sites de collectivités. Beaucoup
rendent leur navigation en JavaScript : récupérée en HTTP simple, leur page
d'accueil ne contient aucun lien, et la recherche échouerait sans rien
signaler.

`scripts/base.py`, lui, n'a besoin de rien d'autre que Python.

Avec Claude Code, le skill `france-transparence` est trouvé tout seul à
l'ouverture du dossier. Rien à configurer.

Sans agent, il ne reste que la base et le tableau de bord. La collecte et la
lecture ne se font pas à la main : c'est l'agent qui les fait.

## Première utilisation

Le dépôt arrive sans données : pas de base, aucun acte téléchargé. Le tableau
de bord ouvert tout de suite affiche un écran qui explique quoi faire, pas une
erreur. C'est normal, l'outil ne présume pas de la commune qui vous intéresse.
Seul `data/portails.yaml` arrive rempli : les adresses déjà vérifiées par
d'autres utilisateurs, pour que la recherche de ces collectivités ne soit pas à
refaire.

Tout part de votre première demande :

> « Surveille les délibérations de ma commune »

L'agent retrouve le code de la collectivité à partir de son nom, puis ouvre
son site dans un navigateur pour trouver où les actes sont publiés. Il vous dit
ce qu'il a trouvé avant de télécharger quoi que ce soit.

Cette adresse est ensuite écrite dans `data/portails.yaml`, et la deuxième
demande sur la même commune va beaucoup plus vite : la recherche ne se refait
pas, on va droit à la page connue. Le fichier est versionné, donc ce que vous
trouvez peut servir à d'autres.

## Demander quelque chose à l'agent

Le skill se déclenche sur une demande en français, ou explicitement avec
`/france-transparence <mode> <collectivité ou référence>` (par exemple
`/france-transparence analyser 26/172`). Il couvre cinq besoins, un mot par
mode. Dire lequel vous voulez évite qu'il en fasse plus que demandé.

### surveiller : suivre une collectivité dans la durée

> « Surveille ma commune »
> « Mets en place un suivi hebdomadaire du conseil municipal de mon village »
> « Surveille toutes mes collectivités suivies » *(tâche générique, sans nommer
> de ville — voir plus bas)*

Installe une tâche planifiée qui, à chaque passage, relève les nouveaux actes,
télécharge leurs PDF, puis les lit et les résume. Entre deux séances il n'y a
rien de neuf et la tâche ne fait rien. Un conseil municipal siège une poignée de
fois par mois, ce qui rend le rythme hebdomadaire raisonnable, en volume comme
en coût.

La planification vient de Claude Code (skill `schedule`), pas de ce dépôt. La
tâche se contente d'enchaîner la collecte et la lecture.

Une tâche vise une collectivité nommée, ou l'ensemble des collectivités déjà
suivies — jamais toutes les communes de France : le dépôt refuse ce
balayage automatique en tâche de fond (voir plus bas).

Mettre en place ce suivi marque aussi la collectivité en base, dans la table
`suivi` — affichée sur le tableau de bord comme un tag « Suivie ». Consulter
une commune une seule fois (modes `analyser`, `recuperer`, `rattraper`) ne
l'y inscrit pas. Exemple concret : « analyse la dernière délibération de
Douai », une fois, par curiosité, laisse Douai avec des actes en base mais
sans tag « Suivie » ; une tâche « surveille toutes mes collectivités » plus
tard ne la traitera jamais, seulement les villes réellement suivies. Pour
arrêter un suivi : « ne suis plus X », qui démarque la collectivité et
rappelle d'annuler la tâche planifiée correspondante.

### recuperer : prendre les documents, sans les lire

> « Récupère les derniers actes de mon agglomération, sans les analyser »

Collecte et télécharge, puis s'arrête. Pratique pour constituer l'archive
d'abord et lire ensuite. Les fiches resteront marquées « pas encore lu ».

### analyser : un acte précis

> « Analyse la délibération 26/329 »
> « Lis-moi ce compte rendu et dis-moi ce qui a été décidé »

Lit un document en entier, écrit son résumé, qualifie ses montants, relève les
pièces auxquelles il renvoie.

### rattraper : une période entière

> « Analyse ce qui s'est passé en mars 2026 »
> « Lis les actes du 1er au 30 juin »

Reprend l'arriéré : tous les documents déjà téléchargés sur la plage de dates
demandée.

### contextualiser : qui reçoit l'argent

> « C'est quoi cette association qui touche 1 500 € ? »

Cherche ce que fait au quotidien le bénéficiaire d'une dépense, à partir de
sources publiques qu'il cite (annuaire des entreprises, Journal officiel des
associations). Ce contexte est présenté à part, et ne rejoint jamais ce que
prouve le PDF.

## Les commandes, sans agent

Tout se lance depuis la racine du dépôt.

```bash
python scripts/base.py                                 # crée ou migre la base
cat data/portails.yaml                                 # où chaque collectivité publie
python scripts/collecter.py --insee <code>             # relit la page connue
python scripts/collecter.py --insee <code> --limite 6  # n'archive que les 6 derniers
python scripts/collecter.py --insee <code> --a-blanc   # sans rien écrire
python scripts/collecter.py --modele <code>            # squelette de collecteur
python scripts/analyse.py --a-lire <code>              # ce qui reste à lire
python scripts/collecter.py --etat                     # bilan de chaque collectivité
```

`base.py` crée les dix tables et rien d'autre : pas de réseau, pas de
recherche. C'est le contrat de schéma entre l'agent qui remplit la base et le
tableau de bord qui la lit, écrit une fois pour que les deux ne dérivent pas.

Une collectivité est désignée par son code INSEE (commune, 5 caractères) ou par
son SIREN (intercommunalité, 9 chiffres). Le type se déduit du code. Si vous ne
le connaissez pas, `geo.api.gouv.fr` le donne à partir du nom, et l'agent s'en
charge.

Les intercommunalités comptent autant que les communes, parfois plus. Ce sont
elles qui décident des transports, des déchets, de l'eau et d'une bonne part de
la voirie : le budget qui vous concerne n'est pas entièrement voté à la mairie.

`data/portails.yaml` note, pour chaque collectivité déjà cherchée, où elle
publie et ce qu'on y trouve. Le champ `type` vaut `portail` quand les actes
sont numérotés et datés de leur vraie séance, `site` quand on n'a que le PDF et
l'intitulé de son lien. La distinction n'est pas cosmétique : le tableau de
bord refuse d'afficher une date de séance qu'il n'a pas.

Rien n'entre dans ce fichier sans que la page ait été ouverte et que des actes
y aient été vus. Une adresse supposée est une source qui n'existe pas.

## Le tableau de bord

```bash
npm run dev     # http://localhost:3000
```

- `/` : ce que contient la base
- `/collectivites` : communes et intercommunalités, filtrables par type
- `/collectivites/[code]` : les actes d'une collectivité, groupés par séance,
  avec un lien de la fiche d'une commune vers son intercommunalité
- `/reunions` : tous les actes, filtrables par texte, collectivité, état de
  lecture, sujet et dates
- `/reunions/[id]` : le résumé, l'ordre du jour, les dépenses votées, les pièces
  citées et le PDF signé

C'est une application Next.js (App Router, TypeScript, Tailwind) dans
`dashboard/`, strictement en lecture. La base est ouverte en `readOnly` : toute
écriture est refusée par SQLite lui-même, pas par convention. `FT_DELIB_DB`
permet de pointer une autre base que celle par défaut.

## Vérifier que tout marche

```bash
python scripts/base.py --selftest
python scripts/collecter.py --selftest
python scripts/analyse.py --selftest
cd dashboard && npm test && npm run typecheck
```

Aucun de ces contrôles n'a besoin du réseau : ils construisent leurs propres
fixtures et les effacent. Ils doivent tous passer avant une fusion.

## Organisation du dépôt

```
scripts/       base.py (crée et migre la base), collecter.py (rejoue la
               collecte d'une collectivité déjà repérée), analyse.py (écrit
               en base ce que l'agent a lu, d'un bloc)
data/collecteurs/  un collecteur Python par commune suivie. Non versionné :
               ce sont vos communes, et du code exécuté tel quel
data/memoire/  ce que l'agent a appris sur chaque commune en la lisant :
               pistes écartées, pièges, ce qui reste à faire. Non versionné
dashboard/     l'application Next.js, en lecture seule
data/          la base, le registre des portails, les PDF. Non versionné,
               sauf portails.yaml
.claude/       le skill france-transparence pour Claude Code
.agents/       le même skill, pour les autres agents
```

`AGENTS.md` est le contrat que suit tout agent qui modifie le projet. Ses onze
invariants l'emportent sur n'importe quelle autre habitude de code.

## Contribuer

Ce qui manque le plus, c'est `data/portails.yaml`. Chaque collectivité que
vous faites suivre y ajoute une adresse vérifiée, et cette adresse évite à
tous les suivants de refaire la recherche. C'est la seule partie du projet qui
s'améliore par accumulation.

Pour repérer un candidat : les sous-domaines habituels sont `deliberations.`,
`actes.`, `bo.`, et une recherche du type `site:ville-x.fr délibération conseil
municipal` donne souvent le bon lien. Notez dans `notes` ce que la source donne
et ce qu'elle ne donne pas, c'est ce qui manque le plus quand on y revient.

## Ce que l'outil ne sait pas faire

Quand les documents viennent du site de la mairie plutôt que d'un portail, on
n'a ni service, ni direction, ni rapporteur : seulement le PDF et l'intitulé de
son lien. La date réelle de la séance est inconnue, et le tableau de bord
affiche alors « date non renseignée » au lieu d'en inventer une.

Certaines communes ne publient pas leurs délibérations en ligne, ou seulement
sous forme d'affichage en mairie. L'outil ne peut rien y faire, et le dit.

Les très grandes villes changent d'échelle. Paris vote environ 5 000
délibérations par an et publie des recueils de séance de 300 à 500 pages :
les référencer est immédiat, les lire entièrement ne l'est pas. `--limite`
borne ce qu'on archive, mais la lecture d'un tel document reste un travail
long, et une fiche non lue le dit plutôt que de résumer trois pages sur
cinq cents.

La collecte a un coût : elle mobilise un agent et un navigateur pour chaque
collectivité. C'est le prix de la fiabilité sur des sites tous différents, mais
ça rend impossible de suivre des centaines de communes à la fois, et c'est très
bien ainsi.

## Règles que l'outil s'impose

Une pause entre deux requêtes vers un même serveur municipal, navigateur
compris. Ces serveurs sont modestes et le service est public.

La collecte se fait à la demande, pour une collectivité nommée. Jamais un
parcours automatique de toutes les communes de France en tâche de fond.

Les comptes rendus des petites communes contiennent régulièrement des données
personnelles : aides sociales nominatives, adresses de particuliers. L'agent qui
lit un document note l'intitulé du point concerné comme une alerte, jamais son
contenu. Ne les recopiez pas, ne les regroupez pas, ne les republiez pas.

Lecture seule d'un bout à l'autre. Le navigateur sert à lire des pages
publiques : il ne remplit aucun formulaire, ne se connecte à aucun espace privé
et n'envoie rien à une administration.

## Licence

Code sous licence MIT (voir [LICENSE](LICENSE)). Les documents récupérés sont
publics, publiés par les collectivités elles-mêmes.
