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
        require(payload.getString("platform") == "WhatsApp")
        require(payload.getInt("count") in 1..30)
        require(optionalText(payload, "page").isBlank() && optionalText(payload, "page_name").isBlank())
        require(!Instant.parse(payload.getString("due_at")).isAfter(Instant.now()))
        MediaPlan.parts(payload)
        return payload
    }

    // Android's JSONObject coerces JSONObject.NULL to the literal "null"; JVM test JSON differs.
    // Read the value explicitly so a missing optional destination never becomes a real destination.
    fun optionalText(payload: JSONObject, key: String): String {
        if (payload.isNull(key)) return ""
        val value = payload.opt(key)
        require(value is String)
        return value
    }
    fun album(payload: JSONObject) = optionalText(payload, "album2").ifBlank { optionalText(payload, "album") }
}
