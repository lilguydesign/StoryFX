package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class PublicationVerificationTest {
    @Test fun uploadingThenPartialThenCompletedBatchIsReobservedWithoutAnyResend() {
        var time = 0L
        var passes = 0
        var observations = 0
        var scrolls = 0
        val evidence = mutableListOf<PublicationVerification.Evidence>()
        val verifier = PublicationVerification(10000, { time }, {}, { time += it })
        val result = verifier.verify(3, { passes++ }, {
            observations++
            when (passes) { 1 -> emptyList(); 2 -> listOf(0); else -> listOf(0, 1, 2) }
        }, { scrolls++; false }, evidence::add)
        assertEquals(PublicationVerification.Evidence(3, "recent_visible"), result)
        assertEquals(3, passes)
        assertEquals(3, observations)
        assertEquals(1, scrolls)
        assertEquals(listOf(0, 1, 3), evidence.map { it.count })
        assertEquals(2000L, time)
    }

    @Test fun anUploadThatNeverCompletesExpiresAtTheExistingGlobalDeadline() {
        var time = 208000L
        var passes = 0
        val evidence = mutableListOf<PublicationVerification.Evidence>()
        val verifier = PublicationVerification(210000, { time }, {}, { time += it })
        val progress = PublicationProgress().apply { beforeProviderSend(); enter("own_status_verification") }
        assertThrows(IllegalStateException::class.java) {
            verifier.verify(9, { passes++ }, { emptyList() }, { error("no completed rows to scroll") }, evidence::add)
        }
        assertEquals(210000L, time)
        assertEquals(2, passes)
        assertTrue(evidence.all { it.count == 0 && it.method == "none" })
        assertEquals("NEEDS_REVIEW" to "result_uncertain", progress.failure())
    }

    @Test fun shiftingPositionsFromDifferentPassesAreNeverCombinedIntoFalseConfirmation() {
        var time = 0L
        var pass = 0
        val verifier = PublicationVerification(3000, { time }, {}, { time += it })
        assertThrows(IllegalStateException::class.java) {
            verifier.verify(2, { pass++ }, { listOf(pass) }, { false }, {
                assertEquals("none", it.method)
                assertEquals(1, it.count)
            })
        }
        assertEquals(3, pass)
    }

    @Test fun differentPagesCannotProveIdentityOrCompleteAPartiallyVisibleBatch() {
        var time = 0L
        var page = 0
        var passes = 0
        val evidence = mutableListOf<PublicationVerification.Evidence>()
        assertThrows(IllegalStateException::class.java) {
            PublicationVerification(3000, { time }, {}, { time += it }).verify(3,
                { passes++; page = 0 }, { if (page == 0) listOf(0, 1) else listOf(2) },
                { if (page == 0) { page++; true } else false }, evidence::add)
        }
        assertTrue(evidence.all { it.method == "none" && it.count < 3 })
        assertEquals(2, passes)
    }

    @Test fun sameStatusMovingFromIndexZeroToOneBetweenPagesNeverBecomesTwoStatuses() {
        var time = 0L
        var page = 0
        val evidence = mutableListOf<PublicationVerification.Evidence>()
        assertThrows(IllegalStateException::class.java) {
            PublicationVerification(3000, { time }, {}, { time += it }).verify(2,
                { page = 0 }, { listOf(page) }, { page++; page <= 1 }, evidence::add)
        }
        assertTrue(evidence.size >= 2)
        assertTrue(evidence.all { it == PublicationVerification.Evidence(1, "none") })
    }

    @Test fun duplicatedPositionInOneObservationIsNotOverstatedInDiagnostics() {
        var time = 0L
        val evidence = mutableListOf<PublicationVerification.Evidence>()
        assertThrows(IllegalStateException::class.java) {
            PublicationVerification(1000, { time }, {}, { time += it }).verify(2,
                {}, { listOf(0, 0) }, { error("must not scroll an ambiguous full-size observation") }, evidence::add)
        }
        assertEquals(listOf(PublicationVerification.Evidence(1, "none")), evidence)
    }

    @Test fun deadlineExceededInsideAuthorizationOrUiObservationCannotConfirm() {
        var time = 0L
        val stalledAuthorization = PublicationVerification(1000, { time }, { time = 1000 }, {})
        assertThrows(IllegalStateException::class.java) {
            stalledAuthorization.verify(1, { error("must not navigate") }, { listOf(0) }, { false }, {})
        }
        time = 0
        val stalledUi = PublicationVerification(1000, { time }, {}, {})
        assertThrows(IllegalStateException::class.java) {
            stalledUi.verify(1, {}, { time = 1000; listOf(0) }, { false }, { error("must not confirm") })
        }
    }
}
