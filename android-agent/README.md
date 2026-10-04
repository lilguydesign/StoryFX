# StoryFX — agent Android diagnostic 0.1.0

Application Android native Kotlin, Android 8+ ; aucune WebView.
Cette première livraison valide l’enrôlement, les heartbeats, la prise d’une tâche
diagnostic et la reprise d’événements après une coupure. Elle ne publie aucun statut.
Elle ne demande aucun accès aux albums, à l’Accessibilité ou au partage d’écran.

## Parcours

1. Créer un code à usage unique dans le tableau de bord StoryFX.
2. Saisir le serveur HTTPS racine et ce code dans l’agent ; le nom du téléphone
   est détecté automatiquement et peut être modifié avant association.
3. Enrôler puis synchroniser. La batterie et l’état verrouillé sont transmis.
4. WorkManager relance environ toutes les 15 minutes si le réseau est disponible.
   Android peut reporter l’exécution en veille ; aucune cadence exacte n’est garantie.
5. Supprimer l’association efface la liaison locale et annule sa tâche périodique.
   La révocation serveur se fait séparément dans le tableau de bord.

## Transport et stockage

HTTPS, validation TLS Android standard, aucun suivi de redirection.
Seul le build debug permet HTTP vers `10.0.2.2`, pour un émulateur isolé.
Le build release refuse tout HTTP. Aucun certificat permissif ni TLS désactivé.
L’UUID d’installation est stable jusqu’à suppression des données/désinstallation.
Le jeton et l’outbox sont chiffrés AES-GCM avec une clé Android Keystore.
Les préférences privées sont exclues des sauvegardes. Aucun secret n’est journalisé.

Les deux événements STARTED et DIAGNOSTIC_CONFIRMED sont persistés avant le premier
appel réseau. Chaque reprise conserve son UUID et son jeton de lease, et aucune
nouvelle tâche n’est réclamée tant que l’outbox reste non résolue. Les tâches d’un
autre appareil ou d’un autre type sont refusées. Le backend doit reconnaître les
réessais identiques même après expiration et autoriser la résolution tardive de
NEEDS_REVIEW avec le même jeton de tentative non remplacé.

## Compilation

AGP 8.9.1, Kotlin 1.9.20, Gradle 8.11.1, SDK 35, JDK 17+.
Configurer `local.properties` avec le chemin SDK ; ce fichier est ignoré par Git.

```powershell
.\gradlew.bat --offline :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:assembleRelease
```

Le debug APK est destiné aux essais synthétiques. Le release APK reste non signé
et n’est pas une publication. La signature et le déploiement ne sont pas inclus.
Le numéro de version/protocole est `0.1.0` ; executor = `diagnostic`.

WorkManager 2.9.0 est une dépendance publique Google résolue à la compilation.
Un premier build sur une machine sans son cache nécessite l’accès à Google Maven.
