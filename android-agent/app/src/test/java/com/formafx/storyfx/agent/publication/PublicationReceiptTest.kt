package com.formafx.storyfx.agent.publication

import com.formafx.storyfx.agent.AgentGateway
import com.formafx.storyfx.agent.AgentRequestException
import com.formafx.storyfx.agent.CompletionCompatibility
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
        PublicationReceipt(api) { CompletionCompatibility.WITHOUT_DIAGNOSTICS }.flush(journal)
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
        assertThrows(AgentRequestException::class.java) { PublicationReceipt(api) { CompletionCompatibility.FULL }.flush(journal) }
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

    @Test fun structuredRollbackDropsOnlyObservationMetricsAndPreservesOriginalJournal() {
        val journal = journal()
        val full = JSONObject().put("expected_count", 12).put("selected_count", 12).put("verified_count", 0)
            .put("verification_method", "none").put("stage", "own_status_verification")
            .put("peak_verified_count", 8).put("verification_observations", 3).put("verification_started", true)
        journal.finish("NEEDS_REVIEW", "result_uncertain", full)
        val bodies = mutableListOf<JSONObject>()
        val paths = mutableListOf<String>()
        val api = object : AgentGateway {
            override fun post(path: String, body: JSONObject): JSONObject {
                paths.add(path); bodies.add(JSONObject(body.toString()))
                if (bodies.size == 1) throw AgentRequestException(422, true)
                return JSONObject()
            }
        }
        PublicationReceipt(api) { CompletionCompatibility.WITHOUT_OBSERVATION_METRICS }.flush(journal)
        assertEquals(2, bodies.size)
        assertEquals(paths[0], paths[1])
        val fallback = bodies[1].getJSONObject("diagnostics")
        assertFalse(fallback.has("peak_verified_count"))
        assertFalse(fallback.has("verification_observations"))
        assertFalse(fallback.has("verification_started"))
        for (key in listOf("expected_count", "selected_count", "verified_count", "verification_method", "stage"))
            assertEquals(full.get(key), fallback.get(key))
        assertEquals("NEEDS_REVIEW", bodies[1].getString("state"))
        assertFalse(journal.reserve(job()))
        assertEquals(8, journal.pending()!!.getJSONObject("diagnostics").getInt("peak_verified_count"))
    }

    @Test fun rejectedMetricFallbackIsNeverRetriedAgainOrAcknowledged() {
        val journal = journal()
        journal.finish("NEEDS_REVIEW", "result_uncertain", JSONObject().put("verification_started", true))
        var calls = 0
        val api = object : AgentGateway {
            override fun post(path: String, body: JSONObject): JSONObject {
                calls++; throw AgentRequestException(422, true)
            }
        }
        assertThrows(AgentRequestException::class.java) {
            PublicationReceipt(api) { CompletionCompatibility.WITHOUT_OBSERVATION_METRICS }.flush(journal)
        }
        assertEquals(2, calls)
        assertTrue(journal.pending()!!.getJSONObject("diagnostics").getBoolean("verification_started"))
    }

    @Test fun rollbackAcceptanceWithLostResponseThenRestartAndUpgradeKeepsSameWireReceipt() {
        val store = Memory()
        val journal = PublicationJournal(store).apply {
            reserve(job().put("receipt_format", "WITHOUT_DIAGNOSTICS"))
            finish("NEEDS_REVIEW", "result_uncertain", JSONObject().put("selected_count", 12)
                .put("verified_count", 0).put("peak_verified_count", 8)
                .put("verification_observations", 3).put("verification_started", true))
        }
        assertEquals(CompletionCompatibility.FULL, journal.receiptFormat())
        var calls = 0
        var accepted: JSONObject? = null
        val oldBackend = object : AgentGateway {
            override fun post(path: String, body: JSONObject): JSONObject {
                calls++
                if (calls == 1) throw AgentRequestException(422, true)
                assertEquals(CompletionCompatibility.WITHOUT_OBSERVATION_METRICS, PublicationJournal(store).receiptFormat())
                accepted = JSONObject(body.toString())
                throw java.net.SocketTimeoutException("Synthetic lost acknowledgement")
            }
        }
        assertThrows(java.net.SocketTimeoutException::class.java) {
            PublicationReceipt(oldBackend) { CompletionCompatibility.WITHOUT_OBSERVATION_METRICS }.flush(journal)
        }
        val restarted = PublicationJournal(store)
        assertEquals(8, restarted.pending()!!.getJSONObject("diagnostics").getInt("peak_verified_count"))
        val newBackend = object : AgentGateway {
            override fun post(path: String, body: JSONObject): JSONObject {
                calls++
                assertTrue(accepted!!.similar(body))
                return JSONObject()
            }
        }
        PublicationReceipt(newBackend) { error("Never renegotiate after a possibly accepted receipt") }.flush(restarted)
        assertEquals(3, calls)
        assertNull(restarted.pending())
        assertEquals(8, JSONObject(store.value).getJSONObject("history").getJSONObject("a".repeat(64))
            .getJSONObject("diagnostics").getInt("peak_verified_count"))
    }
}
