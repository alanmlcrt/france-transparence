# AGENTS.md — travailler sur ce dépôt

Instructions valables pour tout agent (Claude Code, Codex, autre CLI). Ce fichier
décrit **comment modifier le projet**. Pour **l'utiliser**, voir
`.claude/skills/france-transparence/SKILL.md`.

## Ce que fait ce dépôt

Recenser les délibérations et comptes rendus des conseils locaux français,
n'importe lesquels, grande ville, village ou intercommunalité, en relever les
montants votés et les pièces citées, et les répertorier dans un tableau de bord
où chaque montant renvoie à l'acte PDF qui le prouve.

**Aucun script ne cherche où une collectivité publie, et c'est le choix
structurant du projet.** Un agent ouvre le site avec un navigateur, trouve la
page des actes, la lit et écrit lui-même les lignes qualifiées en base. Une
version antérieure scriptait cette recherche par motifs ; elle ratait les
sites rendus en JavaScript, se laissait piéger par des intitulés de liens
trompeurs, et rendait zéro document sans que rien ne prenne le relais.

Ce que l'agent comprend une fois, il le dépose dans un collecteur dédié,
`data/collecteurs/<code>.py`, pour ne pas le refaire : `scripts/collecter.py`
l'exécute ensuite en une seconde, sans navigateur. La surveillance hebdomadaire
vit de ça. Mais la lecture des PDF, elle, ne se met jamais en script.

Une collectivité est designée par son code INSEE (commune, 5 caractères) ou par
son SIREN (EPCI : agglo, métropole, communauté de communes — 9 chiffres). Le
type en est déduit, sans option supplémentaire : c'est la colonne générée
`type_collectivite`, seul endroit où vit cette règle.

Ce qu'une collectivité publie change tout ce qu'on peut en dire. Un portail
de délibérations dédié date et numérote ses actes, souvent avec le service et
le rapporteur ; une page de site officiel ne donne que le PDF et l'intitulé de
son lien, sans date de séance. La colonne `source` (`portail` ou `site`) porte
cette distinction, et le dashboard s'en sert pour ne jamais afficher une date
qu'il n'a pas.

Une adresse trouvée une fois s'écrit dans `data/portails.yaml`, seule source :
`collecter.py` la recopie dans la table `portails` (et le rattachement EPCI
dans `appartenances_epci`) à chaque passage. La recherche suivante part de là
au lieu de tout refaire.

## Contexte obligatoire

Avant une modification, lire dans cet ordre :

1. `.claude/skills/france-transparence/SKILL.md` pour le déroulé du pipeline
   agent et ses garde-fous d'éthique ;
2. `dashboard/AGENTS.md` pour ce que montre le tableau de bord ;
3. `DESIGN.md` lorsqu'une interface est modifiée.

## Architecture

```
scripts/base.py         cree et migre la base. Aucun reseau, aucun jugement :
                        c'est le contrat de schema entre l'agent et le dashboard.
scripts/collecter.py    rejoue la collecte d'une collectivite DEJA reperee en
                        executant son collecteur dedie. Il ne cherche rien et
                        refuse une collectivite qui n'en a pas.
scripts/analyse.py      la plume de l'agent : ecrit une lecture (montants,
                        points, pieces, resume) en une transaction depuis un
                        JSON UTF-8, et refuse ce qui violerait un invariant.
                        Ne lit aucun PDF, ne juge de rien.
data/collecteurs/       un collecteur Python par collectivite suivie, ecrit par
                        l'agent apres avoir compris le site.
data/memoire/           un fichier par collectivite : ce que l'agent a appris en
                        LA LISANT. Pistes ecartees, structure de ses actes,
                        pieges de qualification, passages successifs.
                        Ces deux dossiers sont NON VERSIONNES : ils decrivent
                        les collectivites de cet utilisateur, et lui seul.
dashboard/              app Next.js (App Router, TypeScript, Tailwind v4) — lecture seule
data/                   deliberations.db, portails.yaml, PDF telecharges — NON VERSIONNE
                        sauf portails.yaml
.claude/                skill france-transparence pour Claude Code
.agents/                miroir portable du skill france-transparence pour les agents
```

Une règle de placement : le contenu propre au projet vit à la racine ou dans
`scripts/`/`dashboard/`. `.claude/` et `.agents/` ne portent que les copies du
skill `france-transparence` ; leurs autres skills éventuels restent tiers et ignorés.

## Ce qui n'est pas versionné

Le dépôt ne suit que ce qui lui appartient.

- **`data/`** — base, PDF téléchargés, caches. Seule exception :
  `data/portails.yaml`, qui retient où chaque collectivité publie ses actes.
  Il se partage parce qu'il évite à chacun de refaire la même recherche, et
  parce que c'est une adresse vérifiée à la main, pas une sortie de traitement.
