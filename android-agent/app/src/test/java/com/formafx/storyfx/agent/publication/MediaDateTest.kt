package com.formafx.storyfx.agent.publication

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import org.junit.Assert.*
import org.junit.Test

class MediaDateTest {
    private val now = Instant.parse("2026-10-08T12:00:00Z").toEpochMilli()
    private val utc = ZoneId.of("UTC")

    @Test fun validCaptureMillisecondsTakePriorityOverImportSeconds() {
        val taken = Instant.parse("2026-09-02T08:00:00Z").toEpochMilli()
        val day = MediaDate.day(now / 1000, taken, utc, now)
        assertEquals(LocalDate.of(2026, 9, 2), day?.value)
        assertEquals(MediaDate.Source.CAPTURED, day?.source)
    }

    @Test fun invalidOrMissingCaptureDateFallsBackWithoutCertifyingCapture() {
        for (taken in listOf(null, 0, -1, now + 1, Long.MAX_VALUE)) {
            val day = MediaDate.day(now / 1000, taken, utc, now)
            assertEquals(LocalDate.of(2026, 10, 8), day?.value)
            assertEquals(MediaDate.Source.ADDED, day?.source)
        }
        for (added in listOf(0L, -1L, now / 1000 + 1, Long.MAX_VALUE)) {
            assertNull(MediaDate.day(added, null, utc, now))
        }
    }

    @Test fun injectedDeviceTimezoneDefinesTheDayForBothSourcesAtMidnight() {
        val time = Instant.parse("2026-09-02T00:30:00Z").toEpochMilli()
        val west = ZoneId.of("America/Los_Angeles")
        for (captured in listOf(true, false)) {
            val taken = if (captured) time else null
            assertEquals(LocalDate.of(2026, 9, 2), MediaDate.day(time / 1000, taken, utc, now)?.value)
            assertEquals(LocalDate.of(2026, 9, 1), MediaDate.day(time / 1000, taken, west, now)?.value)
        }
    }
}
