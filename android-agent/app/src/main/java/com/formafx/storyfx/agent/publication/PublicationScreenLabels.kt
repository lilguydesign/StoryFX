package com.formafx.storyfx.agent.publication

/** Exact provider labels only. Contact names and approximate matches are never accepted. */
object PublicationScreenLabels {
    fun emptyOwn(text: String, description: String) =
        listOf(text, description).any { it in setOf("Add status", "Ajouter un statut") }
    private val updates = setOf("Updates", "Actus", "Mises à jour")
    private val own = setOf("My status", "Mon statut")
    fun updates(text: String, description: String) = text in updates || description in updates
    fun own(text: String, description: String) = text in own || description in own
}
