# Déverrouillage local Android — 0.4.3

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
