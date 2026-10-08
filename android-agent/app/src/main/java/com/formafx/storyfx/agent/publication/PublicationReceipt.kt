package com.formafx.storyfx.agent.publication

import com.formafx.storyfx.agent.AgentGateway
import com.formafx.storyfx.agent.AgentRequestException
import org.json.JSONObject

/** Retry acknowledgements only. This class has no access to provider gestures. */
class PublicationReceipt(private val api: AgentGateway, private val legacyContract: () -> Boolean) {
    fun flush(journal: PublicationJournal) {
        val pending = journal.pending() ?: return
        val body = JSONObject().put("state", pending.getString("state")).put("evidence", pending.getString("evidence"))
        pending.optJSONObject("diagnostics")?.let { body.put("diagnostics", it) }
        val path = "/v1/control/android/jobs/${pending.getString("job_id")}/complete"
        try { api.post(path, body) } catch (failure: AgentRequestException) {
            if (failure.status != 422 || !failure.invalidRequest || !body.has("diagnostics") ||
                !legacyContract()) throw failure
            // Preserve the encrypted diagnostic; omit it only for a recognized older schema.
            body.remove("diagnostics")
            api.post(path, body)
        }
        journal.acknowledged()
    }
}
