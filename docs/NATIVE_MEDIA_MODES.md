# Modes WhatsApp Android 0.4.13

Le mode `intro` sélectionne la première vidéo, classée par date d’ajout décroissante,
dans l’album introduction. Le mode `multi` sélectionne exactement le nombre prévu
de médias dans l’album du lot, avec repli sur l’album principal. Le mode
`intro+multi` place une vidéo d’introduction en premier, suivie du lot complet.
Un lot de 11 médias signifie donc 12 statuts au total avec l’introduction.

Les trois modes utilisent un partage Android groupé vers Mon statut WhatsApp
Business. Les URI sont ordonnées ; aucun média déjà choisi comme introduction
n’est ajouté deux fois. Le total est limité à 30. Deux dossiers ayant le même nom,
un fichier absent ou une quantité insuffisante refusent le lot entier avant envoi.
Les fichiers restent sur le téléphone. Android et WhatsApp peuvent imposer leurs
propres limites vidéo ; un résultat non vérifiable demeure incertain.

Les modes vidéo nécessitent les autorisations Photos et Vidéos, l’Accessibilité,
Internet, le profil propriétaire associé et Android 0.4.13 minimum. Les anciens
agents continuent leur mode multi images sans recevoir les nouvelles commandes.
Le moteur Windows pilote conserve son adaptateur multi existant ; Facebook,
Instagram et TikTok natifs ne sont pas implémentés par cette correction.

La date de mise en service est conservée dans `control_media_rollout`. Le scheduler
ne rattrape pas automatiquement les anciens modes nouvellement pris en charge.
Les commandes déjà demandées restent protégées par leur occurrence unique et le
journal chiffré Android. Un résultat incertain ne revient jamais dans la file.
Une révocation de l’accès vidéo bloque l’autorisation finale d’une commande vidéo.

Validation : tests de modes/comptages/ordre, collisions d’albums, quantités
insuffisantes, anciennes versions, révocation, non-rejeu et date de mise en service.
La compilation et le contrat public ne prouvent pas une publication réelle.
Les preuves de livraison et les limites du téléphone figurent dans le rapport.

Rollback : revenir au backend précédent et au pointeur APK sauvegardés. Les tables
ajoutées sont compatibles avec l’ancienne version ; conserver les historiques et
ne pas rétrograder ni effacer les données Android. Le compte, le PIN, les albums,
les horaires et la planification ne sont pas reconfigurés par le déploiement.
