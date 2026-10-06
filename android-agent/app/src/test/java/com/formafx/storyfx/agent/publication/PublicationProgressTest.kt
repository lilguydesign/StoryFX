package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertEquals
import org.junit.Test

class PublicationProgressTest {
    @Test fun capturesExactFailureBeforeSend() {
        val progress = PublicationProgress()
        assertEquals("FAILED_BEFORE_PUBLICATION" to "album_media_unavailable", progress.failure())
        progress.enter("updates_navigation_failed")
        assertEquals("FAILED_BEFORE_PUBLICATION" to "updates_navigation_failed", progress.failure())
    }

    @Test fun uncertaintyCannotBeResetByAnotherStage() {
        val progress = PublicationProgress()
        progress.beforeProviderSend()
        progress.enter("contacts_preview_refused")
        assertEquals("NEEDS_REVIEW" to "result_uncertain", progress.failure())
        progress.enter("own_status_unavailable")
        assertEquals("NEEDS_REVIEW" to "result_uncertain", progress.failure())
    }

    @Test(expected = IllegalArgumentException::class)
    fun refusesUnknownFailureEvidence() { PublicationProgress().enter("unknown") }
}
