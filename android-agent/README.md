# StoryFX — agent Android 0.4.15

Application native Kotlin Android 8+, connexion FormaFX sécurisée, association
chiffrée et mise à jour signée depuis la dernière version officielle.

Le pilote de publication fonctionne dans un service Accessibilité activé
explicitement par le propriétaire. Choisir le profil historique dans
StoryFX, autoriser les photos/vidéos et activer le service Android. Le serveur
conserve matrices et programmation ; le téléphone exécute les modes intro,
multi et intro+multi dans Mon statut WhatsApp Business. Facebook et TikTok
natifs restent non implémentés. Voir [le périmètre du pilote](docs/ANDROID_PUBLICATION_PILOT.md)
et [les preuves et limites 0.4.14](docs/PUBLICATION_DIAGNOSTICS_0414.md).
La [version 0.4.15](docs/PUBLICATION_VERIFICATION_0415.md) attend la fin du lot
jusqu'à la limite de temps de la tentative, sans répéter l'envoi.

Le déverrouillage local et Direct Boot disposent d'un consentement distinct,
d'un stockage chiffré et d'un essai borné ; sans cette configuration, le premier
déverrouillage Android reste manuel. La sauvegarde privée du PIN est une fonction
séparée. Un écran verrouillé, une absence d’Internet ou une permission manquante
met les tâches en attente. Aucun secret n'est inclus dans les diagnostics.

Une tâche interrompue ne rejoue jamais les gestes de publication. Le journal
AES-GCM conserve le résultat confirmé ou incertain avant son accusé serveur.
Les données privées sont exclues des sauvegardes. Aucun secret ni contenu
de discussion n’est journalisé. HTTPS/TLS standard, aucune WebView ni TLS
permissif. Les diagnostics WorkManager conservent leur cadence indicative
de 15 minutes ; le service actif interroge les commandes environ toutes les
20 secondes. Les limitations Samsung et les arrêts forcés restent à vérifier
sur chaque appareil.

Compilation : AGP 8.9.1, Kotlin 1.9.20, Gradle 8.11.1, SDK 35, JDK 17+.
Configurer le SDK dans local.properties (ignoré par Git), puis :

```powershell
.\gradlew.bat --offline :app:testDebugUnitTest :app:lintDebug :app:assembleRelease
.\scripts\build-release-signed.ps1 -Offline -SkipBuild
```

Le script contrôle le certificat historique, l’identité et les permissions
de l’APK. L’installateur Android exige toujours la confirmation système ;
aucune installation silencieuse ni autorisation de service forcée.
