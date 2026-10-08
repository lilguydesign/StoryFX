package com.formafx.storyfx.agent

import org.json.JSONObject

/** Compatibility is positively identified; a validation failure never disables new guards. */
object AgentErrorPolicy {
    fun invalidRequest(error: JSONObject) = error.opt("error") == "INVALID_REQUEST"

    fun legacyCompletionContract(health: JSONObject): Boolean =
        health.opt("status") == "ok" && health.opt("version") == "0.3.0" &&
            health.opt("mode") == "diagnostic_only" && health.opt("publishing_enabled") == false &&
            health.opt("account_auth_enabled") == true && health.opt("control_center_mode") == "windows_bridge" &&
            health.opt("android_publication_enabled") == true && health.opt("android_executor") == "whatsapp_images_pilot" &&
            health.opt("publication_failure_stages") == true && health.opt("manual_android_retry_available") == true &&
            health.opt("android_media_modes_min_version") == "0.4.13" &&
            (!health.has("structured_attempt_diagnostics") || health.opt("structured_attempt_diagnostics") == false)
}
