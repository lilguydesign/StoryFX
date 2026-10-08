# StoryFX — diagnostic du 8 octobre 2026

## Portée et concurrence

Source officielle : dépôt StoryFX existant. Le moteur Windows/Appium/USB actif
doit être préservé. Aucune session téléphone concurrente, installation, reprise
ou publication réelle de validation avant confirmation de Jerry que ce moteur
est en pause, puis vérification de l'absence d'exécuteur concurrent.
Les résultats confirmés, incertains ou déjà repris ne sont jamais rejoués.

Le chantier a été déclaré « du 3 octobre » ; le chat initial a débuté le
4 octobre à 00:54:13.519 Africa/Douala. Ces deux repères sont distincts.

## Preuves revalidées

Lecture DB02 du 8 octobre vers 06:44 Africa/Douala : backend
`3e0671ab1b30a886ab1acb1d754d75bb05f8688b`, observation active et fraîche,
trois confirmations d'agent, huit occurrences en échec avant envoi,
une occurrence incertaine et 46 occurrences sans adaptateur validé.
Les agrégats comptent l'état le plus récent d'une occurrence ; une tentative
parente échouée puis reprise demeure dans l'audit des tentatives.
Dernière confirmation d'agent : échéance du 8 octobre à 06:40 Douala,
trois images. Ce signal ne prouve ni le bon compte ni l'absence de concurrence.

FE : version 0.4.12, publication autorisée, contact récent. Plus : 0.4.10,
contact récent, publication WhatsApp désactivée. Les quatorze lignes Facebook
(sept CM et sept CI) sont conservées. Les versions sont celles de la dernière
observation ; l'ancienne version n'était pas enregistrée dans chaque tentative.

Le dernier échec avant cette lecture concerne neuf images le 8 octobre à
03:40 Douala, `own_status_unavailable`. L'incertain du 7 octobre à 11:40
Douala demeure exclu de tout rejeu. Aucune capture de panne historique ne peut
être reconstruite depuis un écran observé plus tard.

## Quantités et équivalence

| Catégorie de programmation | Images/médias multi | Intro additionnelle |
| --- | ---: | ---: |
| Hurry+Images | 11 | 1 |
| Motivations_Stories | 9 | 0 |
| Never_Give_Up+Images | 11 | 1 |
| Images_Dubai | 11 | 0 |
| Video_Dubai | 11 | 0 |
| Advices_Stories | 5 | 0 |
| Before_After | 3 | 0 |

Les valeurs matrice et `albums.count_per_post` concordent actuellement.
Le moteur Windows donne priorité au paramètre album ; le serveur lit la matrice.
Cet écart latent reste documenté : changer le calcul ou les identités historiques
en cours de rattrapage exige une migration contrôlée, pas une réécriture implicite.
Une intro seule vaut un média ; une intro+multi avec onze vaut douze médias.

La référence Windows fonctionnelle est la transmission du 3 octobre, pas les
anciens fichiers de la racine. Elle possède Gallery, profils de pages Facebook,
TikTok et rapports historiques. Le pont Windows web reste limité au pilote
WhatsApp multi. Le service Android n'est donc pas un port complet de Windows.
Les dix rubriques web sont conservées : Launcher, Pages, Profiles, Devices,
Systems, Matrix, Albums, Programmation, Locators et Reports. Le catalogue web
Locators importé était vide ; les sélecteurs natifs sont du code validé.
Les rapports Windows fondés sur un clic et une quantité demandée ne démontrent
pas à eux seuls le nombre finalement publié. Les partages automatiques de
publications de page Facebook ne sont pas des preuves StoryFX.

## Corrections du candidat 0.4.14 / code 19

- Navigation bornée sur écrans explicitement reconnus ; attente de rendu,
  choix exact Mon statut, absence de clic répété et refus des écrans inconnus.
- Vérification des lignes récentes terminées ; le compteur global de la
  collection seul n'est plus une preuve de publication complète.
- Diagnostics fermés persistés avec la tentative et transmis avec le résultat :
  version, étape, réseau, service, durée et quantités attendue/sélectionnée/vérifiée.
- Rapports datés en Africa/Douala avec liens de tentative, distinctions entre
  confirmation agent, échec avant envoi, incertain, attente et non pris en charge.
- Les preuves historiques ne sont pas enrichies rétroactivement par des
  observations nouvelles. Les résultats terminaux restent immuables.
- Motifs distincts pour Android indisponible, autorisations, capacités médias,
  conflit d'exécuteurs et pont Windows déconnecté, sans modifier l'éligibilité.
- Sonde de résultats raccordable au collecteur Maintenance existant, sans
  publication ni reprise et sans modification du quota administratif.

## Limites et recette requise

Ce candidat ne prouve pas encore l'autonomie. Facebook et TikTok natifs restent
non implémentés. La conversation ou le lecteur WhatsApp repris dans un état non
reconnu nécessite une observation physique contrôlée pour ajouter un parcours
précis ; aucun sélecteur de destinataire n'est élargi pour forcer le succès.

Le service a un timer de vingt secondes, mais le verrou de réveil est acquis
après réception d'une tâche. Le worker périodique est un diagnostic. Ces
mécanismes ne garantissent pas l'exécution en veille profonde : Android diffère
les accès réseau et les tâches dans Doze.
Référence : [documentation Android officielle](https://developer.android.com/training/monitoring-device-state/doze-standby).

Après pause Windows confirmée : vérifier le téléphone/profil et le compte/page,
installer uniquement la nouvelle version signée sans remplacer l'ancienne sous
son numéro, observer le parcours inconnu sans publier, puis valider une prochaine
échéance non tentée avec quantité complète. Valider ensuite démarrage, écran
éteint, veille profonde et changement Wi-Fi/mobile, sans PC/USB. Ne pas confondre
installation, heartbeat, HTTP 200 ou confirmation d'agent avec cette recette.

La diffusion publique de l'APK, son installation et la recette sont des étapes
distinctes. Les résultats et éventuels blocages de livraison sont consignés dans
le rapport local final et les reçus de déploiement, jamais supposés depuis ce texte.
