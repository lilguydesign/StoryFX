# Réservation et observation de vérification

## Réservation atomique

Le catalogue et l'identité d'occurrence restent inchangés. La réservation relit
les exécuteurs sous la transaction `BEGIN IMMEDIATE` qui insère le job : propriétaire,
profils courants, révocation, fraîcheur du contact, lien Android principal exact,
permissions et capacité média. Un snapshot pris avant un changement de profil
ne peut donc plus consommer une occurrence sur l'ancien profil du même nœud.

Le choix conserve les règles existantes : Android compatible est prioritaire ;
le fallback Windows reste limité à `multi` ; des exécuteurs ambigus sont refusés.
Les associations Facebook secondaires ne font jamais partie du routage WhatsApp.
Les verrous de recette, révision de catalogue, génération du scheduler et unicité
d'occurrence sont contrôlés avant toute insertion. Aucun rejeu n'est ajouté.

Le retry explicite d'un échec avant publication utilise cette même lecture
transactionnelle. Une réaffectation du primaire après le snapshot est refusée
avant création d'une nouvelle tentative, même si Windows est disponible : ce
retry reste réservé au moteur Android. Le reçu parent est conservé à l'identique.
Les résultats incertains, déjà confirmés et les tentatives de recette restent
inéligibles ; la liste des échecs admissibles et les autres gardes ne changent pas.

## Diagnostic facultatif de vérification

Trois champs fermés et facultatifs complètent `diagnostics` sur `/complete` :

| Champ | Type | Sens |
| --- | --- | --- |
| `verification_started` | booléen strict ou null | Le vérificateur a été invoqué. |
| `verification_observations` | entier strict 0..3000 ou null | Nombre d'observations effectuées. |
| `peak_verified_count` | entier strict 0..30 ou null | Plus grand compte observé dans une seule vue. |

Le défaut est null, donc inconnu pour un ancien reçu. Aucune mesure absente n'est
transformée en zéro ou faux. Le maximum ne cumule jamais les lignes de plusieurs
pages et ne remplace pas `verified_count`. Il ne suffit pas à confirmer un lot.
Les conditions de `CONFIRMED`, le statut du compte et les délais ne changent pas.

L'agent peut envoyer `false`, `0`, `null` avant vérification. Après lancement du
vérificateur, il compte les observations et leur maximum individuel. Une tentative
incertaine reste incertaine, même si son maximum égale le nombre attendu.

## Compatibilité des reçus et rollback

`/health` annonce `verification_observation_diagnostics=true` sur ce serveur.
Ce marqueur décrit uniquement le contrat API, jamais une publication réussie.

`control_attempt_diagnostics.value` conserve son format historique. Les nouvelles
mesures non nulles sont stockées dans `control_attempt_observations`, liée au job
et au propriétaire. Les rapports joignent les deux ; les anciennes lignes restent
identiques sur disque et sont présentées avec trois valeurs nulles.

Pour un résultat déjà final, les champs historiques, l'état et la preuve sont
comparés strictement. Une mesure non nulle différente, ou l'ajout rétroactif d'une
mesure autrefois inconnue, sont refusés. Une mesure omise/null signifie « aucune
nouvelle observation » : elle n'efface jamais une mesure déjà enregistrée. Le
premier horodatage et les valeurs stockées restent immuables.

Le protocole Android de repli doit reconnaître positivement le contrat historique
du même serveur avant de retirer uniquement ces trois champs. Un simple 422,
un contrat inconnu ou le marqueur true ne permettent aucun repli. Le format de
transport négocié doit être persisté dans le journal chiffré avant son unique
retry ; les mesures complètes restent conservées localement. Aucun geste de
publication ne participe à ce retry.

Cette combinaison couvre les réponses perdues pendant les deux transitions :
ancien reçu accepté puis serveur mis à jour, et reçu complet accepté puis
rollback et remise à jour. Elle ne rétro-remplit jamais une preuve historique.

## Validation

Tests synthétiques : changement du primaire entre snapshot et réservation avec
et sans fallback Windows ; changement des permissions, média et révocation ;
retry hors recette avec réaffectation intercalée ou simple heartbeat, avec et sans
moteur Windows disponible, et conservation intégrale du reçu parent ;
bornes et types stricts ; isolation propriétaire ; reçu historique absent/null
inchangé ; impossibilité de rétro-remplir ; omission après rollback conservant
les mesures ; maximum complet insuffisant pour confirmer.

Après correction du retry, la passe ciblée du 8 octobre 2026 a réussi : 33 tests
sur recovery, cohérence de réservation, Android et progression des recettes.

Aucun téléphone, envoi réel, retry de publication ou reprise de scheduler n'est
exécuté par ces tests. La vérification physique d'une publication reste distincte.
