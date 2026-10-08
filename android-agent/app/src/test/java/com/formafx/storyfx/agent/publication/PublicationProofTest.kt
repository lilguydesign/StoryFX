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
        assertEquals("none", PublicationProof.verified(9, 0, emptySet()))
        assertEquals("none", PublicationProof.verified(9, 8, (0..7).toSet()))
        assertEquals("none", PublicationProof.verified(9, 10, (0..9).toSet()))
        assertEquals("none", PublicationProof.verified(9, 9, (0..9).toSet()))
        assertEquals("none", PublicationProof.verified(9, 10, (0..8).toSet()))
        assertEquals("recent_visible", PublicationProof.verified(9, 9, emptySet()))
        assertEquals("recent_rows", PublicationProof.verified(9, 4, (0..8).toSet()))
        assertEquals("none", PublicationProof.verified(31, 31, emptySet()))
    }

    @Test fun pendingLabelsAreClosedAndDoNotSerializePrivateText() {
        assertTrue(PublicationProof.pending("Sending…", ""))
        assertTrue(PublicationProof.pending("", "Retry"))
        assertFalse(PublicationProof.pending("0 views", ""))
        assertFalse(PublicationProof.pending("Validation technique", ""))
    }
}