- **Les skills tiers** de `.agents/skills/` et `.claude/skills/` — anti-ui-slop,
  ui-design, ui-radar, ui-ux-pro-max. Dupliqués entre les deux dossiers, dont
  rien dans ce projet ne dépend. `skills-lock.json` en garde la source et
  l'empreinte : c'est lui le fichier versionné, pas leur contenu.
- **`dashboard/node_modules/` et `dashboard/.next/`** — installées par `npm`
  et reconstruites par `next build`. `package-lock.json` est versionné : c'est
  lui qui fige les versions.
- **`.claude/settings.local.json`** — réglages propres à une machine.

Reste versionné dans `.claude/skills/` et `.agents/skills/` : le skill
`france-transparence` du projet, et lui seul. Ces deux copies sont des miroirs et
doivent rester strictement identiques.

**Ne jamais ajouter de dépendance vendorisée au suivi.** Si un outil externe est
nécessaire, c'est son gestionnaire qui l'installe et son lockfile qui est
versionné.

## Les invariants

Ils prévalent sur toute autre pratique du projet — un document de conception,
une habitude de code, un ticket. En cas de conflit, l'invariant l'emporte.

1. **Un montant porte sa source.** Chaque ligne collectée renvoie à l'acte
   PDF qui la prouve, servi depuis son chemin enregistré en base — jamais un
   chemin fourni par le client. Un montant sans PDF associé est un défaut de
   livraison, pas une approximation.
2. **Une adresse ouverte, jamais devinée.** `data/portails.yaml` et la table
   `portails` ne reçoivent une entrée qu'après avoir ouvert l'URL et y avoir
   vu des actes. Un sous-domaine qui ressemble à un portail n'en est pas un,
   et une source jamais consultée n'existe pas.
3. **Collecte à la demande.** Jamais de balayage automatique de toutes les
   communes de France en tâche de fond : chaque collectivité est traitée sur
   une demande explicite, nommée. Ça vaut aussi pour une collectivité déjà
   connue : avoir des actes en base ne vaut pas permission de la retraiter
   sans qu'on la nomme. La table `suivi` distingue une collectivité mise en
   suivi actif (mode `surveiller`) d'une simple consultation ponctuelle. Une
   demande qui ne nomme aucune collectivité (« surveille toutes les
   délibérations ») ne porte que sur celles que `suivi` marque actives —
   jamais sur toutes celles jamais consultées, et encore moins sur toutes les
   communes de France.
4. **Lecture seule sur les sources publiques, et sur la base côté dashboard.**
   L'agent n'écrit jamais sur un site de collectivité : il le lit. Le
   navigateur qu'il pilote ne remplit aucun formulaire, ne clique sur aucun
   bouton d'envoi et ne se connecte à aucun espace privé. Seule exception, en
   script et non au navigateur : un adaptateur de plateforme de
   `collecter.py` peut interroger en POST une API de **recherche publique**
   dont c'est la seule forme (DematDoc), sans authentification ni effet sur la
   source — autorisé par l'utilisateur le 2026-10-01. Le tableau de bord
   ouvre `data/deliberations.db` en lecture stricte (`readOnly`, refusé par le
   moteur SQLite lui-même) : c'est son seul mode. Écrivent en base l'agent qui
   exécute le skill (par `scripts/analyse.py` et `scripts/collecter.py`), et
   `scripts/base.py` pour le seul schéma.
5. **Données personnelles écartées.** Les points repérés par l'agent qui
   lit un acte sont consignés comme une alerte — le seul intitulé du
   point de l'ordre du jour, jamais son contenu. Ni affichées en masse, ni
   agrégées, ni republiées au-delà de ce signal. La frontière : un élu ou un
   agent dans l'exercice de son mandat ou de sa fonction (indemnités, frais de
   mandat, délégation) relève de l'action publique ; un particulier nommé ou
   identifiable (aide, succession, sinistre, situation personnelle d'un
   agent) donne une alerte, et aucun montant de ce point n'est écrit en base,
   puisque sa phrase source porterait son nom.
6. **Un PDF lu l'est en entier, et sa lecture n'est terminée qu'avec son
   résumé.** La lecture parcourt toutes les pages et tous les points d'ordre
   du jour, sans échantillonnage ni limite silencieuse. Un document long se
   lit en plusieurs fois, pas en extrait. Si une partie résiste, le statut est
   `echec` : aucune synthèse partielle ne doit être présentée comme complète.
   Qualifier les montants d'une délibération sans écrire ensuite
   `syntheses_reunions` pour cette même délibération est exactement ce cas :
   une analyse partielle que le dashboard ne distingue pas d'une analyse
   complète. Constaté à l'échelle : plus d'une centaine de délibérations
   qualifiées puis jamais résumées. Les deux s'écrivent dans la même passe,
   avant de passer à la délibération suivante — jamais l'une sans l'autre.
   Le texte que l'agent rédige lui-même (`explication`, `resume`,
   `vote_global`, les champs de `points_ordre_jour`) garde ses accents comme
   n'importe quel texte français publié — constaté à l'échelle là aussi :
   des dizaines de lignes affichées sans un seul accent. `python
   scripts/base.py --verifier-accents` les détecte après coup.
