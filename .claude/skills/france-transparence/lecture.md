# Lire un PDF et l'écrire en base

## Lire

- **Le PDF entier**, avec l'outil `Read` (par tranches de `pages` s'il est
  long), jamais une extraction de couche texte : les pages arrivent rendues,
  un tableau garde ses lignes, un scan se lit comme un natif. Extrait en texte,
  un montant et son intitulé sortent sur deux lignes, parfois inversées ;
  attribuer une somme à la mauvaise ligne est une erreur de fond. Si la mise
  en page ne tranche pas : `verifie = 0`. `Read` renvoie parfois aussi la
  couche texte à côté des pages rendues : elle aide à repérer un passage,
  mais un montant et sa ligne se lisent sur la page rendue.
- Toutes les pages, tous les points, tous les montants. Une partie qui résiste
  → `"statut": "echec"`, jamais une synthèse partielle présentée comme
  complète.
- Ne relis pas un PDF déjà traité sans demande : la trace en base fait foi.
- Plusieurs sous-agents en parallèle seulement pour un rattrapage de dizaines
  de délibérations ; un seul agent sinon.
- **Quoi lire d'abord** : `--a-lire` donne les inachevées, puis les plus
  récentes. Un procès-verbal ou une délibération avant une liste des
  délibérations de la même séance : la liste ne porte ni exposé ni montant.
  Une liste se lit quand elle est seule pour sa séance (le PV vient souvent des
  mois plus tard) : elle prouve les votes. Son résumé tient en un paragraphe
  (objets votés, majorités) et dit qu'aucun montant n'y figure.

## Comprendre avant d'écrire

Pour chaque point : numéro et objet exacts ; distinguer la proposition, le
débat et la décision soumise au vote ; rattacher chaque montant au bon point
et lui donner son rôle ; dire s'il est décidé ou seulement cité ; garder la
phrase source complète, sans points de suspension ajoutés.

