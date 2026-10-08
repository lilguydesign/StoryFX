package com.formafx.storyfx.agent.publication

import com.formafx.storyfx.agent.AgentGateway
import com.formafx.storyfx.agent.AgentRequestException
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PublicationReceiptTest {
    private class Memory : PublicationStateStore {
        var value = "{}"
        override fun publicationState() = value
        override fun savePublicationState(value: String) { this.value = value }
    }
    private fun job() = JSONObject().put("id", "00000000-0000-0000-0000-000000000001")
        .put("occurrence_id", "a".repeat(64))
    private fun journal(): PublicationJournal = PublicationJournal(Memory()).apply {
        reserve(job())
        finish("NEEDS_REVIEW", "result_uncertain", JSONObject().put("selected_count", 9))
    }

    @Test fun oldServerReceivesOneReceiptRetryAndLocalEvidenceSurvives() {
        val journal = journal()
        val bodies = mutableListOf<JSONObject>()
        val api = object : AgentGateway {
            override fun post(path: String, body: JSONObject): JSONObject {
                assertTrue(path.endsWith("/complete"))
                bodies.add(JSONObject(body.toString()))
                if (bodies.size == 1) throw AgentRequestException(422, true)
                return JSONObject()
            }
        }
        PublicationReceipt(api) { true }.flush(journal)
        assertEquals(2, bodies.size)
        assertTrue(bodies[0].has("diagnostics"))
        assertFalse(bodies[1].has("diagnostics"))
        assertNull(journal.pending())
        assertFalse(journal.reserve(job()))
        assertEquals(9, journal.pending()!!.getJSONObject("diagnostics").getInt("selected_count"))
    }

    @Test fun newUnknownOrUnavailableServerNeverDowngradesAValidationFailure() {
        val journal = journal()
        var calls = 0
        val api = object : AgentGateway {
            override fun post(path: String, body: JSONObject): JSONObject {
                calls++; throw AgentRequestException(422, true)
            }
        }
        assertThrows(AgentRequestException::class.java) { PublicationReceipt(api) { false }.flush(journal) }
        assertEquals(1, calls)
        assertNotNull(journal.pending()!!.getJSONObject("diagnostics"))
    }

    @Test fun accessDenialNeverTriggersCapabilityProbeOrFallback() {
        val journal = journal()
        val api = object : AgentGateway {
            override fun post(path: String, body: JSONObject): JSONObject { throw AgentRequestException(403) }
        }
        assertThrows(AgentRequestException::class.java) {
            PublicationReceipt(api) { error("unexpected probe") }.flush(journal)
        }
        assertNotNull(journal.pending())
    }
}
