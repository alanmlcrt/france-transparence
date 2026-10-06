<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Contexte France Transparence

Avant toute modification du dashboard, lire :

1. `../AGENTS.md` — invariants du projet, dont l'invariant 9 sur l'affichage
   des montants, qui s'applique ici et n'est pas redit ;
2. `../scripts/base.py` — le schéma de `data/deliberations.db`, qui fait seul
   autorité sur les noms de tables et de colonnes ;
3. `../.claude/skills/france-transparence/SKILL.md` — comment l'agent remplit
   cette base ;
4. `../DESIGN.md` — contrat visuel, seulement pour une modification d'interface.

**Lecture seule, sans exception.** Le dashboard n'écrit jamais dans la base ;
aucun Python ne vit dans `dashboard/`.

**Routes.** `/` résume la base. `/collectivites` et `/collectivites/[code]`
parcourent communes (code INSEE) et intercommunalités (SIREN), filtrables par
`?type=commune|epci` ; `/villes` y redirige pour ne pas casser les liens déjà
partagés. `/reunions` liste les actes, `/reunions/[id]` en montre le détail,
`/reunions/[id]/pdf` sert la copie archivée.

**Ce que le dashboard ne recalcule jamais.** Le type d'une collectivité vient
de la colonne générée `type_collectivite`. Le rattachement d'une commune à son
intercommunalité vient de `appartenances_epci` — agglo pas encore connue (pas
d'actes en base) : on la nomme sans lien plutôt que de promettre une fiche
vide.

**Suivi actif, pas juste « a des actes ».** La table `suivi` (voir
`../AGENTS.md`, invariant 3) dit si une collectivité est en surveillance
planifiée, distinct du fait d'avoir des actes en base — une commune peut être
`suivie=false` avec 200 délibérations, simplement consultée une fois. Table
ajoutée après coup : une base plus ancienne peut ne pas l'avoir encore,
`communesMoissonnees()` s'en accommode (`suivie: false` par défaut) au lieu
d'échouer.

**Ce qui prouve qu'un document a été lu.** `statut_lecture` ne dit que « PDF
parcouru ». L'analyse réelle se prouve par une ligne dans `syntheses_reunions`
— un résumé écrit, rien d'autre. Des montants qualifiés (même affichables
comme décision financière) ne suffisent pas : c'est une analyse commencée,
pas terminée (voir `../AGENTS.md`, invariant 6). Porter une `explication` ne
suffit pas non plus : un agent explique aussi pourquoi il écarte un SIRET ou
une borne de tableau, et une délibération peut compter vingt montants
« expliqués » sans qu'aucun ne soit une décision financière — marquer
« analysée » sur ces seuls critères affichait un badge vert au-dessus d'une
fiche vide ou incomplète. L'état affiché et l'état filtrable sortent d'une
seule définition, `lib/etat-lecture.ts` : sans ça, filtrer « lu et analysé »
ramène des lignes marquées « pas analysé ».

**Un tag classe, il n'informe pas.** Le composant `Tag` (pill colorée) est
réservé aux attributs qu'on peut vraiment filtrer ou classer : état de
lecture, type de document, thème, signal, nature d'un montant décidé. Une
citation, un fait descriptif ou une liste de contenu (pièces citées, par
exemple) s'affiche en texte simple — la pill suggère une catégorie sur
laquelle on peut agir, et en mettre sur ce qui ne l'est pas fabrique du bruit
qu'un utilisateur apprend vite à ignorer, y compris pour les tags qui, eux,
comptent.

**Ce qu'une fiche n'affirme pas.** Sans lecture d'agent, elle annonce « pas
encore lu » plutôt que d'exposer des fragments. Une date de séance s'affiche
quelle que soit la source, parce qu'elle n'est écrite en base que si elle a
été lue (sur la source ou dans l'acte, voir `lib/reunions.ts`) ; sans date
lue, la fiche le dit au lieu d'en inventer une. Une pièce citée prouve
que le texte la mentionne, jamais sa présence ou son absence dans le dossier
publié.

**Le PDF est servi depuis le chemin enregistré en base**
(`app/reunions/[id]/pdf/route.ts`) — jamais un chemin fourni par le client.
Ce chemin est relatif à la racine du dépôt (le parent de `data/`) ;
`cheminPdf()` le résout, et laisse tel quel un chemin absolu d'une base
ancienne.
Quand la copie archivée manque, la fiche mène à l'URL d'origine, en la
distinguant de l'archive : l'une est figée et empreintée, l'autre peut changer.
