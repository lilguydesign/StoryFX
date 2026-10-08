package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class PublicationProofTest {
    @Test fun queuedRowsAndAmbiguousContainersNeverCountAsCompleted() {
        assertTrue(PublicationProof.row(1, 1, false))
        assertFalse(PublicationProof.row(1, 0, false))
        assertFalse(PublicationProof.row(1, 1, true))
        assertFalse(PublicationProof.row(2, 1, false))
        assertFalse(PublicationProof.row(1, 2, false))
    }

    @Test fun exactRecentCompletedCountIsRequiredRegardlessOfCollectionGrowth() {
        assertEquals("none", PublicationProof.verified(9, emptyList()))
        assertEquals("none", PublicationProof.verified(9, (0..7).toList()))
        assertEquals("none", PublicationProof.verified(9, (0..9).toList()))
        assertEquals("recent_visible", PublicationProof.verified(9, (0..8).toList()))
        assertEquals("recent_visible", PublicationProof.verified(3, listOf(null, null, null)))
        assertEquals("none", PublicationProof.verified(31, (0..30).toList()))
    }

    @Test fun duplicateOrInvalidPositionsWithinOneObservationCannotConfirm() {
        assertEquals("none", PublicationProof.verified(2, listOf(0, 0)))
        assertEquals("none", PublicationProof.verified(3, listOf(0, null, 0)))
        assertEquals("none", PublicationProof.verified(2, listOf(-1, 0)))
        assertEquals("recent_visible", PublicationProof.verified(3, listOf(0, 1, 2)))
    }

    @Test fun pendingLabelsAreClosedAndDoNotSerializePrivateText() {
        assertTrue(PublicationProof.pending("Sending…", ""))
        assertTrue(PublicationProof.pending("", "Retry"))
        assertFalse(PublicationProof.pending("0 views", ""))
        assertFalse(PublicationProof.pending("Validation technique", ""))
    }
}
