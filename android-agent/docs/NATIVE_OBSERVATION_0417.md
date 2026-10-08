# Android 0.4.17 — diagnostic de la liste native

Version 0.4.17, code 22. La compilation, la publication de l'APK, son installation
et la recette physique sont des étapes distinctes, à vérifier dans leurs reçus.

## Lecture explicite

Le diagnostic du service expose `whatsapp_native_observation` uniquement lors
d'une demande explicite de son état. Il n'effectue aucun geste, ne choisit aucun
média et n'enregistre pas les événements d'accessibilité. La lecture est bornée
à 2 500 nœuds et 128 niveaux ; une lecture tronquée ou échouée est signalée.

Les données renvoyées sont des compteurs et catégories fermées : structure de
la propre liste, états de défilement annoncés, lignes terminées visibles, fraîcheur,
signaux d'envoi en cours ou d'échec, disponibilité des indices et tailles de
collection. Les valeurs négatives signifient indisponible. Un champ de collection
ne constitue pas un nombre de statuts terminés dans le lot courant.

À partir d'Android 13, la lecture compte seulement les nœuds dont le fournisseur
expose un `uniqueId`. Aucune valeur de cet identifiant n'est renvoyée ou conservée.
La sortie ne contient ni texte de statut, nom, album, URI, date de photo, image,
coordonnée d'écran, code privé, jeton ou identifiant matériel.

## Limites de la preuve

`top_candidate` décrit un indice de position, pas une position certifiée.
`top_verified`, `stable_media_identity_verified` et `publication_proof` restent
tous à `false`. La complétude de la lecture n'atteste pas la stabilité temporelle
de l'écran fournisseur. L'absence d'un champ dans un export UIAutomator ne prouve
pas son absence dans l'API native ; ce diagnostic permet de distinguer les deux.

La confirmation reste fondée sur le lot complet dans une seule observation.
Des vues successives ne sont jamais additionnées comme des médias différents.
Les quantités, le délai de 210 secondes, les destinataires et le journal de
non-rejeu restent inchangés. Un lot incertain ne devient pas confirmé grâce à
ce diagnostic et ne peut pas être renvoyé pour compléter une preuve manquante.

La sélection Android utilise le tirage global introduit en 0.4.16, sans remise
au sein du lot, en préférant des jours différents lorsqu'ils sont connus.
Les dates d'import utilisées en repli ne certifient pas les dates de prise de vue.
Il n'existe pas de mémoire inter-publications des images sélectionnées.

## Fonctions encore non validées

Le socle natif distingue l'arrêt global de l'agent du profil WhatsApp désactivé.
Les associations secondaires sont explicites et contrôlées par le serveur ;
aucune association n'est créée par cette version ou par le diagnostic.
Les adaptateurs Facebook et TikTok restent non implémentés et leurs capacités
de publication restent fermées. La veille, les grands lots, le changement de
réseau et le fonctionnement autonome demandent des essais physiques séparés.

Les tests unitaires vérifient les structures synthétiques, la valeur indisponible
`-1`, les arbres tronqués, les API antérieures à Android 13 et l'absence de valeurs
privées dans la sortie. Ils ne remplacent aucune recette sur téléphone.
