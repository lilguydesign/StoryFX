package com.formafx.storyfx.agent.publication

/** Once a provider send control is approached, a failure requires human review. */
class PublicationProgress {
    private var stage = "album_media_unavailable"
    private var sendApproached = false

    fun enter(value: String) {
        require(value in stages)
        stage = value
    }

    fun beforeProviderSend() { sendApproached = true }

    fun failure(): Pair<String, String> = if (sendApproached) {
        "NEEDS_REVIEW" to "result_uncertain"
    } else {
        "FAILED_BEFORE_PUBLICATION" to stage
    }

    private companion object {
        val stages = setOf("album_media_unavailable", "provider_not_ready",
            "updates_navigation_failed", "own_status_unavailable",
            "share_selection_refused", "contacts_preview_refused", "own_status_verification")
    }
}