**Montants** (invariants 8 à 11 d'`AGENTS.md`) :

- `nature`, vocabulaire fermé : `Dépense`, `Recette`, `Recette abandonnée`,
  `Financement par un tiers`, `Estimation de la part d'un tiers`,
  `Estimation`, `Montant historique`, `Montant de référence`,
  `Montant mentionné`, et trois **engagements votés qui ne sont pas des
  dépenses** : `Garantie d'emprunt` (le montant garanti par la collectivité,
  pas celui de l'emprunt quand elle n'en garantit qu'une part),
  `Autorisation de programme` (le montant de l'AP ; ses crédits de paiement
  annuels « prévisionnels » sont des `Estimation`), `Plafond voté` (« dans la
  limite de », « pour un montant maximal de » : la borne que le vote fixe à
  une dépense encore à chiffrer). Ces trois-là peuvent porter
  `decision_financiere = 1` quand le vote les adopte : la fiche les affiche
  avec leur nature, sans les additionner. Un simple accord de principe, qu'une
  délibération ultérieure confirmera, reste `Montant de référence` ; un plafond
  calculé par la loi et seulement rappelé (indemnités maximales des élus)
  aussi, puisque le conseil ne le vote pas ; un engagement voté par une
  délibération antérieure et seulement cité reste `Montant historique`.
- `verifie = 1` seulement si **sa propre phrase** qualifie explicitement son
  rôle. Une preuve ne se transfère jamais à une autre occurrence du même
  chiffre. Ambigu : `verifie = 0`, nature `Montant mentionné`.
- `decision_financiere = 1` seulement si le même point porte une formulation
  financière locale **et** un résultat de vote explicite. Jamais pour une
  estimation, un historique, un budget de référence ou la part d'un tiers.
  Seuls ces montants s'affichent sur la fiche ; les autres restent pour
  l'audit.
- Une dépense exige un montant et une action de dépense (achat, travaux,
  facture, rémunération, subvention attribuée, marché conclu, crédits
  engagés). Recette, plafond, financement reçu, estimation : pas une dépense.
- **Un seul montant final par décision** : le chiffre précis introduit par la
  formulation opératoire (« Par cette délibération... ») et couvert par le vote
  porte `retenu = 1` ; l'arrondi du débat et ses répétitions `retenu = 0`. La
  seule proximité numérique ne fusionne jamais deux dépenses.
- **HT et TTC** pour le même montant : retenir celui de la formulation
  opératoire (le plus souvent le HT, « le conseil autorise la signature du
  devis de X € HT ») et marquer l'autre `retenu = 0`, même nature, avec
  « même montant exprimé TTC » en explication. Un seul des deux cité : on le
  garde tel quel, avec son `suffixe`.
- **Totaux et lignes** d'une décision modificative ou d'un budget : retenir
  les lignes votées et marquer les totaux de section `Montant de référence` ;
  le contraire compterait deux fois la même somme.
- **Un montant tiré d'un tableau** : `phrase` reprend les cellules exactes,
  intitulé de ligne puis colonne (« AP 2026-1 École Jules Verne | Montant de
  l'AP : 2 348 456 € »), sans rien reformuler ; l'`explication` dit qu'il
  s'agit d'une ligne de tableau.
- Ne jamais additionner les montants d'un procès-verbal. Un nombre lu et jugé
  non financier (article, SIRET, date) ne s'écrit pas du tout.
- `explication` justifie le rôle **depuis le PDF seul** ; aucun contexte
  externe.

**Thèmes**, seulement si le sujet est explicite dans l'intitulé, l'ordre du
jour ou la décision : `Budget et fiscalité`, `Subventions`, `Commande
publique`, `Urbanisme et foncier`, `Mobilités et voirie`, `Bâtiments et
patrimoine`, `Transition écologique`, `Ressources humaines`, `Éducation et
jeunesse`, `Culture`, `Sports`, `Solidarités et santé`, `Sécurité`,
`Numérique`, `Logement`, `Eau et assainissement`.

**Pièces citées** : un type de document explicitement désigné comme pièce du
dossier, une fois par délibération, forme canonique : `annexe`, `arrêté`,
`avenant`, `bail`, `bilan`, `CCAP`, `CCTP`, `charte`, `consultation`,
`contrat`, `convention`, `délibération`, `devis`, `diagnostic`, `étude`,
`facture`, `marché`, `notice`, `offre`, `plan de financement`,
`procès-verbal`, `protocole`, `rapport`. « Vu le CGCT » est un fondement, pas
une pièce ; un « Vu la délibération du... » d'usage ne vaut que s'il éclaire
la décision. Citée ne veut dire ni présente ni absente du dossier publié.

**Alertes** : le seul intitulé d'un point sensible (aide nominative, adresse,
situation individuelle, succession, sinistre chez un particulier), jamais son
contenu. La frontière :

- **Un élu, ou un agent, dans l'exercice de son mandat ou de sa fonction**
  (indemnités, remboursement de frais de mandat — y compris une dépense de
  la commune qu'un élu a avancée de sa poche —, délégation, désignation dans
  un organisme) : c'est l'action publique, publiée comme telle. Pas d'alerte ;
  les montants s'écrivent normalement.
- **Un particulier nommé ou identifiable** (habitant, famille, propriétaire,
  agent dans sa situation personnelle : sanction, maladie, logement) : une
  alerte portant l'intitulé du point, et **aucun montant de ce point n'est
  écrit**, puisque sa `phrase` porterait le nom. Si l'intitulé du point nomme
  la personne, l'alerte le reprend en remplaçant le nom par sa qualité
  (« Cimetière ancien : tombe d'une particulière ») : sinon le nom entre en
  base par l'alerte même. Le résumé en parle sans nommer (« une aide
  individuelle a été accordée »).

## Le résumé : c'est lui qui termine la lecture

Deux à trois paragraphes en français courant, pour quelqu'un qui n'a jamais
ouvert une délibération, **avec ses accents** (texte publié tel quel) :

1. *Ce que c'est et ce qui a été voté* : nommer l'acte, traduire le jargon
   dans la phrase même (« ce n'est pas un nouveau budget : il reprend le
   résultat de l'exercice précédent et ajuste les crédits déjà votés »),
   donner le total et la majorité.
2. *Les chiffres clés, nommés par ce qu'ils paient* : six à huit postes
   maximum (« 285 000 € de dépenses courantes : papier, produits d'entretien,
   couches pour les crèches »). Un poste qu'un habitant reconnaît apprend plus
   que la plus grosse ligne.
3. *Ce que ça change* : les évolutions que le document donne, avec leurs deux
   valeurs (emprunt de 106,4 à 88,7 M€, épargne brute de 33,6 à 20,9 M€) ; une
   tension se dit sans la commenter.

Tout vient du PDF. Un acte qui n'engage aucune dépense (prise d'acte, rapport
pour information) le dit. `points` suit les vraies divisions du document, pas
une ligne par ligne de tableau. `vote_global` reprend « à l'unanimité » ou
« à la majorité » (avec les voix contre et abstentions si données), jamais
« adopté » seul. `nombre_presents` vient de l'en-tête de séance ; le cadre de
signature vierge des maquettes M57 (« membres présents : 0 ») n'est pas un
quorum.

## Écrire : un fichier, une transaction

Écrire `scratch_analyse.json` (UTF-8, ignoré par git) puis
`python scripts/analyse.py --ecrire scratch_analyse.json` :

```json
{"id": 12,
 "resume": "Premier paragraphe.\n\nDeuxième.\n\nTroisième.",
 "vote_global": "Adoptée à l'unanimité", "nombre_presents": 45,
 "points": [{"titre": "Avenant n°2 au marché Concorde", "decision": "Approuvé",
             "resultat_vote": "Unanimité", "est_budget": false}],
 "montants": [{"valeur": 603006.10, "suffixe": "HT",
               "phrase": "L'avenant n°2 porte le montant du marché de +603 006,10 € HT.",
               "point": "26/172 Avenant marché Concorde", "nature": "Dépense",
               "decision_financiere": 1, "verifie": 1, "retenu": 1,
               "explication": "Incidence de l'avenant chiffrée ; délibération adoptée à l'unanimité."}],
 "pieces": ["avenant"], "alertes": [], "themes": ["Commande publique"]}
```

Le script refuse tout ce qui violerait un invariant (lecture sans résumé,
vocabulaire hors liste, estimation « décidée », montant vérifié sans
explication) **sans rien écrire**, et signale les mots sans accent : corriger
le fichier et relancer — une réécriture remplace la précédente. Une liste
d'objets écrit plusieurs lectures, chacune dans sa transaction : elle sert
au rattrapage par sous-agents, qui rendent chacun leurs lectures terminées.
Seul, écrire chaque délibération dès qu'elle est lue, avant d'ouvrir la
suivante : un budget épuisé en cours de route ne perd alors rien. Un PDF qui
résiste : `{"id": 12, "statut": "echec"}`.

Ce que le PDF ne dit pas s'affiche « non détecté » ; il ne se comble pas.
