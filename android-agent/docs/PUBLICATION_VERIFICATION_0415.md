# Android 0.4.15 — attendre la fin du lot

La version 0.4.15/code 20 corrige un arrêt trop précoce après l'envoi : un lot
encore incomplet ou une liste sans page suivante est réobservé, au lieu de
devenir immédiatement incertain. L'attente du premier rendu Mon statut suit
également le délai global existant de 210 secondes, mesuré depuis le début
de l'exécution ; aucun délai supplémentaire n'est accordé à la vérification.

Chaque passe revient au début de la liste reconnue, parcourt au plus huit pages
et compte uniquement les lignes terminées selon les preuves de 0.4.14. Une
confirmation exige désormais le lot entier dans une même observation, sans
indice connu dupliqué. Aucun indice n'est cumulé entre pages ou passes : une
position peut changer pendant l'envoi sans identifier un média différent.
La pagination apporte un diagnostic, jamais une preuve d'identité cumulée.
Les deux clics d'envoi restent hors de cette boucle. Les sélecteurs et
destinataires sont inchangés.

Un lot qui dépasse toujours la quantité visible sur une seule vue reste
NEEDS_REVIEW au délai limite, sans rejeu : cette version ne possède pas de
preuve d'identité stable permettant de certifier un lot réparti entre pages.
La méthode historique `recent_rows` n'est plus produite par cette version ;
les résultats historiques du serveur restent conservés.
Les appels réseau/UI déjà engagés gardent leurs timeouts existants ; le délai
est recontrôlé après leur retour avant toute confirmation. Ce correctif ne
prouve ni la livraison physique, ni le compte WhatsApp, ni la veille profonde.
La version 0.4.14 déjà publiée est conservée ; aucune installation sur un
téléphone occupé n'est autorisée par la compilation de cette version.
