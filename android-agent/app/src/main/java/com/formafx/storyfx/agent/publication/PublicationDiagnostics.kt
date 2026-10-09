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
    private var verificationStarted = false
    private var verificationObservations = 0
    private var peakVerified: Int? = null
    private var sequential: JSONObject? = null

    fun beginVerification() { verificationStarted = true }

    fun observeVerification(evidence: PublicationVerification.Evidence) {
        if (sequential == null) {
            verified = evidence.count
            verification = evidence.method
        }
        // This is a maximum of individual views, never a sum or an identity-based proof.
        peakVerified = maxOf(peakVerified ?: 0, evidence.count)
        verificationObservations = (verificationObservations + 1).coerceAtMost(3000)
    }

    fun recordSequential(proof: JSONObject, complete: Boolean) {
        sequential = JSONObject(proof.toString())
        val counts = proof.getJSONArray("verified_counts")
        verified = (0 until counts.length()).sumOf(counts::getInt)
        verification = if (complete) SequentialPublication.METHOD else "none"
    }

    fun snapshot(runtime: JSONObject): JSONObject = JSONObject(runtime.toString())
        .put("expected_count", expected).put("selected_count", selected)
        .put("verified_count", verified).put("stage", stage)
        .put("navigation_state", navigation).put("own_label_count", ownLabels.coerceIn(0, 2500))
        .put("provider_package", if (provider) "whatsapp_business" else "unknown")
        .put("account_verified", false).put("verification_method", verification)
        .put("verification_started", verificationStarted).put("verification_observations", verificationObservations)
        .put("peak_verified_count", peakVerified)
        .put("sequential_proof", sequential)
        .put("elapsed_ms", ((now() - started) / 1_000_000).coerceIn(0, 900000))
}
