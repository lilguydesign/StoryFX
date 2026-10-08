# Associations explicites de profils Android

Cette extension prépare les droits nécessaires à plusieurs profils Facebook sur un
appareil déjà associé. Elle ne fournit pas d'adaptateur Facebook et n'active aucune
publication, recette ou programmation. Les identifiants ci-dessous décrivent des
champs de contrat ; aucun identifiant matériel ni contenu privé n'est requis.

## Autorisation et périmètre

- Utiliser la session propriétaire existante, contrôlée côté serveur. Les mutations
  utilisent aussi le contrôle `Origin` existant. Un jeton agent seul ne suffit pas.
- L'appareil doit déjà appartenir au propriétaire authentifié, être non révoqué et
  posséder son lien principal Android existant vers un nœud non révoqué.
- Le profil supplémentaire doit exister dans le catalogue de ce même propriétaire,
  être activé et être désigné par son UUID canonique, jamais par un identifiant matériel.
- Le seul périmètre supplémentaire accepté est `Facebook`. Une association ne
  crée aucun profil, rôle, appareil, lien principal ni permission WhatsApp.
- Un profil ne peut être associé simultanément à deux appareils, ni être à la fois
  principal et secondaire. Réutiliser le nom d'un profil supprimé ne transfère pas
  son autorisation : le nouvel UUID doit faire l'objet d'une nouvelle demande.
- Chaque appareil accepte au maximum 99 associations secondaires actives, plus
  son primaire. La centième est refusée avant mutation avec
  `ANDROID_PROFILE_LIMIT_REACHED`. Le reçu idempotent existant reste prioritaire.

## API propriétaire

`GET /v1/control/android/profile-bindings`

Réponse : `{revision, bindings, capabilities, devices, primary_profile_ids}`.
`devices` contient les appareils du propriétaire avec lien Android principal,
nœud et appareil non révoqués, et profil canonique existant :
`{device_id,name,primary_profile_id,primary_profile,revoked:false}`.
`primary_profile_ids` liste les UUID de tous les profils principaux déjà liés du
propriétaire, même si leur appareil est indisponible ou révoqué : ces profils
restent réservés et ne doivent pas être proposés comme secondaires.
La liste `bindings` contient les associations
du propriétaire, y compris les retraits pour retrouver leur reçu. Chaque entrée :

```text
id, client_key, device_id, profile_id, profile (ou null si supprimé),
platform="Facebook", active, enabled, ready=false, reason,
created_at, revoked_at
```

`active` décrit une autorisation non retirée. `enabled` décrit le profil canonique.
Aucun des deux ne constitue une capacité de publication.

`POST /v1/control/android/profile-bindings`

```text
{client_key: UUID, device_id: UUID, profile_id: UUID,
 revision: entier, platform: "Facebook"}
```

Réponse directe : l'entrée d'association. La clé client doit être créée et conservée
avant la requête. Même clé et même corps rendent le reçu existant avant de vérifier
la révision ou l'état idle courant. Un corps différent avec la même clé échoue avec
`IDEMPOTENCY_KEY_CONFLICT`. Après retrait, rejouer l'ancienne requête retourne
l'association inactive ; cela ne la réactive pas. Une nouvelle intention requiert
une nouvelle clé et la révision courante.

`POST /v1/control/android/profile-bindings/{id}/remove`

Corps : `{revision: entier}`. Réponse directe : entrée devenue inactive. Le retrait
est conservé avec son horodatage. Répéter le retrait rend ce même reçu.

Les nouvelles mutations exigent sous la même transaction `BEGIN IMMEDIATE` :

- aucune publication du propriétaire sans reçu final dans les états `QUEUED`,
  `CLAIMED`, `CANCEL_REQUESTED`, `NEEDS_REVIEW` ;
- aucun diagnostic `QUEUED`, `CLAIMED`, `STARTED` sur l'appareil concerné ;
- aucun verrou de recette manuelle du propriétaire.

Un timeout de publication n'est pas une preuve d'arrêt. Les reçus tardifs restent
acceptés par les endpoints existants ; aucune annulation ni remise en file n'est
utilisée pour obtenir cet état idle. Un échec rend le code fermé correspondant :
`PUBLICATION_IN_PROGRESS`, `DEVICE_ACTIVITY_IN_PROGRESS`, `MANUAL_RECIPE_ACTIVE`.
La révision du catalogue et les définitions de programmation restent inchangées.

## Contrat Android rétrocompatible

