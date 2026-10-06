# DÃ©verrouillage local Android â€” 0.4.5

Dans StoryFX Android, Â« DÃ©verrouillage local Â» permet d'enregistrer, tester ou
supprimer le PIN du tÃ©lÃ©phone associÃ©. Le champ reste masquÃ©, sans remplissage
automatique ni sauvegarde d'Ã©tat. Le secret est chiffrÃ© AES-GCM par AndroidKeyStore,
liÃ© au profil et Ã  l'installation ; il n'est transmis ni au serveur ni aux rapports.

StoryFX ouvre le dialogue Android normal uniquement pour une tÃ¢che WhatsApp image
dÃ©jÃ  due, dans le pÃ©rimÃ¨tre d'un scheduler actif et de son propriÃ©taire authentifiÃ©.
Le service vÃ©rifie le clavier numÃ©rique System UI, l'entrÃ©e vide et les dix touches.
Une tentative est rÃ©servÃ©e avant la saisie ; aprÃ¨s un Ã©chec, le propriÃ©taire doit
dÃ©verrouiller manuellement. Aucun contournement du verrou, root, rÃ©glage global de
sÃ©curitÃ© ou permission administrateur n'est utilisÃ©.

Le bouton de test autorise pendant une minute un essai local avec l'association
serveur toujours valide. Cette demande reste seulement en mÃ©moire et ne survit pas
au redÃ©marrage. Le test ne crÃ©e aucune publication ; les planifications existantes
peuvent ensuite reprendre normalement.

AprÃ¨s redÃ©marrage complet, le premier dÃ©verrouillage manuel Android reste nÃ©cessaire
avant l'accÃ¨s au stockage protÃ©gÃ© des identifiants. Le service AccessibilitÃ© peut
ensuite reprendre les commandes existantes. La prÃ©sence d'un tÃ©lÃ©phone connectÃ© ne
prouve pas que ses statuts sont publiÃ©s.

## Statut personnel vide et reprise contrÃ´lÃ©e

Le pilote accepte le repÃ¨re exact Â« Add status Â» / Â« Ajouter un statut Â» pour
Ã©tablir une rÃ©fÃ©rence de zÃ©ro statut actif. Il vÃ©rifie ensuite le rÃ©sultat dans
Â« My status Â» ; un rÃ©sultat incertain reste rÃ©servÃ© et ne peut Ãªtre rejouÃ©.

Une ancienne erreur gÃ©nÃ©rique `preflight_refused` peut Ãªtre reprise seulement si
le mÃªme tÃ©lÃ©phone observe maintenant son espace de statut entiÃ¨rement vide,
sans tÃ¢che en cours, avec les permissions et le profil actifs. La preuve expire
aprÃ¨s 45 secondes ; la tentative originale doit avoir moins de 23 heures pour
Ã©viter de confondre un statut expirÃ© avec une absence d'envoi. Les lignes,
albums, nombres, destinataires et planifications doivent Ãªtre inchangÃ©s.
La reprise crÃ©e une tentative distincte ; elle ne modifie pas l'audit original.
Une sÃ©lection de 1 Ã  20 tentatives est validÃ©e et mise en file atomiquement.
Les rÃ©sultats confirmÃ©s, incertains ou ayant franchi le sÃ©lecteur restent exclus.

Le contrÃ´le public de maintenance vÃ©rifie seulement le contrat serveur. Il ne
certifie ni un dÃ©verrouillage rÃ©el ni la publication sur un tÃ©lÃ©phone : ces preuves
doivent Ãªtre fournies sÃ©parÃ©ment par les essais matÃ©riels et le rapport d'exÃ©cution.

## Reconnaissance Android 0.4.4

Le titre Updates et lâ€™onglet Updates sont distinguÃ©s par leur position. La preuve
Â« espace vide Â» exige une vue portrait du fournisseur, son titre Updates en haut,
la section Status et la premiÃ¨re tuile Add status, sans My status ni bouton Send.
Un nom de contact identique, une lÃ©gende approximative ou un sÃ©lecteur dâ€™envoi
ne suffisent pas. Aucun texte de discussion nâ€™est conservÃ©.

Le clavier PIN peut Ãªtre une fenÃªtre System UI sÃ©parÃ©e de lâ€™activitÃ© de rÃ©veil.
Le service inspecte seulement les fenÃªtres System UI et exige un unique clavier
numÃ©rique reconnu avant de saisir le code. Le rÃ©sultat local est un libellÃ© fermÃ©
(AUTORISATION, RÃ‰VEIL_DEMANDÃ‰, CLAVIER_NON_RECONNU, SAISIE_EN_COURS, CONFIRMÃ‰,
NON_CONFIRMÃ‰, ERREUR ou AUTORISATION_REFUSÃ‰E), sans PIN, capture ni texte dâ€™Ã©cran.
Le bouton Voir le rÃ©sultat affiche ce diagnostic sur le tÃ©lÃ©phone.

