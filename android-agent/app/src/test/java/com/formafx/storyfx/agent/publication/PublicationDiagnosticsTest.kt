package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PublicationDiagnosticsTest {
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
        assertEquals(900000, result.getInt("elapsed_ms"))
    }
}
