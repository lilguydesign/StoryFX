# FX Maintenance — premier jalon StoryFX

Référentiel local canonique mis à jour :
`C:\FormaFX Group\sendfx\docs\fx-maintenance\FX_MAINTENANCE.md`.
Catalogue, sonde et tests ajoutés dans
`C:\FormaFX Group\sendfx\ops\fx-maintenance`.
La section datée a été ajoutée sans modifier les octets précédents. Le dépôt
SendFX contient du travail antérieur ; aucun de ces fichiers antérieurs n'est
inclus dans la PR StoryFX. Les trois nouveaux modules sont conservés également
dans `ops\maintenance` de StoryFX pour une livraison isolée et reproductible.

Application : StoryFX. Maturité : prototype local de diagnostic, version 0.1.0.
Déclencheur : démarrage manuel de son serveur et exécution locale de la sonde.
Worker de récupération des baux : toutes les dix secondes pendant la vie du
serveur. Horodatage UTC ; affichage en heure du navigateur et planning ancien
Africa/Douala. Bail : 120 secondes ; retard du worker toléré : 30 secondes.
Heartbeat Android et disponibilité en arrière-plan restent distincts.
WorkManager prévoit une récupération réseau au minimum toutes les quinze
minutes, avec backoff réseau et délais système ; aucune cadence exacte promise.
La veille prolongée et l'endurance sur téléphone physique restent non vérifiées.

Signal attendu : `/health` confirme stockage, worker et périmètre diagnostic ;
la file expose ses échéances. Un bail expiré devient `NEEDS_REVIEW`, sans replay.
Une observation fiable et récente est obligatoire pour un verdict positif.
File vide normale ; revue en attente normale ; preuve absente = `unknown`.
Un diagnostic confirmé ne prouve ni une publication ni la disponibilité d'une
application sociale. Le catalogue ne suit aucune URL fournie par une réponse.

Symptômes : API indisponible, worker figé, stockage incohérent, bail expiré
encore actif, frontière diagnostic non vérifiée. Diagnostic : santé fraîche,
échéance du bail, événements et version du seul service StoryFX. Réparation :
reprendre le service local, conserver SQLite et le journal de l'agent, corriger
le protocole puis rejouer la sonde. Un résultat ambigu n'est pas republié.
Rollback : revenir au commit précédent de ce socle et arrêter uniquement son
serveur ; préserver le programme Windows, les historiques et les autres apps.

Preuves : tests de sonde et smoke sur les vrais endpoints locaux. Les règles
existantes de quota global deux heures, groupement, résolution silencieuse et
persistance ont leurs tests ciblés de non-régression. Aucune notification ni
conversation TeamBox créée pendant cette validation.

Le contrôle n'est pas raccordé au collecteur de production ni à un timer
permanent. Le serveur HTTPS public, la disponibilité physique des téléphones,
la publication réelle, le canal d'alerte StoryFX et son template illustré sont
non vérifiés. Aucun logo ou template fictif n'est annoncé comme validé.
