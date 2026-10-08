package com.formafx.storyfx.agent.publication

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

/** MediaStore DATE_ADDED is seconds; DATE_TAKEN is milliseconds and may be unavailable. */
object MediaDate {
    enum class Source { CAPTURED, ADDED }
    data class Day(val value: LocalDate, val source: Source)

    fun day(addedSeconds: Long, takenMillis: Long?, zoneId: ZoneId, nowMillis: Long): Day? {
        if (takenMillis != null && takenMillis > 0 && takenMillis <= nowMillis) {
            return Day(Instant.ofEpochMilli(takenMillis).atZone(zoneId).toLocalDate(), Source.CAPTURED)
        }
        if (addedSeconds > 0 && addedSeconds <= nowMillis / 1000) {
            // An import day can help spread a draw, but it never certifies the capture day.
            return Day(Instant.ofEpochSecond(addedSeconds).atZone(zoneId).toLocalDate(), Source.ADDED)
        }
        return null
    }
}
