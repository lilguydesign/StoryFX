package com.formafx.storyfx.agent.publication

import org.json.JSONObject

/** Count describes the multi batch. The intro adds one video, always first. */
object MediaPlan {
    data class Part(val album: String, val kind: String, val count: Int)

    fun parts(payload: JSONObject): List<Part> {
        val engine = payload.getString("engine")
        val count = payload.getInt("count")
        require(count in 1..30)
        val intro = PublicationPolicy.optionalText(payload, "album")
        val multi = PublicationPolicy.optionalText(payload, "album2").ifBlank { intro }
        val result = when (engine) {
            "intro" -> listOf(Part(intro, "video", 1))
            "multi" -> listOf(Part(multi, "mixed", count))
            "intro+multi" -> listOf(Part(intro, "video", 1), Part(multi, "mixed", count))
            else -> throw IllegalArgumentException("UNSUPPORTED_MEDIA_MODE")
        }
        require(result.all { it.album.isNotBlank() } && result.sumOf { it.count } <= 30)
        return result
    }

    fun total(payload: JSONObject) = parts(payload).sumOf { it.count }

    fun shareMime(types: List<String>): String {
        require(types.isNotEmpty() && types.all { it.startsWith("image/") || it.startsWith("video/") })
        return if (types.all { it.startsWith("image/") }) "image/*" else
            if (types.all { it.startsWith("video/") }) "video/*" else "*/*"
    }
}
