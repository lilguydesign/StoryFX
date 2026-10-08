package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class PublicationRowEvidenceTest {
    private fun row(stamps: Int = 1, views: Int = 1, pending: Boolean = false,
                    index: Int? = null, complete: Boolean = true) =
        PublicationRowEvidence.Ancestor(stamps, views, pending, index, complete)

    @Test fun pendingSiblingOnCollectionRowCannotHideBehindACompletedInnerWrapper() {
        assertNull(PublicationRowEvidence.completed(listOf(row(), row(pending = true, index = 4))))
        assertEquals(4, PublicationRowEvidence.completed(listOf(row(), row(index = 4)))!!.rowIndex)
    }

    @Test fun unindexedRowsCanBeCountedButPartialTreesAndWholeListsCannot() {
        assertNotNull(PublicationRowEvidence.completed(listOf(row(views = 0), row())))
        assertNull(PublicationRowEvidence.completed(listOf(row(complete = false))))
        assertNull(PublicationRowEvidence.completed(listOf(row(stamps = 2, views = 2))))
        assertNull(PublicationRowEvidence.completed(listOf(row(views = 0))))
    }
}
