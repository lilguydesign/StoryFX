# StoryFX — chantier Internet, premier jalon

Ce jalon conserve le moteur Python existant comme référence et démarre une
orchestration indépendante de l'adresse ADB : API Python/FastAPI, file SQLite
persistante, tableau de bord web et agent Android Kotlin. Il exécute uniquement
des diagnostics synthétiques. Il ne publie aucun statut ou message.

La transmission du 3 octobre est conservée intégralement dans `transmission/`,
hors Git et hors livraison publique. C'est la référence actuelle du moteur
Windows, avec des corrections non présentes dans la vieille branche Git.
Les anciens fichiers Python à la racine reflètent cette branche historique et
ne sont ni lancés ni modifiés par le nouveau serveur.

## Démarrer le socle local

Depuis `C:\FormaFX Group\storyfx` :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server\requirements-lock.txt
.\Start_StoryFX_Diagnostic.ps1
```

Ouvrir `http://127.0.0.1:18743/dashboard/?demo=1` pour l'aperçu sans secret.
Le mode connecté demande une clé de validation locale créée dans le dossier
privé `.runtime\private`. La clé reste en mémoire dans le navigateur ; ne pas
la partager ni la capturer. Le serveur écoute uniquement sur localhost.
Cette clé de laboratoire ne remplace pas la future connexion FormaFX par compte.

```powershell
.\.venv\Scripts\python.exe -B -m pytest server\tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B server\tools\smoke_diagnostics.py
.\.venv\Scripts\python.exe -B server\tools\maintenance_local.py
```

Le dashboard peut créer un code d'association de dix minutes, programmer un
diagnostic, révoquer une installation et examiner le planning ancien. L'import
est un aperçu inactif ; il ne crée aucun plan ni job de publication.

## Prochaines étapes

1. Authentification des comptes FormaFX, permissions par appareil et HTTPS
   sur un service serveur isolé ; remplacer l'accès de laboratoire.
2. Enrôler un téléphone pilote puis vérifier changement Wi-Fi/mobile,
   redémarrage, veille et journal local ; aucun besoin d'USB pour le protocole.
3. Valider un parcours Android déterministe, visible et volontairement autorisé,
   puis une publication explicitement demandée avec une preuve du résultat.
4. Porter les plans et les checkpoints intro/images ; basculer le planning
   après coordination avec le scheduler Windows pour éviter les doublons.
5. Finaliser le dashboard et sa version desktop à partir de la même interface.
6. Ajouter en dernier la bibliothèque centrale et la synchronisation des albums.

Architecture et limites : `docs\internet\ARCHITECTURE.md`.
Recette et livraison : `docs\internet\VALIDATION.md`.
