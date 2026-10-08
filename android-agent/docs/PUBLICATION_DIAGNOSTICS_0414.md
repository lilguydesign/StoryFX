# Android 0.4.14 — navigation et preuve de lot

La version 0.4.14/code 19 attend les transitions du fournisseur et conserve une
liste Mon statut déjà ouverte. Un écran tardif est observé sans répéter le clic.
Les seuls gestes de navigation admis sont Actus et Mon statut, déjà identifiés
par leurs libellés exacts dans la fenêtre WhatsApp Business. Aucun bouton Retour
n'est utilisé depuis une conversation, un lecteur de statut ou un écran inconnu.
Un libellé texte Mon statut prime sur la description identique de son avatar
uniquement s'ils partagent un même contrôle cliquable borné ; plusieurs libellés
ou un avatar sans ce lien restent ambigus. Le sélecteur de destinataire conserve
l'identifiant `contactpicker_row_name` et le libellé exact, sans correspondance
approximative ni nouvelle cible.

Une croissance de la collection ne suffit plus à confirmer une publication.
Chaque ligne récente retenue doit porter son indicateur de vues et aucun état
d'envoi/erreur reconnu. La quantité exacte est vérifiée dans une page ou par les
indices de lignes distincts sur plusieurs pages. Un lot partiel, un chargement
indéterminé ou une structure non reconnue après l'envoi reste NEEDS_REVIEW et
n'est jamais rejoué. Cette preuve locale agent n'est pas une attestation
indépendante du fournisseur : le compte WhatsApp n'est pas encore lié à une
référence de compte vérifiée et `account_verified` demeure false.

Les diagnostics par tentative contiennent uniquement version, état du service,
type de réseau, étape, durée, quantités attendue/préparée/vérifiée, état fermé de
navigation et méthode de vérification. `selected_count` désigne les URI locales
préparées, pas un compteur attesté de l'éditeur WhatsApp. Les nombres inconnus
sont absents. Le journal chiffré réserve l'incertitude avant tout geste et conserve
les diagnostics au changement d'étape ; un crash ne réarme aucune occurrence.
Les textes d'écran, médias, albums, comptes, identifiants matériels et secrets
ne sont jamais sérialisés. Le réseau est observé sans le modifier.

Un rollback du backend peut refuser le nouveau champ diagnostics. Le seul repli
admis concerne l'accusé de résultat après HTTP 422/INVALID_REQUEST et vérification
positive du contrat `/health` historique, sain, sur le même serveur HTTPS. Le
contrat annonçant `structured_attempt_diagnostics=true` interdit ce repli. Un
serveur inconnu, inaccessible ou un refus d'accès conserve le reçu en attente.
La copie chiffrée du diagnostic reste conservée et aucun geste n'est rejoué.

Limites conservées : le poll de publication est un ScheduledExecutor Android ;
son réveil en veille profonde n'est pas garanti par cette correction. Le travail
WorkManager toutes les 15 minutes ne traite que le diagnostic. Une reconnexion
réseau, un démarrage et une nuit naturelle sans USB doivent être vérifiés sur
chaque téléphone avant de conclure à l'autonomie. Les tests JVM et le build
valident le code, pas le rendu installé de WhatsApp ni une publication réelle.

Les essais physiques exigent d'abord l'accord de pause du moteur Windows/USB
actif et la vérification d'absence d'exécuteur concurrent. Aucun échec, résultat
incertain, succès ou rattrapage existant n'est repris par cette version.
