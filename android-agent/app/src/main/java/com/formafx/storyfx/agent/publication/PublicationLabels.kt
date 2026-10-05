package com.formafx.storyfx.agent.publication

object PublicationLabels {
    fun reason(value: String) = when (value) {
        "DISABLED" -> "Pilotage désactivé"
        "WAITING_PERMISSIONS" -> "En attente des autorisations Android"
        "ACCESSIBILITY_REQUIRED" -> "Activez le service Accessibilité StoryFX"
        "MEDIA_PERMISSION_REQUIRED" -> "Autorisez les photos des albums"
        "SCREEN_LOCKED" -> "Déverrouillez le téléphone et laissez l’écran allumé"
        "" -> "Prêt pour les tâches compatibles du serveur"
        else -> "En attente : consultez les rapports"
    }
}
