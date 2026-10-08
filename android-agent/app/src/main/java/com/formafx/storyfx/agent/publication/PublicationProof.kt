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

    /** Positions are not stable identities. Only one complete observation can confirm. */
    fun verified(requested: Int, completed: List<Int?>): String {
        val indexed = completed.filterNotNull()
        return if (requested in 1..30 && completed.size == requested &&
            indexed.all { it >= 0 } && indexed.size == indexed.distinct().size) "recent_visible" else "none"
    }
}
