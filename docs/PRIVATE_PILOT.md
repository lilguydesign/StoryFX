# StoryFX — pilote privé Internet, 0.2.0

Le back-office principal est https://story.formafx.com. Le moteur Python tourne sur
DB02 dans un conteneur dédié ; l'ordinateur Windows de Jerry n'est plus nécessaire
au fonctionnement de ce moteur. L'agent Android interroge ce moteur via HTTPS.
Il n'y a pas d'application Windows supplémentaire à installer pour ce jalon.

## Périmètre livré

- Connexion avec le compte FormaFX existant : mot de passe, OTP, réinitialisation
  après OTP récent et SSO central. Aucun compte StoryFX concurrent n'est créé.
- Accès réservé aux propriétaires FormaFX actifs définis par PriceFX, vérifié
  côté serveur sur l'identité GoTrue, les suspensions et l'état du compte.
- Flotte et jobs isolés par compte. Les appareils hérités du laboratoire restent
  dans le propriétaire de validation et ne sont jamais adoptés automatiquement.
- Association Android par consentement explicite, PKCE S256, nonce et ticket
  temporaire à usage unique. Aucun JWT ni mot de passe dans les URLs.
- Révocation d'un téléphone, file de diagnostics, historique, reprise et
  journal Android durable des accusés de réception.
- APK signé disponible sur apps.formafx.com/storyfx ; le bouton de téléchargement
  résout la dernière version depuis le catalogue serveur, sans version figée.

## Installer et associer un téléphone

1. Télécharger l'APK depuis la page StoryFX, puis l'installer sur Android.
2. Ouvrir StoryFX, nommer le téléphone et choisir la connexion FormaFX.
3. Se connecter sur la page complète, puis autoriser ce téléphone affiché.
4. Revenir dans l'agent et vérifier le serveur et l'état de connexion.
5. Dans le dashboard, lancer seulement un diagnostic pour cette étape.

La connexion utilise Internet ; USB et Wi-Fi commun ne sont pas requis. Android
peut retarder les tâches en arrière-plan avec Doze et les restrictions constructeur.
WorkManager est une planification différée, pas une horloge exacte. Les résultats
durables évitent de rejouer aveuglément un travail déjà démarré.

Fermer ou déconnecter le dashboard ne révoque pas les agents associés. Pour
retirer un téléphone, utiliser sa révocation dans la flotte. Une perte d'accès
propriétaire, une suspension ou une session FormaFX non renouvelable bloque les
commandes suivantes et nécessite une nouvelle association si la session expire.

## Limites conservées explicitement

La publication autonome des stories WhatsApp/Facebook/Instagram n'est pas
implémentée. Le pilote exécute exclusivement des diagnostics synthétiques.
Il ne demande pas le service Accessibilité et ne publie aucun contenu réel.
Les visuels marketing illustrent la direction du produit ; la capture synthétique
du dashboard est identifiée comme telle.

Le planificateur et les anciens albums sont documentés dans le jalon 1. Le
nouveau dashboard n'adopte pas automatiquement leurs appareils ni leurs tâches.
La prévisualisation d'import des anciennes configurations reste un outil local
de préparation. La synchronisation des galeries et albums reste la dernière étape.

Les tests de ce jalon vérifient les contrats, les refus et les diagnostics.
Un téléphone personnel en conditions réelles et une endurance de plusieurs jours
ne sont pas assimilés à la validation sur émulateur.

## Livraison et rollback

Le bundle serveur est créé avec git archive depuis le commit vérifié. Le déploiement
est limité à /opt/formafx/storyfx, au site Caddy story.formafx.com, à son seul chemin
de téléchargement /downloads/storyfx-android et à la fonction storyfx-agent-download.
Les sauvegardes sont conservées dans les sous-dossiers
backups de StoryFX. L'ancien conteneur reste disponible par son image de commit.

Le catalogue APK est immuable et la publication de latest intervient seulement
après vérification du fichier signé téléchargé depuis le serveur public. Une
erreur du smoke test rétablit le pointeur app_versions et le code Edge précédent.
Une première installation échouée retire uniquement le nouveau conteneur StoryFX.
Le domaine DNS nouveau a un reçu contenant son ID pour une suppression ciblée
si le premier déploiement doit être abandonné ; aucun autre enregistrement ne change.
