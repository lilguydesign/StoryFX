# Recette du premier jalon

## Contrôles proportionnés

Les tests serveur utilisent des identités et tâches synthétiques. Ils couvrent
les permissions propriétaire/appareil, l'association à usage unique et son
expiration, la révocation, la rotation de clé jusque dans la transaction,
les occurrences uniques, les tâches futures, l'expiration, les claims
concurrents, les événements répétés et contradictoires, les transitions,
les résultats tardifs, le redémarrage et l'absence de secrets dans SQLite.

Le smoke local appelle les vrais endpoints HTTP : santé du stockage et du
worker, enrôlement, heartbeat, diagnostic, replay des événements, confirmation,
aperçu inactif, ressources du dashboard et révocation. Il n'importe pas le
moteur Windows et ne contacte aucune plateforme sociale.

La sonde FX Maintenance locale évalue la santé et les baux depuis ce protocole.
Son catalogue annonce explicitement l'absence de déploiement et de couverture
permanente. Les contrôles et le quota des notifications existantes sont conservés.

## Conditions avant déploiement Internet

- Authentification réelle des comptes FormaFX et permissions par appareil.
- Remplacement de la clé de laboratoire ; limitation des origines et HTTPS.
- Stockage de production, sauvegarde restaurable, service et sonde attestés.
- Politique de reprise et capacités du téléphone mesurées sur appareil.
- Vérification de l'identité physique lors de l'association des anciens profils.
- Validation d'un parcours sans publication, puis essai réel explicitement demandé.

Ce jalon n'active aucun planning existant, ne coupe pas le scheduler Windows
et ne déploie pas une automatisation incomplète sur DB02. Le build Android ne
constitue pas une validation de publication WhatsApp/Facebook/Instagram/TikTok.
Le passage Wi-Fi vers données mobiles, la veille prolongée, le redémarrage d'un
téléphone physique et la précision des créneaux restent à vérifier.

## Reprise et rollback

Une perte de bail produit `NEEDS_REVIEW` ; aucun second exécuteur n'est lancé
automatiquement. Le même journal du même bail peut résoudre le diagnostic.
Une annulation explicite invalide ce bail et débloque la file. Une réassociation
invalide l'ancien jeton et ses baux. Ce comportement de diagnostic ne permet
pas de rejouer une future publication dont le résultat serait ambigu.

Le premier jalon est ajouté en modules séparés. Revenir au commit précédent
ou arrêter le seul processus StoryFX de diagnostic restaure le périmètre
historique ; la transmission et le programme Windows d'origine sont préservés.
Ne pas fermer d'autres applications, tuer ADB globalement ni effacer l'historique.

Les résultats exacts, chemins d'APK, captures, PR et limites observées sont
consignés dans le `FINAL_REPORT.txt` livré avec le pack du jalon.
