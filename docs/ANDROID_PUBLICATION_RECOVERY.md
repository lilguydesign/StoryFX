# Reprise du pilote Android — 6 octobre 2026

Les deux installations existantes peuvent être conservées : aucune déconnexion,
aucune réassociation forcée et aucun effacement des réservations chiffrées.
L’autorisation Android s’active par le bouton natif « Configurer l’Accessibilité
StoryFX », puis les écrans système normaux. L’application ne change pas les
paramètres sécurisés elle-même et ne désactive pas Play Protect.

Le code de déverrouillage du propriétaire reste dans son stockage DPAPI existant,
lié aux deux matériels ; il n’est ni transmis au serveur ni incorporé dans l’APK.
Le pilote natif ne contourne pas l’écran de verrouillage. Après un redémarrage,
Android réassocie le service après le premier déverrouillage. Ce parcours de
reboot physique reste à vérifier séparément.

## Diagnostic et reprise

Android 0.4.2 distingue les étapes d’échec avec des codes fermés : album,
ouverture du fournisseur, navigation, liste des statuts, sélection et aperçu.
Aucun texte d’une conversation, image, destinataire ou exception privée ne
quitte le téléphone. Les libellés d’interface acceptent les textes et les
descriptions d’accessibilité exacts, avec une seule cible interactive.

Une tentative est considérée incertaine dès la première flèche d’envoi du
sélecteur. Même si une future version de WhatsApp saute l’aperçu, une erreur
après cette flèche ne peut donc pas devenir une permission de rejeu.

« Rapports → Réessayer après correction » crée une nouvelle tentative explicite
uniquement pour un échec prouvé avant toute flèche d’envoi. Le résultat original
reste inchangé. Un parent ne peut avoir qu’un successeur ; les répétitions de
requête sont refusées. La planification, l’album, le nombre, le profil, la journée,
les droits actuels et la disponibilité native sont revalidés côté serveur.
Le résultat de la dernière tentative apparaît dans la programmation.

Une erreur générique ancienne `preflight_refused`, une transition après le
sélecteur, un résultat incertain ou une publication confirmée ne sont pas
éligibles. Le scheduler ne crée pas de reprise automatique et les journaux
locaux continuent à refuser la même occurrence.

Les champs JSON facultatifs null sont lus explicitement. Android convertit la
sentinelle JSON en texte `null`, contrairement à la bibliothèque des tests JVM :
[source Android](https://android.googlesource.com/platform/libcore/+/refs/heads/main/json/src/main/java/org/json/JSONObject.java).
Ce correctif de compatibilité est testé avec le JSON Android réel par la sonde
synthétique `platform-tests/AndroidJsonPolicyProbe.java`. Aucun accès aux photos,
compte, écran ou réseau n’est nécessaire pour cette sonde.

## Maintenance et limites

Sonde réelle : `storyfx_control_probe.py`, intégrée au collecteur existant.
Le contrat HTTPS expose la disponibilité de la reprise et des étapes d’échec.
Cela ne prouve pas qu’une story a été publiée : seuls les résultats privés
`CONFIRMED / own_status_verified` et leur relecture le permettent.
La détection horaire des erreurs d’interface des téléphones n’est pas couverte
par cette sonde publique ; les rapports privés sont contrôlés dans cette tâche.

Déclencheurs : scheduler explicitement lancé, poll natif toutes les 20 s,
reprise manuelle explicite. Fuseau Africa/Douala, stockage UTC ; présence 45 s,
réservation incertaine après 900 s. Aucune modification des timers, destinataires
ou quotas de maintenance, et aucune notification envoyée par la validation.
Exclusions normales : écran verrouillé, service désactivé, réseau absent,
absence d’échéance, vidéos, autres fournisseurs et résultats à vérifier.

Réparation : vérifier le motif avant envoi, corriger le téléphone et reprendre
seulement si le bouton est éligible. Rollback : backend et pointeur APK précédents,
sans restaurer un ancien journal pour rejouer des publications. Template : logo
officiel StoryFX ; livraison d’alerte non revalidée par ce chantier.
Les preuves d’installation, de contrats, de sondes et de publication physique
sont distinctes dans le rapport de livraison ; ne pas les déduire d’un build.
