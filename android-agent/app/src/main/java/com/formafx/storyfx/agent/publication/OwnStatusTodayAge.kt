package com.formafx.storyfx.agent.publication

import java.time.LocalTime
import java.time.temporal.ChronoUnit

/** Interpret only an explicit Today date in the device's local clock. Never guess a bare time. */
object OwnStatusTodayAge {
    private val twelve = Regex("Today, (1[0-2]|[1-9]):([0-5]\\d) ([AP]M)")
    private val twentyFour = Regex("(?:Today|Aujourd'hui), ([01]?\\d|2[0-3]):([0-5]\\d)")

    fun isAged(text: String, now: LocalTime): Boolean {
        val normalized = text.trim().replace('\u00a0', ' ').replace('\u202f', ' ').replace('\u2019', '\'')
        val amPm = twelve.matchEntire(normalized)
        val plain = twentyFour.matchEntire(normalized)
        val stamp = when {
            amPm != null -> LocalTime.of(amPm.groupValues[1].toInt() % 12 +
                if (amPm.groupValues[3] == "PM") 12 else 0, amPm.groupValues[2].toInt())
            plain != null -> LocalTime.of(plain.groupValues[1].toInt(), plain.groupValues[2].toInt())
            else -> return false
        }
        // Minute precision cannot exclude a fresh row until two full displayed minutes have elapsed.
        // Negative differences, including midnight/clock changes, remain unknown rather than wrapping.
        return ChronoUnit.SECONDS.between(stamp, now) >= 120
    }
}
