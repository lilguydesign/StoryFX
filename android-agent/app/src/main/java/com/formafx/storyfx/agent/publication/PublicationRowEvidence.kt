package com.formafx.storyfx.agent.publication

/** Ancestors are nearest first. A collection row, when available, owns all its wrappers. */
object PublicationRowEvidence {
    data class Ancestor(val stamps: Int, val views: Int, val pending: Boolean,
                        val rowIndex: Int?, val complete: Boolean = true)
    data class Completed(val rowIndex: Int?)

    fun completed(ancestors: List<Ancestor>): Completed? {
        val row = ancestors.firstOrNull { it.rowIndex != null } ?:
            ancestors.firstOrNull { it.views > 0 } ?: return null
        if (!row.complete || !PublicationProof.row(row.stamps, row.views, row.pending)) return null
        return Completed(row.rowIndex)
    }
}
