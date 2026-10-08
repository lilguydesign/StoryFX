# Recette manuelle des publications

La recette vérifie des lots distincts du calendrier. Elle ne constitue pas une
preuve d'autonomie sans ordinateur, d'identité du compte, de fonctionnement en
veille ou de disponibilité de Facebook natif.

## Conditions physiques

Avant une installation ou un essai réel, obtenir la confirmation de pause du
moteur Windows/USB, puis contrôler l'absence de concurrence. Un téléphone branché,
un PID absent ou une file serveur vide ne prouve pas une pause durable.

Ne pas arrêter ADB/Appium ni un runner en cours. Les commandes historiques
« Arrêter scheduler », « Stopper » et « Quitter » peuvent interrompre les tâches.
Conserver les journaux, la progression du rattrapage et les réponses différées.

La préparation web ne commande pas le moteur Windows historique. Son verrou ne
protège que les nouvelles réservations réalisées par le serveur StoryFX.

## Parcours de recette

1. Sélectionner les lignes éligibles et vérifier destination, mode et quantité.
2. Créer un brouillon : aucune publication et aucun verrou.
3. Après pause externe confirmée, démarrer la préparation. Les tâches déjà en
   attente ou engagées terminent normalement ; aucune n'est annulée.
4. Attendre un état prêt, puis demander explicitement une seule publication.
5. Examiner le résultat. La prochaine étape reste bloquée jusqu'à une preuve
   complète et au moins cinq minutes après son enregistrement terminal.
6. Déclencher explicitement chaque étape suivante. Aucun compte à rebours ne
   déclenche lui-même un envoi.
7. Une erreur ou une incertitude bloque la recette. Examiner la publication
   existante ; ne pas rejouer le lot pour obtenir un résultat plus favorable.
8. Clore la recette lorsque les tentatives engagées sont terminées. La
   planification reste arrêtée jusqu'à un démarrage automatique explicite.

L'annulation ferme les étapes futures sans interrompre la publication engagée.
Le serveur conserve le plan, ses tentatives et les anciennes occurrences.
Les clés idempotentes évitent qu'un double clic ou une réponse réseau perdue
réserve une seconde tentative. Une recette ne réutilise pas `/retry`.

## Preuve acceptée pour un lot Android

L'agent doit être compatible, connecté, prêt et associé au profil attendu.
Un pont Windows disponible ne remplace pas cet exécuteur Android.

Le résultat doit être `CONFIRMED`, avec `own_status_verified`, les mêmes quantités
attendue, sélectionnée et vérifiée, et la méthode `recent_visible`. Une ancienne
confirmation sans ces diagnostics ne valide pas l'étape.

Le contrôle Android exige le lot achevé dans une même observation. Les positions
de la liste ne sont pas des identités stables entre plusieurs pages. Une
pagination ne suffit donc pas à prouver un grand lot. Ne pas réduire ni
fractionner les quantités configurées pour faire passer le contrôle.

Le compte WhatsApp reste à vérifier physiquement : `account_verified=false`
ne doit jamais être présenté comme une identité validée.

## Destinations et exclusions

Le canal WhatsApp autorisé pour cette recette est FE. Plus WhatsApp reste désactivé.
Les profils Facebook CM et CI, leurs pages et leurs calendriers sont conservés.

L'adaptateur natif Facebook n'est pas implémenté. Ces lignes restent indiquées
comme non prises en charge ; un essai WhatsApp réussi ne valide pas Facebook.
Le moteur Windows historique ne convient pas tel quel : ses reprises après
erreur et sa sélection de page non bloquante doivent être corrigées et vérifiées
avant une utilisation réelle. TikTok natif reste également non implémenté.

## Retour à la planification

La sortie ne relance aucun créneau écoulé pendant la recette. Un redémarrage
explicite utilise une borne future et respecte les lignes effectivement validées.
Ne pas restaurer l'ancienne heure de départ pour produire un rattrapage implicite.

La recette physique, la veille prolongée, le redémarrage et le fonctionnement sans
USB sont des validations distinctes. Un HTTP 200 ou un timer actif ne les prouve pas.

## Confidentialité et maintenance

Les rapports utilisent des compteurs et des motifs fermés. Ne pas y inclure
d'identifiants matériels, d'albums privés, de sessions, de codes ou de PIN.
Les alertes Maintenance gardent leur quota global et ne déclenchent aucun rejeu.
L'observation périodique reste sans envoi et conserve sa fenêtre de sept jours.
