# Choix d'architecture StoryFX — 4 octobre 2026

## Avis sur la direction

Garder Python est pertinent. Le problème principal est la dépendance au PC et
au transport ADB, pas la vitesse du langage. Les configurations déclaratives,
les règles horaires, l'introduction suivie des images et les règles de reprise
constituent du travail utile à préserver. Réécrire tout le produit perdrait ces
acquis sans résoudre automatiquement les permissions Android.

Le serveur central garde les comptes, plans, occurrences, résultats et médias
nécessaires aux jobs. L'agent Kotlin installé sur chaque téléphone initie ses
connexions HTTPS. Une identité d'installation persistante remplace l'IP comme
identifiant. Une connexion utilisateur permettra l'enrôlement ; elle ne doit
pas obliger le téléphone à envoyer son mot de passe à chaque synchronisation.

Le tableau de bord web sert aussi de base à la future version desktop.
Une enveloppe installable pourra être choisie lorsque le dashboard sera stable,
sans créer un second moteur métier. PostgreSQL est prévu pour la production
multiutilisateur ; SQLite sert ici de socle transactionnel local vérifiable.

## Ce que montre l'audit

Le moteur actuel dépend de PySimpleGUI, ADB, Appium, de chemins Windows et de
parcours de Galerie Samsung. Déplacer l'EXE ou Appium sur un serveur ne crée
pas un agent Android. Appium reste utile comme référence et outil de test.

Le scheduler actuel bloque pendant chaque tâche et peut manquer un autre
créneau. Certaines identités de déduplication sont en mémoire et ne séparent
pas tous les parcours. Plusieurs helpers de plateformes peuvent retourner
après un bouton absent ; le nombre prévu est ensuite marqué comme envoyé.
Le dashboard doit donc distinguer sélection, envoi déclenché et publication
confirmée. Un retour sans exception n'est pas une preuve de publication.

Un ancien secret de déverrouillage est codé dans la transmission. Il n'est
jamais repris dans le nouveau produit. Le nouveau moteur doit attendre un
déverrouillage autorisé et ne pas contourner le verrou sécurisé.

## Premier jalon implémenté

- Association temporaire à usage unique ; jeton d'installation révocable,
  stocké comme empreinte serveur et chiffré par Android Keystore sur le téléphone.
- Diagnostics datés, fenêtre d'exécution, clé d'occurrence unique et transactions.
- Un seul diagnostic actif par installation ; un état incertain bloque la reprise.
- Bail de 120 secondes, renouvelable et borné par l'échéance du job.
- Journal Android enregistré avant transmission ; `event_id` identique à la reprise.
- Événements dédupliqués durablement, y compris après redémarrage du serveur.
- Résultat tardif du même bail accepté pour résoudre un diagnostic à examiner.
- Annulation propriétaire d'un diagnostic incertain, avec invalidation du bail.
- Aperçu du planning historique, sans activation ni reprise de publication.

L'identité est celle d'une installation. La preuve que plusieurs profils
représentent le même téléphone physique reste une condition de migration.
Le protocole ne contient ni script, ni commande shell, ni sélecteur fourni
par le serveur ; la seule tâche acceptée est `diagnostic`.

`DIAGNOSTIC_CONFIRMED` signifie que l'agent a exécuté son contrôle et acquitté
le protocole. Il ne signifie jamais qu'une Story a été publiée.

## Agent et limites Android

Un futur exécuteur local sera déterministe, activé volontairement et visible.
Les XPath Appium devront être adaptés aux éléments Android natifs.
Ne pas démarrer par un service `dataSync` permanent : Android 15+ limite ces
services en arrière-plan à six heures par période de 24 heures.

WorkManager permet une synchronisation persistante, avec un minimum de quinze
minutes et des délais système possibles. Un push pourra accélérer la découverte
des jobs, avec une récupération périodique. Ni l'un ni l'autre ne garantit une
publication exactement à la seconde. Un téléphone sans réseau, verrouillé ou
sans autorisation doit afficher un état précis plutôt qu'un faux succès.

Après un redémarrage, le stockage protégé par les identifiants utilisateur est
accessible après le premier déverrouillage. Une disponibilité permanente et la
tolérance horaire devront être mesurées sur les téléphones réellement utilisés.

## Plateformes

Étudier les API officielles pour les comptes éligibles. La documentation Meta
Instagram distingue notamment les Stories des comptes Business dans le parcours
Facebook Login. Aucune API publique de publication de « Mon statut » WhatsApp
n'a été identifiée dans les sources officielles consultées ; `statuses` dans
Cloud API concerne la livraison des messages. Les Pages Facebook ont une piste
API dédiée, dont l'éligibilité exacte reste à revalider avant intégration.

Le premier pilote doit se limiter à un téléphone et une plateforme, puis
prouver envoi, résultat, perte réseau et absence de doublons. L'activation ou
l'essai d'une publication réelle reste soumis à une demande explicite portant
sur la destination et le contenu. La demande de démarrer ce chantier n'en lance aucune.

## Albums en dernier

Préparer un média nécessaire à un job est différent de synchroniser toutes les
galeries. Le chantier final utilisera une bibliothèque serveur versionnée,
empreintes SHA-256, téléchargement reprenable, fichiers temporaires puis
intégration MediaStore dans les albums. Les ajouts seront synchronisés ; la
politique de suppression devra être explicite. Le serveur n'aspirera pas la
galerie personnelle complète par défaut.

## Références techniques vérifiées

- [ADB](https://developer.android.com/tools/adb)
- [WorkManager](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work)
- [Limites services Android](https://developer.android.com/develop/background-work/services/fgs/timeout)
- [Keyguard](https://developer.android.com/reference/android/app/KeyguardManager)
- [Direct Boot](https://developer.android.com/privacy-and-security/direct-boot)
- [AccessibilityService](https://developer.android.com/guide/topics/ui/accessibility/service)
- [Politique Google Play](https://support.google.com/googleplay/android-developer/answer/10964491?hl=en)
- [FCM](https://firebase.google.com/docs/cloud-messaging/android-message-priority)
- [Collection Meta Instagram](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [Collection Meta WhatsApp](https://www.postman.com/meta/whatsapp-business-platform/collection/wlk6lh4/whatsapp-cloud-api)
- [Page Stories API — accès documentaire non vérifié](https://developers.facebook.com/docs/page-stories-api/)
- [Transactions SQLite](https://www.sqlite.org/lang_transaction.html)
- [Déploiement FastAPI](https://fastapi.tiangolo.com/deployment/concepts/)
