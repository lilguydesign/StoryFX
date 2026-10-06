package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PublicationPolicyTest {
    private fun job(): JSONObject = JSONObject().put("id", "00000000-0000-0000-0000-000000000001")
        .put("occurrence_id", "a".repeat(64)).put("payload", JSONObject()
            .put("device", "Validation technique").put("execution_origin", "web_android_agent")
            .put("web_triggered", true).put("platform", "WhatsApp").put("engine", "multi")
            .put("count", 3).put("due_at", "2020-01-01T00:00:00Z").put("album", "Validation technique"))

    @Test fun wrongPhoneOrProviderOrFutureCommandCannotStart() {
        for ((key, value) in listOf("device" to "Autre appareil", "platform" to "Facebook",
            "engine" to "intro", "due_at" to "2999-01-01T00:00:00Z", "page_name" to "Autre destination",
            "web_triggered" to false, "execution_origin" to "web_windows_bridge")) {
            val input = job(); input.getJSONObject("payload").put(key, value)
            assertThrows(IllegalArgumentException::class.java) { PublicationPolicy.validate(input, "Validation technique") }
        }
    }
    @Test fun videosAndOversizedBatchesAreExcluded() {
        for ((key, value) in listOf("album2" to "Video", "system" to "video", "count" to 31, "count" to 0)) {
            val input = job(); input.getJSONObject("payload").put(key, value)
            assertThrows(IllegalArgumentException::class.java) { PublicationPolicy.validate(input, "Validation technique") }
        }
        assertEquals(3, PublicationPolicy.validate(job(), "Validation technique").getInt("count"))
    }
    @Test fun optionalNullsAreBlankAndAlbumFallsBackWithoutCoercion() {
        val input = job()
        val payload = input.getJSONObject("payload")
        for (key in listOf("page", "page_name", "album2", "system")) payload.put(key, JSONObject.NULL)
        assertEquals(3, PublicationPolicy.validate(input, "Validation technique").getInt("count"))
        assertEquals("Validation technique", PublicationPolicy.album(payload))
        assertEquals("", PublicationPolicy.optionalText(payload, "page_name"))
    }
    @Test fun optionalDestinationTypesAndLiteralNullTextAreNotAcceptedAsBlank() {
        for (value in listOf(42, true, "null")) {
            val input = job(); input.getJSONObject("payload").put("page_name", value)
            assertThrows(IllegalArgumentException::class.java) { PublicationPolicy.validate(input, "Validation technique") }
        }
    }
}
