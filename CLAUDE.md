# CLAUDE.md

Voir **[AGENTS.md](AGENTS.md)** — architecture, invariants, conventions de code,
contrôles et workflow. Ce fichier n'ajoute que ce qui est propre à Claude Code.

## Utiliser l'outil

Le skill `france-transparence` (`.claude/skills/france-transparence/SKILL.md`) se
déclenche seul sur une demande de surveillance, de collecte ou de
consultation des délibérations d'une collectivité. Cinq modes, un mot chacun : `surveiller`
(planification), `recuperer` (téléchargement seul), `analyser` (un acte),
`rattraper` (une plage de dates) et `contextualiser` (qui est le bénéficiaire
d'une dépense). Aucun script ne cherche où une collectivité publie : l'agent ouvre lui-même
son site avec un navigateur (Playwright), trouve la page des actes et la
décrit une fois dans `data/portails.yaml`. `scripts/collecter.py` rejoue
ensuite cette collecte sans navigateur, `scripts/analyse.py` écrit en base ce que
l'agent a lu, et `scripts/base.py` ne fait que créer
et migrer la base. La lecture des PDF revient toujours à l'agent. Le skill décrit ce déroulé et les garde-fous d'éthique
(politesse réseau, lecture seule, données personnelles).

## Modifier le projet

Avant de fusionner : `python scripts/base.py --selftest`,
`python scripts/collecter.py --selftest` et `python scripts/analyse.py
--selftest`, puis `npm test` **et**
`npm run typecheck` dans `dashboard/`.

Le tableau de bord est une application Next.js dans `dashboard/`. Sa version de
Next impose ses propres conventions : lire `dashboard/AGENTS.md` et
`dashboard/node_modules/next/dist/docs/` avant d'y écrire du code.
