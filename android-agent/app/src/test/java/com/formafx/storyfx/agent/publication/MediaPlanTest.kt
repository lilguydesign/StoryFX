package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class MediaPlanTest {
    private fun payload(engine: String, count: Int = 11) = JSONObject().put("engine", engine).put("count", count)
        .put("album", "Validation technique introduction").put("album2", "Validation technique")

    @Test fun introIsOneVideoAndCombinationKeepsAllElevenAdditionalAssets() {
        assertEquals(listOf(MediaPlan.Part("Validation technique introduction", "video", 1)), MediaPlan.parts(payload("intro")))
        assertEquals(11, MediaPlan.total(payload("multi")))
        val combination = MediaPlan.parts(payload("intro+multi"))
        assertEquals("video", combination.first().kind)
        assertEquals("Validation technique", combination.last().album)
        assertEquals(11, combination.last().count)
        assertEquals(12, MediaPlan.total(payload("intro+multi")))
    }

    @Test fun missingIntroAlbumAndOversizedTotalRefuseTheWholeLotBeforeSelection() {
        assertThrows(IllegalArgumentException::class.java) { MediaPlan.parts(payload("intro+multi", 30)) }
        assertThrows(IllegalArgumentException::class.java) { MediaPlan.parts(payload("intro+multi").put("album", JSONObject.NULL)) }
        assertEquals(30, MediaPlan.total(payload("intro+multi", 29)))
        assertEquals(30, MediaPlan.total(payload("multi", 30)))
    }

    @Test fun bucketCollisionAndInsufficientAdditionalAssetsAreRejectedWithoutPartialLot() {
        fun item(uri: String, bucket: Long, added: Long, id: Long) = MediaSelection.Candidate(uri, bucket, added, id, "image")
        val items = listOf(item("intro", 1, 30, 3), item("second", 1, 20, 2), item("third", 1, 20, 1))
        assertEquals(listOf("second", "third"), MediaSelection.select(items, 2, setOf("intro")))
        assertThrows(IllegalArgumentException::class.java) { MediaSelection.select(items, 3, setOf("intro")) }
        assertThrows(IllegalArgumentException::class.java) { MediaSelection.select(items + item("other", 2, 40, 4), 1) }
        assertThrows(IllegalArgumentException::class.java) { MediaSelection.select(listOf(items.first(), items.first()), 2) }
    }

    @Test fun mixedMimeKeepsVideosAndImagesAndRefusesNonMediaFiles() {
        assertEquals("*/*", MediaPlan.shareMime(listOf("video/mp4", "image/jpeg")))
        assertEquals("video/*", MediaPlan.shareMime(listOf("video/mp4")))
        assertEquals("image/*", MediaPlan.shareMime(listOf("image/png", "image/jpeg")))
        assertThrows(IllegalArgumentException::class.java) { MediaPlan.shareMime(listOf("application/pdf")) }
        assertThrows(IllegalArgumentException::class.java) { MediaPlan.shareMime(emptyList()) }
    }
}
