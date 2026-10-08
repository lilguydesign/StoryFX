# Recettes manuelles distinctes

Les recettes sont des plans privés du propriétaire authentifié. Leur création
ne lance aucune publication, ne pose aucun verrou et n'active aucun automatisme.
Le contrat utilise les mêmes contrôles de session propriétaire et d'origine que
le centre de contrôle. Aucun jeton, contenu média ou numéro n'est ajouté au rapport.

## API

Préfixe : `/v1/control`.

| Méthode et route | Corps | Effet |
| --- | --- | --- |
| `POST /recipes` | `client_key` UUID, `revision`, `row_ids` UUID uniques (1–30), `executor: "android"` | Brouillon figé, aucun envoi. |
| `GET /recipes` | Aucun | Cent derniers plans, plus le plan actif s'il est plus ancien. |
| `GET /recipes/{id}` | Aucun | Vue propriétaire du plan et de ses étapes. |
| `POST /recipes/{id}/start` | `{}` | Verrou persistant et drainage ; aucune réservation. |
| `POST /recipes/{id}/steps/{step_id}/launch` | `client_key` UUID | Une réservation explicite, jamais l'étape suivante automatiquement. |
| `POST /recipes/{id}/cancel` | `{}` | Ferme les étapes futures ; aucun job annulé ou interrompu. |
| `POST /recipes/{id}/release` | `{}` | Libération après réussite ou annulation, seulement après tous les reçus. |

Les vues sont retournées directement, sauf le lancement qui retourne
`job_id`, `occurrence_id`, `state` et `recipe` (la vue actualisée).
Les états calculés sont `DRAFT`, `DRAINING`, `READY`, `IN_PROGRESS`, `COOLDOWN`,
`BLOCKED`, `PASSED`, `CANCELLED` et `RELEASED`. `next_allowed_at` est en UTC.
La vue inclut `lock_held`, `external_pending`, `next_step_id`, `block_reason`,
`scheduler_before`, `all_steps_verified`, et les publications figées de `steps`.

La clé de création est unique par propriétaire. Rejouer une requête identique
retourne le même plan même si la révision a changé ; réutiliser sa clé pour une
autre définition produit `RECIPE_IDEMPOTENCY_CONFLICT`. Une étape possède au plus
une tentative : une répétition après timeout, annulation ou libération retourne
cette tentative. Une clé de lancement déjà affectée à une autre étape est refusée.
L'occurrence SHA-256 utilise le domaine distinct `recipe:v1` ; aucun ancien
identifiant, `original_occurrence` ou `retry_parent` n'est réutilisé.

## Verrou, drainage et preuves

Le verrou bloque les réservations ordinaires, les rattrapages, les retries et
le démarrage automatique du propriétaire. Le scheduler vérifie ce verrou avant
authentification ou contrôle de révision ; sa pause interne ne peut pas annuler
une file conservée sous verrou. Les tâches déjà `QUEUED` ou `CLAIMED` continuent
normalement, leurs reçus sont toujours acceptés. Un timeout `NEEDS_REVIEW` sans
reçu final reste non terminé : il ne permet ni lancement de recette ni libération.

Une seule étape peut être réservée. Le prochain lancement explicite exige une
preuve complète précédente et au moins 300 secondes après son reçu serveur,
y compris après redémarrage ou entre deux recettes. Le premier lancement attend
aussi si une publication externe vient de fournir cette preuve pendant drainage.
Une confirmation ancienne sans diagnostics, un échec ou un résultat incertain
bloquent les étapes suivantes. Il n'existe aucun retry automatique de recette.

La preuve exige `CONFIRMED`, `own_status_verified`, Android 0.4.15 minimum,
`service_ready=true`, l'étape finale `own_status_verification` ou `complete`,
`provider_package=whatsapp_business`, `verification_method=recent_visible`, et
`expected_count == selected_count == verified_count == quantité figée attendue`.
Une étape `preflight`, la méthode historique `recent_rows` ou des compteurs seuls
ne suffisent pas. La preuve décrit l'observation de l'agent : elle n'atteste pas
indépendamment l'identité du compte WhatsApp, la veille ou l'autonomie complète.

L'exécuteur doit être Android 0.4.15 ou ultérieur, connecté, autorisé et lié au
profil exact ; aucune retombée vers Windows n'est permise. Facebook et les autres
adaptateurs non validés sont refusés dès création. Les gardes de sélection de
destination et de baseline de l'agent restent inchangés.

## Libération et reprise

Annuler ne modifie ni scheduler ni jobs. Une recette démarrée garde le verrou
jusqu'à libération explicite ; la libération exige zéro tentative non terminée
pour le propriétaire. Libérer un brouillon jamais démarré ne touche pas le
scheduler ou le verrou d'un autre plan.

Libérer une recette démarrée désactive le scheduler sans toucher ses définitions,
son scope, sa génération ni l'historique. Le statut initial est conservé pour audit.
La borne de reprise est au moins l'heure de libération et, après réussite, le
dernier reçu complet plus 300 secondes. Aucune reprise n'est déclenchée.

Une reprise automatique explicite exige une recette entièrement réussie à la
même révision couvrant toutes les lignes du scope choisi. Valider une ligne ne
valide pas d'autres profils, lignes ou Facebook. Le mode `manual` est refusé à
la reprise ; le mode `auto` repart d'une borne future, sans rattraper l'intervalle
de pause. Restaurer l'ancienne borne temporelle serait un rattrapage implicite
et n'est donc pas assimilé à restaurer les définitions du planning.

## Maintenance et validation

L'observateur existant ajoute `manual_validation` contract_version 1, uniquement
si les tables sont présentes. Cet agrégat exclut identités, profils et albums :
état, démarrage, verrou, nombres d'étapes et de preuves, tentatives non terminées,
échéance minimale, borne de reprise, disponibilité auto et violations d'intervalle.
L'absence de contrat reste inconnue, pas saine. Les occurrences planifiées durant
un intervalle de recette réellement démarrée portent `manual_recipe_hold` ; les
retards antérieurs, échecs et résultats incertains ne sont pas masqués.

Tests synthétiques : `test_control_recipes.py`, `test_recipe_progress.py`,
`test_recipe_resume.py`, `test_recipe_proof.py`, `test_recipe_observation.py`.
Ils couvrent idempotence concurrente, propriété/origine, drainage et reçus tardifs,
version native, refus Facebook, preuves insuffisantes, espacement persistant,
scope de reprise, historique inchangé et agrégat sans données privées.
Les essais sur téléphones et les publications réelles sont une validation séparée.
