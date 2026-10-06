package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PublicationCountDeltaTest {
    @Test fun verifiesExactlyTheNewBatchEvenWithOlderStatusesAndPagination() {
        assertTrue(PublicationCountDelta.matches(0, 11, 11))
        assertTrue(PublicationCountDelta.matches(11, 22, 11))
        assertFalse(PublicationCountDelta.matches(11, 21, 11))
        assertFalse(PublicationCountDelta.matches(11, 23, 11))
    }
    @Test fun missingCountsOrExpiredOldRowsCannotConfirmTheBatch() {
        assertFalse(PublicationCountDelta.matches(null, 11, 11))
        assertFalse(PublicationCountDelta.matches(11, null, 11))
        assertFalse(PublicationCountDelta.matches(11, 11, 11))
        assertFalse(PublicationCountDelta.matches(0, 31, 31))
    }
}
