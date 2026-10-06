# Déverrouillage local Android — 0.4.7

Dans StoryFX Android, « Déverrouillage local » permet d'enregistrer, tester ou
supprimer le PIN du téléphone associé. Le champ reste masqué, sans remplissage
automatique ni sauvegarde d'état. Le secret est chiffré AES-GCM par AndroidKeyStore,
lié au profil et à l'installation ; il n'est transmis ni au serveur ni aux rapports.

StoryFX ouvre le dialogue Android normal uniquement pour une tâche WhatsApp image
déjà due, dans le périmètre d'un scheduler actif et de son propriétaire authentifié.
Le service vérifie le clavier numérique System UI, l'entrée vide et les dix touches.
Une tentative est réservée avant la saisie ; après un échec, le propriétaire doit
déverrouiller manuellement. Aucun contournement du verrou, root, réglage global de
sécurité ou permission administrateur n'est utilisé.

Le bouton de test autorise pendant une minute un essai local avec l'association
serveur toujours valide. Cette demande reste seulement en mémoire et ne survit pas
au redémarrage. Le test ne crée aucune publication ; les planifications existantes
peuvent ensuite reprendre normalement.

Après redémarrage complet, le premier déverrouillage manuel Android reste nécessaire
avant l'accès au stockage protégé des identifiants. Le service Accessibilité peut
ensuite reprendre les commandes existantes. La présence d'un téléphone connecté ne
prouve pas que ses statuts sont publiés.

## Statut personnel vide et reprise contrôlée

Le pilote accepte le repère exact « Add status » / « Ajouter un statut » pour
établir une référence de zéro statut actif. Il vérifie ensuite le résultat dans
« My status » ; un résultat incertain reste réservé et ne peut être rejoué.

Une ancienne erreur générique `preflight_refused` peut être reprise seulement si
le même téléphone observe maintenant son espace de statut entièrement vide,
sans tâche en cours, avec les permissions et le profil actifs. La preuve expire
après 45 secondes ; la tentative originale doit avoir moins de 23 heures pour
éviter de confondre un statut expiré avec une absence d'envoi. Les lignes,
albums, nombres, destinataires et planifications doivent être inchangés.
La reprise crée une tentative distincte ; elle ne modifie pas l'audit original.
Une sélection de 1 à 20 tentatives est validée et mise en file atomiquement.
Les résultats confirmés, incertains ou ayant franchi le sélecteur restent exclus.

Le contrôle public de maintenance vérifie seulement le contrat serveur. Il ne
certifie ni un déverrouillage réel ni la publication sur un téléphone : ces preuves
doivent être fournies séparément par les essais matériels et le rapport d'exécution.

## Reconnaissance Android 0.4.4

Le titre Updates et l’onglet Updates sont distingués par leur position. La preuve
« espace vide » exige une vue portrait du fournisseur, son titre Updates en haut,
la section Status et la première tuile Add status, sans My status ni bouton Send.
Un nom de contact identique, une légende approximative ou un sélecteur d’envoi
ne suffisent pas. Aucun texte de discussion n’est conservé.

Le clavier PIN peut être une fenêtre System UI séparée de l’activité de réveil.
Le service inspecte seulement les fenêtres System UI et exige un unique clavier
numérique reconnu avant de saisir le code. Le résultat local est un libellé fermé
(AUTORISATION, RÉVEIL_DEMANDÉ, CLAVIER_NON_RECONNU, SAISIE_EN_COURS, CONFIRMÉ,
NON_CONFIRMÉ, ERREUR ou AUTORISATION_REFUSÉE), sans PIN, capture ni texte d’écran.
Le bouton Voir le résultat affiche ce diagnostic sur le téléphone.

Le test matériel du 6 octobre a observé un vrai verrouillage du S23 FE, sans encore
confirmer son déverrouillage par la version 0.4.3. La version 0.4.4 doit être
validée séparément ; sa compilation et ses tests ne prouvent pas une publication.

## Diagnostic matériel fermé — 0.4.5

Le dump Android du service fournit uniquement des indicateurs : disponibilité du
service, verrouillage, catégorie de fenêtre, dimensions, présence des repères du
statut et clavier numérique reconnu. Aucune conversation, capture, valeur de PIN,
identité de session ou jeton n’est lu ni imprimé par ce diagnostic. Le service
n’expose aucune nouvelle commande réseau ; Android contrôle l’accès normal DUMP.

La fenêtre WhatsApp retenue doit être une application du fournisseur avec le focus,
unique ; une fenêtre système active ne peut plus masquer cette fenêtre. Le repère
vide exige le texte Add status de la première tuile, avec les deux en-têtes. La
simple description générique My status de son avatar n’est pas un statut actif ;
un texte My status ou un contrôle Send exclut toujours la preuve.

