package com.formafx.storyfx.agent.publication

import com.formafx.storyfx.agent.AgentGateway
import com.formafx.storyfx.agent.AgentRequestException
import com.formafx.storyfx.agent.CompletionCompatibility
import org.json.JSONObject

/** Retry acknowledgements only. This class has no access to provider gestures. */
class PublicationReceipt(private val api: AgentGateway, private val compatibility: () -> CompletionCompatibility) {
    fun flush(journal: PublicationJournal) {
        val pending = journal.pending() ?: return
        val format = journal.receiptFormat()
        val body = receiptBody(pending, format)
        val path = "/v1/control/android/jobs/${pending.getString("job_id")}/complete"
        try { api.post(path, body) } catch (failure: AgentRequestException) {
            // A rollback must retain the full new proof locally, never downgrade its meaning.
            if (body.optJSONObject("diagnostics")?.has("sequential_proof") == true) throw failure
            if (failure.status != 422 || !failure.invalidRequest || !body.has("diagnostics") ||
                format != CompletionCompatibility.FULL) throw failure
            val negotiated = compatibility()
            if (negotiated == CompletionCompatibility.FULL || negotiated == CompletionCompatibility.WITHOUT_OBSERVATION_METRICS &&
                observationFields.none { body.getJSONObject("diagnostics").has(it) }) throw failure
            // Persist before the request: a lost response or restart must resend identical evidence.
            journal.rememberReceiptFormat(negotiated)
            // Retry only this same receipt once; all original evidence remains encrypted locally.
            api.post(path, receiptBody(pending, negotiated))
        }
        journal.acknowledged()
    }

    private fun receiptBody(pending: JSONObject, format: CompletionCompatibility): JSONObject {
        val body = JSONObject().put("state", pending.getString("state")).put("evidence", pending.getString("evidence"))
        if (format != CompletionCompatibility.WITHOUT_DIAGNOSTICS) pending.optJSONObject("diagnostics")?.let {
            val diagnostic = JSONObject(it.toString())
            if (format == CompletionCompatibility.WITHOUT_OBSERVATION_METRICS) observationFields.forEach(diagnostic::remove)
            body.put("diagnostics", diagnostic)
        }
        return body
    }

    private companion object {
        val observationFields = listOf("peak_verified_count", "verification_observations", "verification_started")
    }
}
