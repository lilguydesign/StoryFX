# Déverrouillage du pilote StoryFX

Le pilote publie avec le moteur Windows/Appium. L'agent Android 0.3.1 assure
la connexion, les diagnostics et la recherche de mise à jour ; il ne publie
pas les stories et ne déverrouille pas seul l'écran sécurisé Android.

## Association

Dans Lancement > Connecter Windows, l'identifiant temporaire désigne une
demande du connecteur local. L'autoriser conserve un accès chiffré Windows
DPAPI pour ce compte. Brancher les téléphones ou connecter l'agent Android
ne réalise pas cette association. Une demande expirée doit être remplacée.
Le connecteur affiche un lien qui préremplit la demande, valable dix minutes.
Ce lien n'autorise aucun accès à lui seul : le bouton reste à confirmer.

## Code local

Depuis le dossier officiel StoryFX, avec le compte Windows qui exécutera
le connecteur : `python windows-bridge/configure_phone_unlock.py`.
La saisie est masquée. L'option `--import-legacy` migre le code déjà configuré
dans le moteur historique sans l'afficher ni exécuter celui-ci.

Le secret reste dans `.runtime/windows-bridge/phone-unlock.dpapi`, chiffré
pour CurrentUser et protégé par ACL. Il n'est envoyé ni au serveur, ni au
dashboard, ni à Appium. Ne jamais exporter ce fichier ou le code historique.
La configuration concerne uniquement les deux matériels des profils
historiques JK650_S23 et JK657_S23+ ; aucune nouvelle identité ADB n'est ajoutée.

Avant une publication autorisée, le moteur réveille l'écran et vérifie le
clavier PIN numérique System UI. Il saisit le code par stdin ADB, sans code
dans les arguments du processus ou les capacités Appium. Une seule tentative
est permise tant que le téléphone reste verrouillé. Un échec ou une interruption
laisse une réservation locale ; déverrouiller manuellement le téléphone permet
ensuite sa reprise. Aucune protection Android n'est désactivée.

## Publications et mises à jour

Le rattrapage respecte les réservations existantes : aucune occurrence déjà
demandée, confirmée ou ambiguë n'est rejouée. Les adaptateurs non validés sont
exclus et affichés dans la prévisualisation. Le PIN ne rend pas ces adaptateurs
opérationnels et ne remplace pas la construction du moteur autonome Android.

Sur Android : ouvrir StoryFX > Mises à jour StoryFX > Rechercher une mise à jour.
Si une version plus récente est disponible, choisir Télécharger et installer.
Les contrôles HTTPS, SHA-256, package, version croissante et signature identique
précèdent l'installateur. Android demande sa confirmation ; l'installation
silencieuse n'est pas promise. Les données et l'association sont conservées.

Le téléchargement officiel utilise la dernière version publiée :
https://api.formafx.com/functions/v1/storyfx-agent-download?platform=storyfx_agent_android&channel=stable&version=latest&asset_type=apk
