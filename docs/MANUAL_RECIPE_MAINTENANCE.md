# Recette manuelle StoryFX et Maintenance — 8 octobre 2026

Le mécanisme est préparé localement ; aucune recette réelle n'est activée par ce travail.
Le serveur publie un agrégat `manual_validation` version 1 dans la dernière observation
du fichier privé `observation-state.json`. La sonde ne lit que cet artefact, sans API,
SQLite, téléphone, commande de lancement, rôle ou permission supplémentaire.

Le brouillon DRAFT n'a aucun effet. Le démarrage explicite pose un verrou persistant
qui bloque les nouvelles réservations et laisse finir les tâches préexistantes.
Chaque étape Android nécessite ensuite une action explicite. La suivante attend au
moins 300 secondes après la preuve complète de la précédente. Un résultat incertain,
un échec ou une preuve incomplète bloque la recette, sans rejeu. La libération attend
l'absence de tâche pendante et laisse le scheduler désactivé avec une borne future.
Une reprise du scheduler reste une action explicite distincte.

La sonde `storyfx_manual_recipe_probe.py` est raccordée au collecteur canonique SendFX
par deux lignes, après la sonde de publication existante. Les contrôles historiques
ne sont pas modifiés. Installation et passage planifié de cette nouvelle sonde en
production restent non vérifiés avant leur reçu dédié.

Les états absents, DRAFT, DRAINING, READY, COOLDOWN et les autres attentes manuelles
ne sont pas des retards automatiques. Une preuve récente `state=none` indique
normalement qu'aucune recette n'est configurée. Un schéma absent, une lecture limitée
ou une preuve âgée de plus de 40 minutes reste inconnue. Même une observation
historique terminée ne prouve pas l'état actuel de la recette.

Incidents détectés : incohérence de verrou, étape incertaine ou échouée, preuve
incomplète, état BLOCKED, incohérence PASSED et violation du délai minimal observée.
Le signal est actualisé par l'observateur existant toutes les 30 minutes pendant sa
fenêtre bornée. Après sa fin, un nouveau contrôle de source doit être préparé et
vérifié ; cette sonde ne relance pas l'observation et ne modifie aucun calendrier.

La preuve quantifiée `recent_visible` ne certifie ni l'identité du compte, ni toutes
les conditions du téléphone, ni l'autonomie. Facebook natif demeure indisponible.
La pause Windows/USB et l'absence d'exécuteur concurrent doivent être confirmées
avant toute recette physique. Aucun identifiant privé, album ou contenu n'est émis.

L'observateur distingue `manual_recipe_hold` uniquement pour une occurrence encore
PLANNED dont l'échéance tombe dans un intervalle de verrou réellement démarré.
Cette exclusion volontaire reste historique après libération. Les retards antérieurs,
échecs et résultats incertains gardent leurs incidents ; le verrou ne les masque pas.

Les incidents conservent le regroupement et le quota global d'un WhatsApp au maximum
toutes les deux heures, avec résolution silencieuse. La limite globale existante
`CONSUMPTION_PRIVATE_READ_NOT_AUTHORIZED` demeure ; elle n'est pas un succès.
Rollback : anciens modules Maintenance et préimage du collecteur ; préserver les
verrous de recette, tâches, reçus, définitions, timers et quotas.

Validation locale : tests synthétiques de seuil, états normaux, incohérences, sortie
fermée et intégration idempotente. Aucun envoi ni test Android réel n'est effectué.
