package com.formafx.storyfx.agent.publication

import java.time.Instant
import java.time.ZoneId
import kotlin.random.Random
import org.junit.Assert.*
import org.junit.Test

class MediaSelectionTest {
    private val zone = ZoneId.of("UTC")
    private val now = Instant.parse("2026-10-08T12:00:00Z").toEpochMilli()
    private fun item(id: Int, day: Int? = null, added: Long = 0, bucket: Long = 1, kind: String = "image") =
        MediaSelection.Candidate("asset-$id", bucket, added, id.toLong(), kind,
            day?.let { Instant.parse("2026-09-${it.toString().padStart(2, '0')}T12:00:00Z").toEpochMilli() })
    private fun select(items: List<MediaSelection.Candidate<String>>, count: Int, seed: Int = 1,
                       excluded: Set<String> = emptySet()) =
        MediaSelection.select(items, count, excluded, Random(seed), zone, now)

    @Test fun seedMakesEachBatchReproducibleAndDifferentSeedsExploreTheWholeAlbum() {
        val items = (0 until 120).map { item(it) }
        val draws = (0 until 100).map { select(items, 12, it) }
        assertEquals(draws[7], select(items, 12, 7))
        assertTrue(draws.toSet().size > 90)
        assertTrue(draws.flatten().toSet().size > 110)
        draws.forEach {
            assertEquals(12, it.size)
            assertEquals(12, it.toSet().size)
            assertTrue(it.all { uri -> items.any { candidate -> candidate.uri == uri } })
        }
    }

    @Test fun everyDrawCanReachOldestAssetsAndDoesNotTakeTheNewestPrefix() {
        val items = (1..80).map { item(it, added = 80L - it) }
        val bounds = mutableListOf<Int>()
        val last = object : Random() {
            override fun nextBits(bitCount: Int) = error("Unexpected random call")
            override fun nextInt(until: Int): Int { bounds.add(until); return until - 1 }
        }
        val result = MediaSelection.select(items, 3, random = last, zoneId = zone, nowMillis = now)
        assertEquals(listOf("asset-80", "asset-79", "asset-78"), result)
        assertEquals(listOf(80, 79, 78), bounds)
    }

    @Test fun captureDaysSpreadEvenWhenEveryAssetWasImportedOnTheSameRecentDay() {
        val imported = now / 1000 - 60
        val items = (0 until 100).map { item(it, day = it % 5 + 1, added = imported) }
        val dates = items.associate { it.uri to MediaDate.day(it.added, it.takenMillis, zone, now)?.value }
        for (seed in 0 until 40) {
            val result = select(items, 5, seed)
            assertEquals(5, result.map { dates.getValue(it) }.toSet().size)
        }
    }

    @Test fun dayPreferenceDoesNotReduceLargeBatchesWhenKnownDaysRunOut() {
        val items = (0 until 45).map { item(it, day = it % 3 + 1) }
        for (seed in 0 until 20) {
            val result = select(items, 30, seed)
            assertEquals(30, result.size)
            assertEquals(30, result.toSet().size)
            assertEquals(3, result.take(3).map { uri -> items.first { it.uri == uri }.takenMillis }.toSet().size)
        }
    }

    @Test fun unknownDatesStayEligibleAndNeverCountAsADistinctCaptureDay() {
        val items = listOf(item(1, day = 1), item(2, day = 2), item(3), item(4))
        for (seed in 0 until 20) {
            val result = select(items, 4, seed)
            assertEquals(setOf("asset-1", "asset-2"), result.take(2).toSet())
            assertEquals(setOf("asset-3", "asset-4"), result.drop(2).toSet())
        }
        val singleKnownDay = listOf(item(1, day = 1), item(2, day = 1), item(3))
        assertTrue((0 until 30).map { select(singleKnownDay, 1, it).single() }.contains("asset-3"))
    }

    @Test fun oneDayAndMissingDatesBothUseRandomDrawsWithoutInventingAnError() {
        for (items in listOf((0..3).map { item(it, day = 1) }, (0..3).map { item(it) })) {
            val orders = (0 until 20).map { select(items, 4, it) }
            assertTrue(orders.toSet().size > 5)
            orders.forEach { assertEquals(items.map { it.uri }.toSet(), it.toSet()) }
        }
    }

    @Test fun duplicateUrisAndAlreadyChosenIntroAreExcludedFromTheEntireMixedPool() {
        val intro = item(100, kind = "video")
        val imagesAndVideos = (0 until 35).map { item(it, kind = if (it % 2 == 0) "video" else "image") }
        val candidates = imagesAndVideos + imagesAndVideos.take(10) + intro
        val result = select(candidates, 30, excluded = setOf(intro.uri))
        assertEquals(30, result.size)
        assertEquals(30, result.toSet().size)
        assertFalse(result.contains(intro.uri))
        assertTrue(result.any { uri -> imagesAndVideos.first { it.uri == uri }.kind == "image" })
        assertTrue(result.any { uri -> imagesAndVideos.first { it.uri == uri }.kind == "video" })
    }

    @Test fun quotaAndBucketAmbiguityFailClosedBeforeAnyDraw() {
        val noDraw = object : Random() { override fun nextBits(bitCount: Int) = error("Must reject before drawing") }
        fun rejects(items: List<MediaSelection.Candidate<String>>, count: Int, excluded: Set<String> = emptySet()) {
            assertThrows(IllegalArgumentException::class.java) {
                MediaSelection.select(items, count, excluded, noDraw, zone, now)
            }
        }
        rejects(emptyList(), 1)
        rejects(listOf(item(1)), 0)
        rejects((1..40).map { item(it) }, 31)
        rejects(listOf(item(1), item(1)), 2)
        rejects(listOf(item(1), item(2)), 2, setOf("asset-1"))
        rejects(listOf(item(1), item(2, bucket = 2)), 1)
        rejects(listOf(item(1), item(2, bucket = 2)), 1, setOf("asset-2"))
    }
}
