# Exclusion durable pendant une mise à jour Android

Le remplacement de l'APK nécessite la pause Windows/USB déjà confirmée par Jerry,
aucun worker local ni session Appium et aucun travail serveur en attente ou actif.
Deux lectures d'inactivité ne ferment pas la course avec une nouvelle commande.

L'opérateur privilégié `storyfx_server.installation_operator` acquiert un verrou
SQLite par propriétaire sous `BEGIN IMMEDIATE`, après contrôle des appareils actifs,
des publications, diagnostics, recettes et de la pause du scheduler. Des triggers
refusent toute insertion et toute transition de dispatch des deux files, y compris
depuis un ancien processus. Les profils, tâches et calendriers ne sont pas modifiés.
Les lectures et heartbeats continuent. L'API traduit le refus en HTTP 409.

Le verrou persiste après fermeture SSH, timeout ADB, redémarrage API ou passage du
temps. Aucun TTL ne le libère. Un résultat d'installation ambigu impose une
réconciliation physique, sans nouvelle commande de remplacement automatique.
L'opérateur libère uniquement l'opération exacte après vérification des APK,
versions, signatures et invariants des deux appareils, avec le SHA-256 du reçu.
Une clé libérée ne peut pas être réacquise. Les entrées privées passent en mémoire
par stdin et ne figurent pas dans stdout ; le serveur conserve leur empreinte.

Rollback : libérer l'opération exacte uniquement après réconciliation des appareils,
puis revenir à la release précédente si nécessaire. Ne pas supprimer le verrou pour
forcer un remplacement ; l'ancien backend reste lui aussi bloqué par les triggers
tant que l'opération demeure active. Aucun rejeu de publication n'est autorisé.

Ce garde est une fonction opérateur, sans cadence ni notification supplémentaire.
Sa persistance et les refus concurrents sont testés sur données synthétiques ;
la recette physique et l'autonomie restent non vérifiées jusqu'aux reçus réels.