Le test matÃ©riel du 6 octobre a observÃ© un vrai verrouillage du S23 FE, sans encore
confirmer son dÃ©verrouillage par la version 0.4.3. La version 0.4.4 doit Ãªtre
validÃ©e sÃ©parÃ©ment ; sa compilation et ses tests ne prouvent pas une publication.

## Diagnostic matÃ©riel fermÃ© â€” 0.4.5

Le dump Android du service fournit uniquement des indicateurs : disponibilitÃ© du
service, verrouillage, catÃ©gorie de fenÃªtre, dimensions, prÃ©sence des repÃ¨res du
statut et clavier numÃ©rique reconnu. Aucune conversation, capture, valeur de PIN,
identitÃ© de session ou jeton nâ€™est lu ni imprimÃ© par ce diagnostic. Le service
nâ€™expose aucune nouvelle commande rÃ©seau ; Android contrÃ´le lâ€™accÃ¨s normal DUMP.

La fenÃªtre WhatsApp retenue doit Ãªtre une application du fournisseur avec le focus,
unique ; une fenÃªtre systÃ¨me active ne peut plus masquer cette fenÃªtre. Le repÃ¨re
vide exige le texte Add status de la premiÃ¨re tuile, avec les deux en-tÃªtes. La
simple description gÃ©nÃ©rique My status de son avatar nâ€™est pas un statut actif ;
un texte My status ou un contrÃ´le Send exclut toujours la preuve.

Le rÃ©sultat PIN_CONFIRMÃ‰ est rÃ©servÃ© au retour dÃ©verrouillÃ© aprÃ¨s une saisie sur le
clavier numÃ©rique reconnu. RÃ‰VEIL_CONFIRMÃ‰ signifie que la saisie nâ€™a pas Ã©tÃ©
nÃ©cessaire. Les validations matÃ©rielles et publications restent Ã  contrÃ´ler.

## VÃ©rification native 0.4.6

Les Ã©lÃ©ments de disposition Android sont demandÃ©s dans les seules fenÃªtres WhatsApp et System UI dÃ©jÃ  autorisÃ©es. Android permet ce rÃ©glage via `FLAG_INCLUDE_NOT_IMPORTANT_VIEWS` : https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#FLAG_INCLUDE_NOT_IMPORTANT_VIEWS. Aucun texte de discussion ni identifiant de contact nâ€™est exportÃ©.

Une sÃ©lection de partage refusÃ©e avant la premiÃ¨re flÃ¨che dâ€™envoi peut Ãªtre reprise uniquement sur demande explicite du propriÃ©taire, aprÃ¨s une nouvelle preuve native entiÃ¨rement vide de Mon statut, postÃ©rieure Ã  lâ€™Ã©chec, fraÃ®che de moins de 45 secondes, sur le mÃªme tÃ©lÃ©phone et avec la mÃªme programmation. Aucun rÃ©sultat CONFIRMED, NEEDS_REVIEW ou refus de lâ€™aperÃ§u aprÃ¨s la flÃ¨che ne devient rejouable. Les anciennes tÃ¢ches restent immuables.

## Diagnostic du clavier 0.4.7

La reconnaissance exige le vÃ©ritable champ de mot de passe System UI, son identifiant PIN, un champ vide et les dix touches numÃ©riques. Elle ne dÃ©pend plus du package dâ€™un Ã©lÃ©ment dÃ©coratif. Le dialogue Android est demandÃ© aprÃ¨s la reprise visible de lâ€™activitÃ©. Le rÃ©sultat du dernier test local est conservÃ© sÃ©parÃ©ment des refus ordinaires de pilotage, qui ne doivent pas masquer ce test. Aucun code nâ€™est enregistrÃ© en clair ni transmis au serveur.


Le candidat 0.4.7 a déverrouillé physiquement les deux téléphones pendant un test local, sans saisie SDK du PIN. Le résultat initial ERREUR révélait une validation Android du dernier chiffre avant la commande suivante. La correction de cette course ne confirme le PIN que si une tentative a été réservée et que les deux verrous Android sont levés, écran interactif. Le candidat final doit être testé séparément.

Les commandes WhatsApp reconnues peuvent utiliser un toucher au centre de leur propre nœud visible et borné, lorsqu'aucun ancêtre ne fournit ACTION_CLICK. La fenêtre doit rester celle de WhatsApp Business au premier plan, Android déverrouillé, sans agrandissement ni exploration tactile. Aucun toucher supplémentaire n'est tenté après une action native échouée ; les vérifications Mon statut / Contacts et le journal avant envoi sont conservés. Cette capacité Android est déclarée explicitement : https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#dispatchGesture(android.accessibilityservice.GestureDescription,%20android.accessibilityservice.AccessibilityService.GestureResultCallback,%20android.os.Handler).

Le contrôle automatique a refusé de retirer l'exclusion des tâches enfants déjà rejouées : les quatre reprises concernées restent exclues, sans nouvelle demande ni réécriture d'audit. Le test de publication doit utiliser une programmation originale distincte, encore non exécutée, ou une autre reprise originale sans descendant après les preuves exigées.