7. **Les tags classent, ils ne décorent pas.** Tous les tags automatiques
   peuvent rester en base pour la recherche et les filtres. Le tableau et la
   fiche n'affichent par défaut que le type du document et son état de lecture,
   afin d'éviter un mur de tags sans hiérarchie.
8. **Un signal n'est pas un fait.** Un sujet exige une mention explicite dans
   l'objet, l'ordre du jour ou la décision. Une dépense exige un montant et un
   contexte de dépense. Une citation d'annexe ne permet de conclure ni à sa
   présence ni à son absence dans le dossier publié.
9. **Zéro approximation dans les informations avancées.** Trouver un montant,
   décider s'il s'agit d'une dépense actée ou d'un chiffre de débat, repérer
   une pièce citée : c'est un jugement de lecture, pas un motif à détecter
   dans du texte. Un algorithme à mots-clés génère autant de bruit qu'il rate
   de vrais montants (constaté : 54 000 « candidats » sur 145 délibérations,
   dont l'essentiel n'était pas financier). C'est donc l'agent qui exécute le
   skill `france-transparence` qui lit chaque PDF et écrit directement en base
   les lignes déjà qualifiées
   (`nature`, `decision_financiere`, `verifie`, `retenu`, `explication` — voir
   le skill, « Lire et écrire en base »). Un montant n'est inséré que si sa
   phrase source qualifie explicitement son rôle. Le statut « décidé/voté »
   exige en plus une formulation financière locale et un vote explicite dans
   le même point. Une preuve ne se transfère jamais à une autre occurrence du
   même chiffre. En cas de doute, masquer l'information (valeurs par défaut :
   non vérifié, non retenu). Le dashboard ne montre **que** ces montants
   décidés et votés dans la section financière d'une fiche — une estimation,
   un montant historique, un budget de référence ou la part calculée d'un
   tiers reste en base pour l'audit mais n'apparaît jamais comme s'il
   s'agissait d'une dépense réelle : un chiffre cité dans un débat n'est pas
   un chiffre acté.
10. **Un seul montant final par décision.** Lorsqu'un même point reformule une
    dépense avec un chiffre arrondi dans le débat, retenir uniquement le
    montant précis introduit par la formulation opératoire de la délibération
    et couvert par son vote. Masquer l'arrondi et toutes ses répétitions.
11. **Un montant doit être compris avant d'être affiché.** Le rattacher au bon
    point, distinguer décision et débat, puis qualifier son rôle financier.
    Ne jamais additionner automatiquement les sommes hétérogènes ou répétées
    d'un procès-verbal.

## Conventions de code

- **Dépendances comptées.** `scripts/base.py` : bibliothèque standard
  uniquement, aucune exception. Playwright n'est requis que par l'agent, pour
  piloter un navigateur, et ne fait partie d'aucun script du dépôt. Tableau de
  bord : Next, React et Tailwind, rien d'autre ; `Intl`, `fetch` et
  `node:sqlite` couvrent le reste. Toute dépendance ajoutée se justifie en
  revue, et le diff le plus court qui fonctionne l'emporte.
- **Les scripts exécutent, l'agent décide.** `base.py` crée la base ;
  `collecter.py` relit une page dont l'adresse et la forme ont déjà été
  vérifiées. Aucun des deux ne cherche où une collectivité publie, ne juge
  qu'une page liste des délibérations, ni ne lit un PDF : ça revient à
  l'agent. La frontière n'est pas « script contre agent », c'est « rejouer un
  jugement déjà fait » contre « le faire ». Le projet a payé cher pour la
  trouver.
- **Un automatisme périmé doit échouer bruyamment.** Un collecteur garde dans
  `ATTENDU` le nombre d'actes vus au dernier passage vérifié. Un site refait ne
  provoque aucune erreur : la page répond, les liens ont bougé, la collecte
  rend zéro. Sans ce contrôle, une surveillance hebdomadaire annonce « rien de
  neuf » pendant des mois.
- **Un collecteur explique le site, il ne fait pas que le lire.** Son docstring
  dit pourquoi cette page-là, ce qui a fait hésiter, les pièges rencontrés.
  Sans ça, le réparer après une refonte revient à tout refaire.
