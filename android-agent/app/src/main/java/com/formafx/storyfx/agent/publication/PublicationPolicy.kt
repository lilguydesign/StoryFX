package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import java.time.Instant
import java.util.UUID

object PublicationPolicy {
    const val provider = "com.whatsapp.w4b"
    fun validate(job: JSONObject, profile: String): JSONObject {
        UUID.fromString(job.getString("id"))
        require(job.getString("occurrence_id").matches(Regex("[a-f0-9]{64}")))
        val payload = job.getJSONObject("payload")
        require(payload.getString("device") == profile)
        require(payload.getString("execution_origin") == "web_android_agent")
        require(payload.getBoolean("web_triggered"))
        require(payload.getString("platform") == "WhatsApp" && payload.getString("engine") == "multi")
        require(payload.getInt("count") in 1..30)
        require(payload.optString("page").isBlank() && payload.optString("page_name").isBlank())
        require(!Instant.parse(payload.getString("due_at")).isAfter(Instant.now()))
        require(album(payload).isNotBlank())
        require(!("${payload.optString("system")}${album(payload)}").contains("video", ignoreCase = true))
        return payload
    }

    fun album(payload: JSONObject) = payload.optString("album2").ifBlank { payload.optString("album") }
}
