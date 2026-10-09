package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PublicationDiagnosticsTest {
    @Test fun aSliceProofCannotMasqueradeAsTheWholeBatchDuringAnInterruptedSave() {
        val diagnostic = PublicationDiagnostics().apply { expected = 11; selected = 11 }
        val proof = JSONObject().put("contract_version", 1).put("verified_counts", org.json.JSONArray())
        diagnostic.recordSequential(proof, false)
        diagnostic.observeVerification(PublicationVerification.Evidence(9, "recent_visible"))
        val partial = diagnostic.snapshot(JSONObject())
        assertEquals("none", partial.getString("verification_method"))
        assertEquals(0, partial.getInt("verified_count"))
        assertEquals(9, partial.getInt("peak_verified_count"))
        proof.put("verified_counts", org.json.JSONArray(listOf(9, 2)))
        diagnostic.recordSequential(proof, true)
        val complete = diagnostic.snapshot(JSONObject())
        assertEquals(11, complete.getInt("verified_count"))
        assertEquals(9, complete.getInt("peak_verified_count"))
        assertEquals(SequentialPublication.METHOD, complete.getString("verification_method"))
        assertFalse(complete.getBoolean("account_verified"))
    }
    @Test fun countUnknownIsAbsentAndDurationIsBounded() {
        var clock = 0L
        val diagnostics = PublicationDiagnostics { clock }
        diagnostics.expected = 9
        clock = 2_000_000_000_000L
        val result = diagnostics.snapshot(JSONObject().put("network", "unknown"))
        assertEquals(9, result.getInt("expected_count"))
        assertFalse(result.has("selected_count"))
        assertFalse(result.has("verified_count"))
        assertFalse(result.getBoolean("account_verified"))
        assertFalse(result.getBoolean("verification_started"))
        assertEquals(0, result.getInt("verification_observations"))
        assertFalse(result.has("peak_verified_count"))
        assertEquals(900000, result.getInt("elapsed_ms"))
    }

    @Test fun lastViewCanReturnToZeroWhilePeakRemainsOneActualView() {
        var time = 0L
        val diagnostics = PublicationDiagnostics { time * 1_000_000 }.apply { expected = 12; beginVerification() }
        var observation = 0
        assertThrows(IllegalStateException::class.java) {
            PublicationVerification(3000, { time }, {}, { time += it }).verify(12, {}, {
                when (observation++) { 1 -> (0 until 8).toList(); else -> emptyList() }
            }, { false }, diagnostics::observeVerification)
        }
        val result = diagnostics.snapshot(JSONObject())
        assertEquals(0, result.getInt("verified_count"))
        assertEquals(8, result.getInt("peak_verified_count"))
        assertEquals(3, result.getInt("verification_observations"))
        assertTrue(result.getBoolean("verification_started"))
        assertEquals("none", result.getString("verification_method"))
        assertEquals(3000, result.getInt("elapsed_ms"))
    }

    @Test fun differentPagesCannotAccumulateIntoPeakOrConfirmation() {
        var time = 0L
        var page = 0
        val diagnostics = PublicationDiagnostics().apply { expected = 12; beginVerification() }
        assertThrows(IllegalStateException::class.java) {
            PublicationVerification(3000, { time }, {}, { time += it }).verify(12,
                { page = 0 }, { if (page == 0) (0 until 8).toList() else (8 until 12).toList() },
                { if (page++ == 0) true else false }, diagnostics::observeVerification)
        }
        val result = diagnostics.snapshot(JSONObject())
        assertEquals(8, result.getInt("peak_verified_count"))
        assertTrue(result.getInt("verification_observations") >= 2)
        assertEquals("none", result.getString("verification_method"))
    }

    @Test fun startingVerificationDoesNotInventAnObservationAndObservationCountIsBounded() {
        val diagnostics = PublicationDiagnostics().apply { beginVerification() }
        val initial = diagnostics.snapshot(JSONObject())
        assertFalse(initial.has("peak_verified_count"))
        assertEquals(0, initial.getInt("verification_observations"))
        repeat(3001) { diagnostics.observeVerification(PublicationVerification.Evidence(0, "none")) }
        assertEquals(3000, diagnostics.snapshot(JSONObject()).getInt("verification_observations"))
    }
}
