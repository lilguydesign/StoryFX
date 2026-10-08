package com.formafx.storyfx.agent.publication

/** A collection size can include uploads. A recent completed row needs its views indicator. */
object PublicationProof {
    fun row(recentStamps: Int, viewIndicators: Int, pending: Boolean) =
        recentStamps == 1 && viewIndicators == 1 && !pending

    fun pending(text: String, description: String): Boolean = listOf(text, description).any { value ->
        val label = value.trim().lowercase()
        label in setOf("sending", "sending…", "sending...", "envoi en cours", "envoi en cours…",
            "envoi en cours...", "failed", "échec", "retry", "réessayer") ||
            label.startsWith("couldn't send") || label.startsWith("échec de l'envoi")
    }

    fun verified(requested: Int, visible: Int, accumulatedRows: Set<Int>): String = when {
        requested !in 1..30 -> "none"
        visible > requested || accumulatedRows.size > requested -> "none"
        visible == requested -> "recent_visible"
        accumulatedRows.size == requested -> "recent_rows"
        else -> "none"
    }
}
