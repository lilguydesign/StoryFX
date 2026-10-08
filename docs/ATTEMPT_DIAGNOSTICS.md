# Rapports de tentative StoryFX

Le reçu Android peut joindre à `/complete` un objet `diagnostics` fermé et
facultatif, conservé dans `control_attempt_diagnostics` dans la même transaction
que le résultat. Le propriétaire et l'appareil doivent correspondre à la
tentative existante. Les champs inconnus, chaînes libres et valeurs hors limites
sont refusés sans être renvoyés dans l'erreur HTTP.

Les rapports montrent l'échéance Africa/Douala, le profil, la plateforme, la
référence de pays de page, la catégorie, l'étape finale observée, la version,
l'état du service, le type de réseau, la durée et les quantités attendue,
sélectionnée et vérifiée. Le lien de tentative permet de retrouver son origine
en cas de reprise explicite. Aucun contenu d'album, média, conversation, PIN,
jeton, numéro de téléphone ni identifiant matériel n'est ajouté au diagnostic.

Il s'agit du reçu de cette tentative, pas d'une capture de panne. Le serveur
n'accepte pas l'ajout d'un diagnostic postérieur à un résultat déjà enregistré.
Une retransmission identique est idempotente : elle ne change ni la date du
résultat, ni le diagnostic, ni le journal. Un résultat final incertain reste
immuable ; une expiration serveur sans reçu peut encore recevoir le résultat
tardif original, sans redémarrer l'exécution.

Pour une nouvelle confirmation quantifiée, les trois compteurs doivent être
égaux au lot prévu, la destination applicative doit être WhatsApp Business et
la méthode de vérification doit désigner des statuts récents observés. Ces
conditions restent des preuves déclarées par l'agent. Le compte WhatsApp n'a
pas de vérification canonique indépendante : Android indique
`account_verified=false`. Ni un HTTP 200, ni ces compteurs ne certifient un
démarrage à froid, une veille profonde ou un fonctionnement autonome sans PC.

Les anciens agents restent compatibles et leurs résultats sont conservés.
Sans diagnostic quantifié, les compteurs sélectionné/vérifié sont inconnus ;
l'observateur ne déduit plus `batch_count_verified=true` du seul code
`own_status_verified`. Il ne modifie aucune ancienne tentative. Les
confirmations historiques restent classées `confirmed_agent`, avec cette
limite distincte de la quantité.

Les occurrences non prises en charge et en attente de moteur restent visibles
dans Rapports sans réservation de tâche. Facebook et TikTok n'ont toujours pas
d'exécuteur Android validé. Les motifs d'attente distinguent l'agent Android,
ses permissions/capacités et le pont Windows. Les indicateurs `/health`
décrivent des capacités logicielles ; `publication_verified_by_health` et
`total_autonomy_verified` restent faux.

Les identités d'occurrence, quantités planifiées, albums, horaires et droits ne
sont pas modifiés par cette livraison. La différence entre `matrix.count` du
serveur et la priorité legacy de `albums.count_per_post` doit faire l'objet
d'une migration contrôlée si les valeurs divergent ; changer l'identité d'une
ancienne occurrence pourrait créer une nouvelle publication.

Rollback : backend précédent et dashboard correspondant. La table additive peut
rester présente ; conserver les reçus et les historiques. Un ancien backend
ne consommera pas ces nouveaux diagnostics et ne doit pas être présenté comme
une preuve de quantification. Les tests synthétiques couvrent contenu fermé,
isolation propriétaire, atomicité, retransmission, immutabilité, absence de
rejeu, anciennes preuves et affichage des valeurs inconnues.
