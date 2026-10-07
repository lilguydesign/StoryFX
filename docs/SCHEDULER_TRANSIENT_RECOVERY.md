# Contrôle temporairement indisponible — 7 octobre 2026

Une erreur AUTH_UNAVAILABLE (503) ou RATE_LIMITED (429) lors du contrôle
d'identité mettait définitivement la planification en pause. Le contrôle du
7 octobre a observé CONTROL_UNAVAILABLE ; le code initial précis n'était pas
conservé et ne peut pas être attribué rétrospectivement à un fournisseur.

Le scheduler conserve désormais sa génération active lors de ces deux erreurs
temporaires seulement. Il n'émet aucune nouvelle réservation pendant l'échec,
conserve les tâches existantes et revérifie l'identité propriétaire complète
après 30, 60, 120, 240 puis 300 secondes au maximum. Le délai, le code fermé,
le statut et le nombre d'échecs sont persistés dans control_scheduler_waits.
Une récupération validée produit SCHEDULER_CONTROL_RESUMED dans le terminal.

Les refus 401/403, la révocation propriétaire, les changements de configuration
et les erreurs non classifiées continuent de mettre en pause. Un arrêt humain
ou une nouvelle génération ne sont jamais annulés par une attente ancienne.
Aucune tâche confirmée, incertaine, échouée ou déjà reprise n'est rejouée par
ce mécanisme. Les reprises avant envoi restent des actions explicites via les
gardes de control_recovery ; le journal initial est conservé.

## Maintenance et preuves

- Application : StoryFX, moteur serveur DB02, contrôle toutes les dix secondes.
- Sonde : ops/maintenance/storyfx_scheduler_recovery_probe.py, lecture SQLite
  mode=ro/query_only du propriétaire déjà associé au suivi ; aucun USB requis.
- Attente normale : identité temporairement indisponible, prochain contrôle
  entre maintenant et cinq minutes ; aucun envoi autorisé par cette sonde.
- Incident : pause technique persistante, ou échéance de contrôle dépassée
  de plus d'une minute. Arrêt volontaire sans motif : disabled.
- Diagnostic : lire le code fermé, délai, compteur et résultat de publication.
  Ne pas assimiler un timer actif à une publication réussie.
- Réparation : rétablir le service d'identité ; la génération encore active
  reprend uniquement après revalidation. Une ancienne pause définitive doit
  être redémarrée explicitement avec les contrôles normaux.
- Rollback : précédent release backend et sauvegarde SQLite via l'installateur
  existant. La table d'attente est additive et peut rester présente au rollback.
- Notifications : préserver le catalogue illustré et le quota Maintenance
  existants, maximum un WhatsApp toutes les deux heures ; aucun test d'alerte.
- Limites : Facebook/TikTok natifs non implémentés ; aucun résultat Facebook
  par page ou nombre d'images n'est certifié par cette sonde.

Validation : tests synthétiques d'attente durable, délais bornés, absence de
dispatch pendant l'erreur, refus persistants et préservation de l'arrêt humain.
La preuve réelle post-déploiement est enregistrée dans delivery, hors Git.
