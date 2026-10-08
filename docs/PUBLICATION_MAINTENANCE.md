# StoryFX — observation des publications, 8 octobre 2026

La santé HTTPS et la présence de l'agent ne démontrent pas une publication.
La nouvelle sonde `ops/maintenance/storyfx_publication_probe.py` lit uniquement
le dernier état du collecteur StoryFX existant. Elle ne contacte aucun téléphone,
ne crée aucune tâche et ne relance aucune publication.

## Périmètre et interprétation

- Source : `/opt/formafx/storyfx/state/observation-state.json`, collecteur
  `storyfx-observation.timer` existant, intervalle de 30 minutes.
- Fuseau métier : Africa/Douala ; preuves horodatées Unix/UTC.
- Fraîcheur : 40 minutes au maximum pendant la fenêtre de sept jours.
- Retard de publication : verdict `late` produit par l'observateur après sa
  grâce de 15 minutes ; la sonde ne recalcule pas les échéances.
- Incidents : résultat incertain, échec avant envoi, occurrence prise en charge
  en retard, preuve périmée, violation du périmètre WhatsApp.
- Exclusions : absence d'échéance, attente, canal désactivé, adaptateur natif
  absent, occurrence hors mise en service ou hors scheduler actif.
- Une confirmation agent demeure une confirmation agent. Ni ces compteurs,
  ni un résultat `ok` de la sonde ne prouvent le bon compte, la livraison d'un
  lot complet, le fonctionnement écran éteint ou l'autonomie sans câble.
- Une observation terminée doit avoir atteint l'échéance et sa grâce finale.
  Ses incidents non résolus restent visibles ; sa fin ne transforme pas un
  résultat incertain en succès. Aucun bilan quatre heures n'est utilisé ici.

La sortie est limitée à des codes fermés, dates, booléens et compteurs par
verdict. Aucune ligne d'album, identité matérielle, référence privée de profil,
session, contenu de message ou secret n'est recopié dans les métriques.

## Intégration et statut de livraison

`storyfx_publication_install_contract.patch` ajoute exactement un import et
un appel à la sonde après le contrôle HTTPS déjà présent dans le collecteur.
Il refuse une intégration partielle ou des ancres modifiées et reste idempotent.
La copie canonique est dans `sendfx/ops/fx-maintenance` ; son `collector.py`
est raccordé localement. Le déploiement et le passage planifié ne sont pas
prouvés par cet ajout local. Les consigner après une vérification réelle.

Le fichier `storyfx_control_catalog.json`, déjà modifié avant ce chantier,
est conservé. La sonde `storyfx_week_observation_probe.py` garde sa mission
de santé du collecteur ; la nouvelle sonde porte les incidents de publication.

Le catalogue dédié est `storyfx_publication_catalog.json`. Les alertes restent
dans la catégorie StoryFX existante, avec le vrai logo et le modèle existants.
La politique globale conserve au maximum un WhatsApp toutes les deux heures,
la résolution silencieuse et la durabilité du quota ; aucun test d'envoi n'est
effectué. L'intégration ne modifie ni timer global ni scheduler StoryFX.

Réparation : lire les étapes et quantités documentées de la tentative, corriger
le défaut exact, tester isolément puis livrer. Avant tout essai réel ou reprise,
attendre que Jerry confirme la pause Windows/USB et vérifier l'absence d'autre
exécuteur. Ne rejouer ni résultat incertain, ni confirmé, ni déjà repris.

Rollback : restaurer la release Maintenance précédente et la préimage exacte
du collecteur. Garder observations, planning, journaux de tâches et quota.

## Comparaison statique des moteurs

Référence : `transmission/StoryFX_Transmission_20261003_130046/source`.
La référence possède les dix onglets Launcher, Pages, Profiles, Devices,
Systems, Matrix, Albums, Programmation, Locators et Reports. Le client Python
actuel n'affiche plus Reports ; le web possède Appareils et les neuf autres
sections, mais l'existence d'un menu ne démontre pas l'équivalence du moteur.
L'import web initialise Locators à vide. Les sélecteurs Android natifs sont
codés séparément ; éditer Locators ne prouve pas leur modification effective.

Le runner historique expose Facebook, WhatsApp, Instagram et TikTok ainsi que
les trois modes. L'adaptateur Windows commandé par le web accepte seulement
WhatsApp multi. L'adaptateur Android actuel est limité à WhatsApp ; les modes
intro et intro+multi exigent au moins 0.4.13 et les permissions médias adaptées.
Un clic Share Facebook ou Story TikTok historique ne constitue pas une preuve
du compte/page, de la livraison et du nombre complet ; TikTok natif reste absent.

La configuration locale conserve sept lignes CM et sept lignes CI, et les
sept lignes WhatsApp du profil S23+ sont désactivées. Les sept catégories ont
des lots de 11, 9, 11, 11, 11, 5 et 3 médias ; les première et troisième
ajoutent une introduction, soit des totaux de 12 et 12. Les références privées
des albums ne sont pas reproduites. Les counts matrice/albums locaux concordent.
Le legacy relit `album.count_per_post` à chaque plan, alors que le plan serveur
lit `matrix.count` : écart latent à traiter séparément sans changer silencieusement
l'identité des occurrences déjà réservées. Cette comparaison locale ne certifie
pas l'état du catalogue privé courant du serveur ni le téléphone actif.
