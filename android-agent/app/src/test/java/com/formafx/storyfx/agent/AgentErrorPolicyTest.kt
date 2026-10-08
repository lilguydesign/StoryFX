package com.formafx.storyfx.agent

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class AgentErrorPolicyTest {
    private fun historical() = JSONObject().put("status", "ok").put("version", "0.3.0")
        .put("mode", "diagnostic_only").put("publishing_enabled", false).put("account_auth_enabled", true)
        .put("control_center_mode", "windows_bridge").put("android_publication_enabled", true)
        .put("android_executor", "whatsapp_images_pilot").put("publication_failure_stages", true)
        .put("manual_android_retry_available", true).put("android_media_modes_min_version", "0.4.13")

    @Test fun onlyKnownHistoricalContractAllowsAnOldReceiptWithoutDiagnostics() {
        assertTrue(AgentErrorPolicy.legacyCompletionContract(historical()))
        assertTrue(AgentErrorPolicy.legacyCompletionContract(historical().put("structured_attempt_diagnostics", false)))
        assertFalse(AgentErrorPolicy.legacyCompletionContract(historical().put("structured_attempt_diagnostics", true)))
        assertFalse(AgentErrorPolicy.legacyCompletionContract(historical().put("structured_attempt_diagnostics", "false")))
        assertFalse(AgentErrorPolicy.legacyCompletionContract(JSONObject().put("status", "ok")))
        assertFalse(AgentErrorPolicy.legacyCompletionContract(historical().put("status", "degraded")))
        assertFalse(AgentErrorPolicy.legacyCompletionContract(historical().put("version", "0.3.1")))
        assertFalse(AgentErrorPolicy.legacyCompletionContract(historical().put("android_executor", "unknown")))
        assertFalse(AgentErrorPolicy.legacyCompletionContract(historical().put("account_auth_enabled", false)))
    }

    @Test fun businessRefusalsAreNotCompatibilitySignals() {
        assertTrue(AgentErrorPolicy.invalidRequest(JSONObject().put("error", "INVALID_REQUEST")))
        assertFalse(AgentErrorPolicy.invalidRequest(JSONObject().put("error", "COUNT_MISMATCH")))
        assertFalse(AgentErrorPolicy.invalidRequest(JSONObject()))
    }
}
