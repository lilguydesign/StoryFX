package com.formafx.storyfx.agent

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

interface QueueStore {
    fun read(): String
    fun write(value: String)
}

class DiagnosticRunner(private val api: AgentGateway, private val store: QueueStore) {
    fun synchronize(deviceId: String, heartbeat: JSONObject): String {
        val previous = JSONArray(store.read())
        if (previous.length() > 0) {
            drain(previous)
            api.post("/v1/devices/heartbeat", heartbeat)
            return "Événements en attente confirmés"
        }
        api.post("/v1/devices/heartbeat", heartbeat)
        val claim = api.post("/v1/agent/claim", JSONObject())
        val job = claim.optJSONObject("job") ?: return "Téléphone connecté • aucune tâche"
        validateJob(job, deviceId)
        val queue = JSONArray()
        for (stage in listOf("STARTED", "DIAGNOSTIC_CONFIRMED")) {
            queue.put(JSONObject().put("job_id", job.getString("id"))
                .put("event_id", UUID.randomUUID().toString())
                .put("lease_token", job.getString("lease_token"))
                .put("stage", stage).put("detail", "diagnostic_only"))
        }
        // Persist both event IDs before the first network call; retry those same IDs.
        store.write(queue.toString())
        drain(queue)
        return "Diagnostic confirmé • aucun statut publié"
    }

    private fun validateJob(job: JSONObject, deviceId: String) {
        check(job.getString("kind") == "diagnostic")
        check(job.getString("device_id") == deviceId)
        UUID.fromString(job.getString("id"))
        check(job.getString("lease_token").isNotBlank())
        check(Instant.parse(job.getString("expires_at")).isAfter(Instant.now()))
        check(Instant.parse(job.getString("lease_expires_at")).isAfter(Instant.now()))
    }

    private fun drain(queue: JSONArray) {
        while (queue.length() > 0) {
            val event = queue.getJSONObject(0)
            val payload = JSONObject(event.toString()).apply { remove("job_id") }
            val response = api.post("/v1/agent/jobs/${event.getString("job_id")}/events", payload)
            check(response.optBoolean("accepted", false))
            queue.remove(0)
            store.write(queue.toString())
        }
    }
}
