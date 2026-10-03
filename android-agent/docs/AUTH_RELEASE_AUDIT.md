# Agent Android StoryFX — audit et pilote 0.2.0

## Sources consultées

- StoryFX : `C:\FormaFX Group\storyfx\android-agent`.
- ScreenTimeFX Android : `auth\AuthRoutes.kt`, `ui\AgentAuthFlowController.kt`,
  `network\AgentAuthRepository.kt`, scripts de signature et de livraison.
- RemoteFX : `scripts\build-remotefx-android.ps1` et configuration Gradle Android.
- FormaFX canonique : `lib\access\sso\formafx_sso_handoff.dart` et les pages
  connexion, récupération de mot de passe et OTP. Le miroir authfx reste une référence.
- Site canonique : `formafx-website\public\assets\js\android-download-config.js`,
  `remotefx-android-editions.js` et catalogue des applications.

L'audit initial StoryFX était propre, sur `feature/internet-diagnostic-foundation`.
ScreenTimeFX Android était propre. RemoteFX contenait des modifications préexistantes :
elles ont été consultées sans modification, copie de secrets, stage ou commit.
Les règles des deux AGENTS.md FormaFX/site ont été lues. Aucun worktree créé.

## Choix de connexion

ScreenTimeFX Android utilise déjà un navigateur externe, un callback à ticket/code,
un nonce d'installation et un échange HTTPS. Les mots de passe, OTP et resets restent
dans les écrans FormaFX. RemoteFX utilise une association technique, sans compte FormaFX.

StoryFX reprend le navigateur système et ajoute PKCE S256. Cette solution partage la
connexion web FormaFX et évite une seconde implémentation de mots de passe/OTP.
Le [RFC8252](https://www.rfc-editor.org/rfc/rfc8252) recommande le navigateur externe
pour l'authentification native. Le [RFC7636](https://www.rfc-editor.org/rfc/rfc7636)
décrit la preuve PKCE contre l'interception du code.

Le callback pilote est `storyfx-android://auth/callback`. Seuls `ticket` et `state`
sont acceptés, sans doublon, fragment, autre hôte ni autre chemin. Le ticket reste
temporaire et à usage unique. Aucun access token, refresh token, mot de passe ou
verifier PKCE ne passe dans une URL. Le verifier reste chiffré dans Android Keystore.

Une future association [Android App Links](https://developer.android.com/training/app-links)
peut ajouter le callback HTTPS, après publication de l'assetlinks correspondant à
la signature officielle. Le pilote actuel ne déclare pas cette vérification acquise.

## Contrat partagé

`POST /v1/auth/agent/start`, public :

```json
{
  "installation_id": "UUID",
  "name": "nom du téléphone, 80 caractères maximum",
  "android_version": "version Android",
  "app_version": "0.2.0",
  "state": "32 octets aléatoires en base64url",
  "device_nonce": "32 octets aléatoires en base64url",
  "code_challenge": "SHA256 du verifier en base64url",
  "code_challenge_method": "S256",
  "redirect_uri": "storyfx-android://auth/callback"
}
```

Réponse : `connect_url` HTTPS de la même origine `/agent/connect?request_id=...`
et `expires_at` ISO UTC. Durée serveur : dix minutes.

Le navigateur appelle `POST /v1/auth/agent/authorize {request_id}` avec sa session
FormaFX. Le serveur vérifie le propriétaire actif avant de produire le ticket.

`POST /v1/auth/agent/exchange`, public : `ticket`, `state`, `device_nonce`,
`installation_id` et `code_verifier`. Réponse : `device_id`, token appareil opaque,
`user.id` UUID et `user.email`. Le ticket expire après 120 secondes.
La session FormaFX reste chiffrée côté serveur ; l'agent conserve son accès appareil
et son profil local dans Android Keystore. Les contrôles propriétaire/refresh/revocation
relèvent du serveur et ne sont jamais remplacés par une décision locale Android.

## Modules et reprise

- `AgentAuthProof.kt` : state, nonce, PKCE et sérialisation privée.
- `AgentAuthRoutes.kt` : validation stricte du navigateur et du callback.
- `AgentAuthProtocol.kt` : transitions start/exchange et validations du contrat.
- `EncryptedStore.kt` : preuve de connexion, token et profil AES-GCM ; commit atomique.
- `MainActivity.kt` : interface native et Intent navigateur, sans WebView.
- `AgentController.kt` : verrou commun avec synchronisation et callback.

Le UUID d'installation, les UUID d'événement, le journal chiffré et WorkManager sont
conservés. Une association ou déconnexion avec événements non confirmés est refusée.
Une coupure pendant la connexion garde sa preuve privée ; un ticket expiré/consommé
demande une nouvelle connexion. Aucune action de publication n'est ajoutée.
L'association technique par code reste visible uniquement dans `.qa`.

## Signature et livraison

Le wrapper StoryFX `scripts\build-release-signed.ps1` utilise le même coffre DPAPI
CurrentUser que RemoteFX, déjà présent à
`C:\Users\lilgu\.screentimefx-android\release-signing.dpapi.json`.
Il ne recopie ni ne crée le keystore et ne renouvelle aucun secret.
Les passwords sont transmis uniquement par variables du processus apksigner,
effacées en finally ; aucun secret ne passe dans les arguments ou les rapports.

La signature officielle est contrôlée par son empreinte publique :
`e3795a1bca6acab02ce61b724ef827c35c19a2c4ffbbb7d9c4c3af3fa7009a12`.
Le wrapper bloque une signature différente, un package `.qa`, une mauvaise version
ou une permission sensible inattendue. Il écrit APK SHA256 et manifeste sûr.

APK attendu : `android-agent\build\release\StoryFX-Android-0.2.0-v2.apk`.
Package : `com.formafx.storyfx.agent`, versionName `0.2.0`, versionCode `2`.
La publication du lien latest sur apps.formafx.com est prise en charge par le chantier
serveur/site, après vérification du fichier signé et de son SHA256 public.
La signature locale n'est pas une preuve de téléchargement public.

## Contrôles prévus

Tests ciblés : vecteur RFC7636, entropie indépendante, callback exact, refus des autres
origines, state différent, expiration, preuve persistée avant réseau, journal non vidé,
perte de réponse et rejet d'une session incorrecte. Le résultat réellement exécuté
figure dans le rapport de build et de livraison, sans qualifier de réussite un test absent.

Le pilote conserve uniquement le diagnostic. Aucun téléphone personnel, permission
Accessibilité, galerie, média ni publication réelle n'est utilisé dans sa validation.