`POST /v1/control/android/settings` conserve les champs `profiles`, `binding`,
`executor` attendus par l'agent WhatsApp 0.4.15. Deux champs sont ajoutés :

```text
capabilities = {facebook: {ready: false, reason: "ADAPTER_NOT_VALIDATED"}}
authorized_profiles = [{profile_id, profile, platform, primary, enabled, ready, reason}]
```

Le primaire reste `platform="WhatsApp", primary=true`. Son `profile_id` est nul si
le profil catalogue a disparu ; il est alors non activé et non prêt. `ready` exige
aussi le contact Android existant de moins de 45 secondes, sans attester une
publication ni l'identité du compte fournisseur. Les secondaires sont toujours
`platform="Facebook", primary=false, ready=false` ; seuls les liens explicites
non retirés dont le profil canonique existe sont listés. Aucun transport privé,
secret, PIN ni identifiant matériel n'est exposé par cette réponse.

Les versions Android existantes peuvent ignorer ces champs supplémentaires. Le
primaire reste le seul membre de `control_nodes.profiles` : les secondaires ne sont
pas ajoutés au routage WhatsApp. Facebook conserve `ADAPTER_NOT_VALIDATED` dans le
moteur de réservation et les recettes ; aucun fallback Windows n'est introduit.

## Protection du lien principal

Répéter `/android/bind` avec le même profil et le même état ne réinitialise plus la
disponibilité et ne modifie aucun job. Toute vraie modification exige l'état idle
décrit ci-dessus. Un changement de profil principal est refusé tant qu'il existe
des associations secondaires actives (`ANDROID_SECONDARY_BINDINGS_PRESENT`).
Les permissions secondaires doivent d'abord être retirées explicitement ; aucun
changement de profil ne les transfère automatiquement.

## Interface propriétaire préparée

L'interface est préparée et testée localement, mais pas encore déployée au moment
de cet amendement du 8 octobre 2026. Après livraison, le parcours normal sera :
`Appareils` → `Profils Facebook supplémentaires` → choisir un téléphone déjà
associé et un profil existant → `Associer pour Facebook`. Il utilise la session
propriétaire normale, sans copie de jeton ni manipulation de session.

Les choix viennent des UUID canoniques de l'API : les profils principaux,
désactivés ou déjà associés sont exclus. Le primaire WhatsApp reste conservé.
Facebook est affiché comme non validé ; aucun bouton de publication, démarrage
de recette ou activation de programmation n'est ajouté dans ce panneau.

La clé et le corps de demande sont conservés avant le POST dans un journal local
par propriétaire. Un verrou Web Lock sérialise les mutations entre onglets.
Après réponse perdue, `Vérifier le résultat` relit le reçu ; `Reprendre la même
demande` réutilise explicitement le même corps et la même clé. Une demande
incertaine n'est pas supprimée pour autoriser une nouvelle intention. Le retrait
exige une sélection et une confirmation explicites et conserve son reçu.

Une recette active met le panneau en lecture seule. Les refus serveur pour une
publication ou un diagnostic en cours restent applicables. Les lectures vérifient
le propriétaire avant et après chargement ; un changement ou une révocation de
session efface les données visibles. La démonstration ne permet aucune mutation.

## Validation et limites

Les tests synthétiques couvrent propriétaires, rôle actif, Origin, profil absent
ou désactivé, appareil révoqué, unicité, concurrence, idempotence après retrait,
réutilisation d'un nom, jobs pending, reçu tardif, recette et diagnostics actifs,
absence de publication Facebook et absence d'élargissement WhatsApp.

Validation locale du 8 octobre 2026 : 42 tests réussis sur les associations,
WhatsApp natif et les recettes (création, progression, reprise), puis 23 tests
réussis après ajout de la borne 99/100, dont un nouveau cas de limite avec claim
WhatsApp préservée ; 43 cas distincts couverts au total. Aucun test
physique, appel fournisseur, enqueue réel ou déploiement n'a été exécuté dans
ce sous-chantier. La livraison coordonnée rapporte également 13 tests synthétiques
du panneau et un smoke Edge hors ligne réussis, puis la suite serveur/maintenance
complète : 299 réussites, 5 tests ignorés et 50 sous-tests. La revue indépendante
des contrats serveur, Android et de l'interface n'a pas identifié de blocage.

Les observations physiques restent nécessaires pour valider un futur adaptateur
Facebook : compte/page exacts avant composition et envoi, sélection des médias,
destination Story, compteur et preuve de lot complet après envoi, erreur/annulation,
crash et absence de renvoi. Cette extension n'atteste aucune de ces capacités.
