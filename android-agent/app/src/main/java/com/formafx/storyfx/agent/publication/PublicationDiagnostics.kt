package com.formafx.storyfx.agent.publication

import org.json.JSONObject

/** Closed attempt evidence only. Never stores screen labels, media, account or device IDs. */
class PublicationDiagnostics(private val now: () -> Long = System::nanoTime) {
    private val started = now()
    var expected = 0
    var selected: Int? = null
    var verified: Int? = null
    var stage = "album_media_unavailable"
    var navigation = "unknown"
    var ownLabels = 0
    var provider = false
    var verification = "none"

    fun snapshot(runtime: JSONObject): JSONObject = JSONObject(runtime.toString())
        .put("expected_count", expected).put("selected_count", selected)
        .put("verified_count", verified).put("stage", stage)
        .put("navigation_state", navigation).put("own_label_count", ownLabels.coerceIn(0, 2500))
        .put("provider_package", if (provider) "whatsapp_business" else "unknown")
        .put("account_verified", false).put("verification_method", verification)
        .put("elapsed_ms", ((now() - started) / 1_000_000).coerceIn(0, 900000))
}