- **Ce qui a été essayé et écarté vaut ce qui a réussi.** `data/memoire/` garde
  les impasses avec leur raison. Un agent qui ne les lit pas les refait, et
  elles coûtent plus cher que la collecte elle-même : sur une commune, retrouver
  qu'une source plus récente était inaccessible a demandé une dizaine
  d'explorations. `collecter.py` journalise chaque passage tout seul (date,
  comptes) et signale bruyamment quand aucune analyse d'agent n'a jamais été
  écrite : la seule partie de cette exigence qu'un script peut vérifier sans
  compter sur une instruction lue.
- **Pas d'abstraction spéculative** : pas d'interface à une implémentation, pas
  de configuration pour une valeur qui ne change jamais.
- **Portabilité** : tout reste exécutable sous Windows (PowerShell) comme
  sous shell POSIX.
- **Chemins résolus depuis `__file__`**, jamais depuis le répertoire courant :
  toutes les commandes se lancent depuis la racine du dépôt.
- **Aucun secret en dépôt.** `data/` n'est pas versionné, et rien ne
  s'authentifie nulle part : les sources lues sont publiques.
- **Vocabulaire de la base, fermé.** `source` vaut `portail` ou `site`,
  `statut_lecture` vaut `brut`, `lu` ou `echec`. Ces valeurs sont contraintes
  par des CHECK : les changer impose de reconstruire la table, ce que
  `base.py` sait faire, et de suivre côté dashboard.

## Contrôles

```bash
python scripts/base.py --selftest         # schema, migrations, miroir du skill
python scripts/collecter.py --selftest    # lecture de page, dates, garde-fou
python scripts/analyse.py --selftest      # ecriture d'une lecture, refus
cd dashboard && npm test                  # lecture de la base
cd dashboard && npm run typecheck
```

Tous doivent passer avant toute fusion. Sans réseau : ils construisent leurs
propres fixtures et les suppriment.

## Ce qui se casse le plus souvent

- **Une adresse devinée plutôt qu'ouverte.** Un sous-domaine qui ressemble à
  un portail de délibérations n'en est pas forcément un. Rien n'entre dans
  `portails.yaml` avant d'avoir vu des actes sur la page.
- **Un site lu sans navigateur.** Beaucoup de sites de collectivités rendent
  leur navigation en JavaScript : une page récupérée en HTTP simple y est vide
  de liens, et la collecte conclut à tort qu'il n'y a rien.
- **Un intitulé de lien pris pour la vérité.** « Bulletin municipal » n'est pas
  une délibération, « Actes réglementaires » peut en être une. C'est
  exactement ce qu'un filtre par mots-clés rate, et la raison pour laquelle
  cette étape n'est pas scriptée.
- **Une date lue dans un numéro.** `124_2025`, `D014 2026`, `26.06.29.01` :
  un détecteur de dates y trouve des séances qui n'ont jamais existé (mois 24,
  année 2029). `date_num` et `date_fr` refusent une date impossible, collée à
  d'autres chiffres ou à plus de six mois d'ici, et la base refuse une
  `date_seance` invalide. Une date fausse vaut moins que pas de date.
- **Une page « vide » qui ne l'est pas.** Liste en iframe d'une plateforme
  (Publiact, Mégalis, DematDoc, LegalView), portail open data (Opendatasoft),
  dossier Drive, PDF servi par un script ou
  déclaré dans une visionneuse : `collecter.py` sait lire ces formes
  (`recherche.md`). Conclure « rien de publié » vient après les avoir
  cherchées.
- **Le dashboard qui écrit.** `dashboard/lib/reunions.ts` n'ouvre jamais la
  base autrement qu'en `readOnly`.
- **Un chemin de PDF fourni par le client.** La route qui sert un PDF
  (`app/reunions/[id]/pdf/route.ts`) ne doit lire que le chemin enregistré en
  base pour cet identifiant, jamais un chemin construit depuis la requête.
- **Une analyse partielle présentée comme complète.** Ne jamais tronquer le
  nombre de pages ou de points analysés et ne jamais remplacer un résultat
  absent par « ouvrir la source pour vérifier ». Le PDF reste la preuve, mais
  la fiche doit afficher directement ce qui a réellement été extrait.
- **Un mur de tags.** Les thèmes automatiques alimentent les filtres précis de
  `/reunions` ; ils sont masqués dans les lignes et les en-têtes de fiches.
- **Une déduction présentée comme certaine.** Respecter le vocabulaire fermé
  du skill. Toute donnée avancée doit posséder une phrase de preuve explicite ;
  les occurrences non prouvées restent en base mais sont masquées. Une pièce
  citée est affichée comme « citée », jamais comme absente ou potentiellement
  manquante sans vérification séparée du dossier publié.
