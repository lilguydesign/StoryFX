# StoryFX — centre de contrôle et mise à jour Android

Le moteur Python historique est conservé sur Windows. Le serveur conserve les
réglages et les demandes de publication, puis le connecteur Windows les récupère
par HTTPS. Les métadonnées techniques du profil sont privées au compte propriétaire ;
leur modification ne donne aucun accès à un téléphone absent du fichier local
de confiance. Le connecteur ne redémarre ni ADB ni l’Appium historique.
Il utilise un serveur pilote séparé, uniquement en boucle locale sur le port 4743.
Un contrôleur Appium historique occupé provoque un refus avant publication.

## Configuration depuis le web

Ouvrir https://story.formafx.com/dashboard/ avec le même compte propriétaire.
Profils : nom, libellé, activation, connexion ADB, série USB, IP/port, version Android,
décalage, options Appium validées et package/activité galerie. Chaque champ est expliqué.
Le numéro de ligne et le nombre de matrices sont calculés. Tri, actualisation,
duplication et propagation aux profils du même téléphone sont disponibles.
Systèmes : heures de base ; Albums : références aux
galeries existantes ; Pages : pays et nom Facebook ; Matrices : liens entre ces
réglages. Programmation affiche les occurrences du jour en Africa/Douala.
Les modifications sont isolées par compte et contrôlées par numéro de révision.
Renommer ou supprimer une référence utilisée par une matrice est refusé.

Les métadonnées d’albums ne transfèrent pas de photos et ne créent pas de dossier
sur Android. La synchronisation des galeries reste le dernier chantier.
Les locators peuvent être enregistrés et consultés ; le pilote WhatsApp utilise
ses repères vérifiés, sans remplacement automatique par des sélecteurs non testés.

## Pilotage Windows

Depuis le dossier officiel, exécuter `Connecter_StoryFX_Web.cmd`. L’association
affiche une demande à autoriser dans Lancement > Connecter Windows. Le credential
du connecteur est stocké avec DPAPI CurrentUser dans le répertoire privé ignoré.
Le programme signale les seuls profils dont le matériel ADB est déjà disponible.

Dans Lancement, sélectionner une occurrence, vérifier sa destination et lancer.
Le pilote sécurisé prend en charge WhatsApp Business, statut personnel et moteur
multi. Les configurations Facebook, Instagram, TikTok et intro restent visibles
et modifiables ; leur exécution par ce nouveau connecteur n’est pas encore validée
et est refusée avant toute publication. Le lanceur historique conserve ces moteurs.
Dans Lancement, le mode Auto suit les échéances à partir de la minute actuelle.
Le mode Manuel reprend les échéances depuis l’heure choisie aujourd’hui puis suit
les prochaines échéances. Une fin facultative borne un rattrapage ponctuel, pas
le scheduler continu. La prévisualisation distingue les occurrences déjà demandées,
les moteurs non validés et les téléphones indisponibles. Le serveur vérifie toutes
les dix secondes le compte propriétaire, la révision et la présence du moteur.
Un changement de configuration ou la perte du droit propriétaire suspend le scheduler.
Le lendemain, seules les occurrences du nouveau jour sont considérées ; les anciennes
occurrences d’un jour précédent ne sont pas rejouées automatiquement.

Arrêter scheduler annule ses publications encore en attente. Stopper les tâches
annule aussi les demandes manuelles et refuse la dernière action sociale si elle
n’est pas déjà partie. Une action déjà transmise peut se terminer. Aucun arrêt
d’Appium ou d’ADB. Le terminal affiche les commandes et résultats structurés ;
Copier copie ce texte, Effacer masque l’affichage sans supprimer l’audit ni les rapports.

Une réservation durable précède les actions sur le téléphone. Une occurrence
acceptée ne peut pas être demandée à nouveau. Les confirmations réseau peuvent
être renvoyées, jamais les actions de publication. Un résultat incertain est
classé À vérifier. Les rapports distinguent les refus avant publication des statuts
confirmés. La publication du 5 octobre 2026 à 06:40 Douala, Before_After, 3 images,
est importée comme confirmée et ne doit pas être relancée.

## Android

L’agent Android conserve son rôle connexion/diagnostic ; il ne remplace pas encore
Appium pour publier sans Windows. Le nouveau téléphone pilote SM-S711B est un
Galaxy S23 FE, associé au profil historique JK650_S23.
La mise à jour interroge le lien officiel latest, impose HTTPS et le domaine
officiel, vérifie SHA-256, identité du package, version croissante et même signature.
L’installation passe par l’installateur Android avec confirmation système. Aucune
désinstallation ni suppression de données. Le récepteur de mise à jour relance
la synchronisation d’une association existante ; Android peut imposer de rouvrir
l’écran de l’application. Une installation silencieuse n’est pas promise.

## Vérification et maintenance

Tests ciblés : séparation propriétaires, Origin, champs fermés sans commandes ADB distantes,
révisions, références, fuseau, preuve d’association, absence de double demande,
réservation unique, résultat ambigu et reprise des seuls accusés de réception.
Les sondes publiques ne publient pas et n’observent pas les galeries privées.
La disponibilité d’un endpoint ne prouve pas une publication ou l’endurance Android.
Rollback : release backend précédente, pointeur APK précédent et conservation des
journaux. Ne jamais restaurer un ancien journal pour contourner une réservation.
