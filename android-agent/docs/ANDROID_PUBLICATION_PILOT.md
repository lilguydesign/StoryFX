# Agent Android autonome — pilote 0.4.0

Le serveur conserve la programmation. L'agent Android associé au compte
propriétaire récupère les tâches avec sa propre identité d'installation.
Dans l'application, choisir le profil existant, enregistrer l'activation puis
accorder les photos et activer soi-même l'Accessibilité StoryFX dans Android.
Les accès ne sont jamais accordés par ADB, ni à la place de l'utilisateur.

Le pilote ne gère que les albums d'images WhatsApp Business, moteur multi,
de 1 à 30 images, destination Mon statut, audience Contacts. Aucun message
à un contact, page Facebook, vidéo, moteur intro ou compte non associé.
Un album absent, ambigu, inaccessible ou trop petit bloque la publication.
Les images restent sur le téléphone ; les journaux remontés ne contiennent
ni photos, ni discussions, ni contenu de l'écran, ni code de verrouillage.

Android gère la durée de vie du service d'Accessibilité activé et le reprend
après redémarrage. Après un reboot, le premier déverrouillage est nécessaire
pour accéder au stockage chiffré. Le récepteur boot/unlock remet la tâche de
diagnostic en place sans forcer l'ouverture d'une activité. Aucun accès
Accessibilité n'est activé automatiquement. Une fermeture forcée par Android
ou l'utilisateur, des restrictions Samsung ou une révocation restent possibles.

Le service interroge le serveur environ toutes les 20 secondes lorsqu'il tourne.
L'écran doit être allumé et déverrouillé ; sinon la file serveur attend.
Une coupure réseau empêche le départ et l'autorisation précédant chaque geste.
Chaque tâche est réservée dans un journal local AES-GCM/Android Keystore avant
toute interaction sociale. Après interruption, seule l'accusé de résultat est
retenté : jamais les gestes de publication. Un résultat ambigu nécessite une
vérification humaine. La même occurrence ne peut être exécutée par Windows
et Android ; un téléphone ne reçoit pas deux gestes concurrents.

La confirmation exige une liste Mon statut sans statut « À l'instant » avant
l'envoi, une sélection unique Mon statut, l'audience Contacts avant le bouton
final, puis exactement le nombre attendu de nouveaux statuts dans la liste
du propriétaire. Une évolution d'interface WhatsApp peut refuser le parcours.
Une acceptation de tâche ou un scheduler actif ne prouve pas une publication.

Les tests synthétiques ne prouvent pas le fonctionnement sur un téléphone
physique. La livraison doit distinguer tests de protocole/journal, installation,
permissions humaines, publication réelle et reprise après reboot réellement
observées. Les sondes publiques ne lisent pas les journaux des téléphones.

Retour arrière : arrêter le scheduler et désactiver le pilotage dans l'agent,
revenir au backend précédent et au pointeur APK précédent. Conserver les
associations chiffrées et les réservations confirmées/ambiguës. Une ancienne
version ne reçoit aucun privilège native via les endpoints Windows.

Références :
- https://developer.android.com/guide/topics/ui/accessibility/views/service
- https://developer.android.com/training/data-storage/shared/media