Le résultat PIN_CONFIRMÉ est réservé au retour déverrouillé après une saisie sur le
clavier numérique reconnu. RÉVEIL_CONFIRMÉ signifie que la saisie n’a pas été
nécessaire. Les validations matérielles et publications restent à contrôler.

## Vérification native 0.4.6

Les éléments de disposition Android sont demandés dans les seules fenêtres WhatsApp et System UI déjà autorisées. Android permet ce réglage via `FLAG_INCLUDE_NOT_IMPORTANT_VIEWS` : https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#FLAG_INCLUDE_NOT_IMPORTANT_VIEWS. Aucun texte de discussion ni identifiant de contact n’est exporté.

Une sélection de partage refusée avant la première flèche d’envoi peut être reprise uniquement sur demande explicite du propriétaire, après une nouvelle preuve native entièrement vide de Mon statut, postérieure à l’échec, fraîche de moins de 45 secondes, sur le même téléphone et avec la même programmation. Aucun résultat CONFIRMED, NEEDS_REVIEW ou refus de l’aperçu après la flèche ne devient rejouable. Les anciennes tâches restent immuables.

## Diagnostic du clavier 0.4.7

La reconnaissance exige le véritable champ de mot de passe System UI, son identifiant PIN, un champ vide et les dix touches numériques. Elle ne dépend plus du package d’un élément décoratif. Le dialogue Android est demandé après la reprise visible de l’activité. Le résultat du dernier test local est conservé séparément des refus ordinaires de pilotage, qui ne doivent pas masquer ce test. Aucun code n’est enregistré en clair ni transmis au serveur.


La version finale 0.4.7 a réveillé et déverrouillé physiquement le S23 FE et le S23+, avec le résultat PIN_CONFIRMÉ, sans saisie SDK du PIN, arrêt Appium ou modification des protections Android. Les deux tests portent sur le même APK signé que la livraison. La validation du dernier chiffre est reconnue seulement après une tentative réservée et le retour des deux verrous Android à l'état déverrouillé, écran interactif.

Les commandes WhatsApp reconnues peuvent utiliser un toucher au centre de leur propre nœud visible et borné, lorsqu'aucun ancêtre ne fournit ACTION_CLICK. La fenêtre doit rester celle de WhatsApp Business au premier plan, Android déverrouillé, sans agrandissement ni exploration tactile. Aucun toucher supplémentaire n'est tenté après une action native échouée ; les vérifications Mon statut / Contacts et le journal avant envoi sont conservés. Cette capacité Android est déclarée explicitement : https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#dispatchGesture(android.accessibilityservice.GestureDescription,%20android.accessibilityservice.AccessibilityService.GestureResultCallback,%20android.os.Handler).

Le contrôle automatique a refusé de retirer l'exclusion des tâches enfants déjà rejouées : les quatre reprises concernées restent exclues, sans nouvelle demande ni réécriture d'audit. Le test de publication doit utiliser une programmation originale distincte, encore non exécutée, ou une autre reprise originale sans descendant après les preuves exigées.


Les états de réveil sont désormais un type Kotlin avec des identifiants ASCII stables. Les libellés français sont traduits à l'affichage et les anciennes préférences restent lisibles. Une corruption d'encodage dans une modification intermédiaire avait fait refuser le réveil avant toute saisie ; le candidat concerné n'a pas été publié. La revue des sources vérifie désormais explicitement l'encodage.

La vérification du lot peut comparer le nombre complet de lignes de la collection Mon statut avant et après l'envoi. Les deux nombres doivent provenir de la vue fournisseur vérifiée, et leur différence doit égaler exactement le nombre demandé ; une métadonnée absente n'est jamais zéro. Les résultats déjà incertains restent conservés sans reprise ni promotion automatique après modification du code.


## Vérification matérielle du 6 octobre 2026

APK signé : `a79fda5d3ddd474e3521428c47e56708a7a0c667f38abfc0801cd7198f094d1e`. Les deux tests physiques du code sont détaillés dans le reçu matériel fermé de livraison. Le S23 FE et le S23+ présentent chacun onze nouvelles images de la programmation originale de 16 h 40 et 16 h 45 UTC, dans Mon statut. La comparaison visuelle des pages et de leur fin est une preuve manuelle ; les deux rapports NEEDS_REVIEW restent immuables. WhatsApp expose ici une ListView sans total ni index de collection : la confirmation automatique du lot complet reste non vérifiée sur ces téléphones.

Après l'envoi, StoryFX attend de manière bornée que la cible exacte Mon statut réapparaisse, sans second envoi. Une interface non reconnue ou un total absent ne devient jamais une preuve de publication complète. Redémarrage physique, coupure du câble/réseau, veille profonde et installation par le bouton de mise à jour Android restent non testés. Le premier déverrouillage après redémarrage complet reste manuel.
