package com.formafx.storyfx.agent.publication

import org.json.JSONObject

interface PublicationStateStore {
    fun publicationState(): String
    fun savePublicationState(value: String)
}

/** One encrypted atomic record: reserve before UI, acknowledge only after the server. */
class PublicationJournal(private val store: PublicationStateStore) {
    private fun state() = JSONObject(store.publicationState())
    fun pending(): JSONObject? = state().optJSONObject("pending")

    fun recordDiagnostics(diagnostics: JSONObject) {
        val value = state()
        val pending = value.getJSONObject("pending").put("diagnostics", diagnostics)
        value.getJSONObject("history").getJSONObject(pending.getString("occurrence_id")).put("diagnostics", diagnostics)
        store.savePublicationState(value.toString())
    }

    fun reserve(job: JSONObject): Boolean {
        val value = state()
        check(!value.has("pending"))
        val history = value.optJSONObject("history") ?: JSONObject()
        val occurrence = job.getString("occurrence_id")
        check(occurrence.matches(Regex("[a-f0-9]{64}")))
        check(history.length() < 1000)
        val prior = history.optJSONObject(occurrence)
        val result = prior ?: JSONObject().put("state", "NEEDS_REVIEW").put("evidence", "result_uncertain")
        history.put(occurrence, result)
        value.put("history", history).put("pending", JSONObject(result.toString())
            .put("job_id", job.getString("id")).put("occurrence_id", occurrence))
        store.savePublicationState(value.toString())
        return prior == null
    }

    fun finish(state: String, evidence: String, diagnostics: JSONObject? = null) {
        val value = state()
        val pending = value.getJSONObject("pending")
        pending.put("state", state).put("evidence", evidence)
        if (diagnostics != null) pending.put("diagnostics", diagnostics)
        value.getJSONObject("history").put(pending.getString("occurrence_id"),
            JSONObject().put("state", state).put("evidence", evidence).apply {
                if (diagnostics != null) put("diagnostics", diagnostics)
            })
        store.savePublicationState(value.toString())
    }

    fun acknowledged() {
        val value = state()
        value.remove("pending")
        store.savePublicationState(value.toString())
    }
}
