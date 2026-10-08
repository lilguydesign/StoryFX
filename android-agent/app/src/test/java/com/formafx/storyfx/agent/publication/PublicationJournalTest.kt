package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PublicationJournalTest {
    private class Memory : PublicationStateStore {
        var value = "{}"
        override fun publicationState() = value
        override fun savePublicationState(value: String) { this.value = value }
    }
    private fun job() = JSONObject().put("id", "00000000-0000-0000-0000-000000000001")
        .put("occurrence_id", "a".repeat(64))

    @Test fun crashBeforeFinalActionIsNeverResumed() {
        val memory = Memory()
        assertTrue(PublicationJournal(memory).reserve(job()))
        val afterRestart = PublicationJournal(memory)
        assertEquals("NEEDS_REVIEW", afterRestart.pending()!!.getString("state"))
        afterRestart.acknowledged()
        assertFalse(PublicationJournal(memory).reserve(job()))
        assertEquals("NEEDS_REVIEW", PublicationJournal(memory).pending()!!.getString("state"))
    }
    @Test fun confirmedPublicationAndAcknowledgementSurviveRestart() {
        val memory = Memory()
        val journal = PublicationJournal(memory)
        journal.reserve(job()); journal.finish("CONFIRMED", "own_status_verified")
        assertEquals("CONFIRMED", PublicationJournal(memory).pending()!!.getString("state"))
        journal.acknowledged()
        assertNull(PublicationJournal(memory).pending())
        assertFalse(PublicationJournal(memory).reserve(job()))
        assertEquals("CONFIRMED", PublicationJournal(memory).pending()!!.getString("state"))
    }
    @Test fun secondClaimCannotOverwriteAnUnacknowledgedResult() {
        val memory = Memory()
        val journal = PublicationJournal(memory)
        journal.reserve(job())
        val saved = memory.value
        assertThrows(IllegalStateException::class.java) { journal.reserve(job().put("occurrence_id", "b".repeat(64))) }
        assertEquals(saved, memory.value)
    }

    @Test fun closedDiagnosticsSurviveCrashWithoutChangingTheUncertainReservation() {
        val memory = Memory()
        val journal = PublicationJournal(memory)
        journal.reserve(job())
        journal.recordDiagnostics(JSONObject().put("stage", "own_status_verification").put("selected_count", 9))
        val pending = PublicationJournal(memory).pending()!!
        assertEquals("NEEDS_REVIEW", pending.getString("state"))
        assertEquals(9, pending.getJSONObject("diagnostics").getInt("selected_count"))
        journal.finish("CONFIRMED", "own_status_verified", JSONObject().put("verified_count", 9))
        journal.acknowledged()
        assertFalse(journal.reserve(job()))
        assertEquals(9, journal.pending()!!.getJSONObject("diagnostics").getInt("verified_count"))
    }
}
