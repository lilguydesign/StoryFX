package com.formafx.storyfx.agent.publication

import com.formafx.storyfx.agent.AgentGateway
import com.formafx.storyfx.agent.AgentRequestException
import org.json.JSONObject

/** Negotiates optional telemetry only. No claim, receipt, unlock or provider action is available here. */
class PublicationHeartbeat(private val api: AgentGateway, private val runtimeSupported: () -> Boolean?) {
    fun send(body: JSONObject): JSONObject {
        val path = "/v1/control/android/heartbeat"
        val copy = JSONObject(body.toString())
        try { return api.post(path, copy) } catch (failure: AgentRequestException) {
            if (failure.status != 422 || !copy.has("native_runtime") || runtimeSupported() != false) throw failure
        }
        // A positively recognised old backend cannot consume v1 physical telemetry.
        // Its only readiness field must also represent the local global stop.
        if (copy.getJSONObject("native_runtime").getBoolean("global_enabled") == false) {
            copy.put("service_ready", false).put("media_modes_ready", false)
        }
        copy.remove("native_runtime")
        try { return api.post(path, copy) } catch (failure: AgentRequestException) {
            if (failure.status != 422) throw failure
        }
        // Preserve the older optional-field fallback, only on that recognised historical server.
        copy.remove("own_status_empty")
        copy.remove("media_modes_ready")
        return api.post(path, copy)
    }
}
