package com.formafx.storyfx.agent.publication

import java.time.LocalDate
import java.time.ZoneId
import kotlin.random.Random

/** Random draws across one exact album, without replacement; this does not simulate Gallery scrolling. */
object MediaSelection {
    data class Candidate<T>(val uri: T, val bucket: Long, val added: Long, val id: Long, val kind: String,
                            val takenMillis: Long? = null)

    fun <T> select(candidates: List<Candidate<T>>, count: Int, excluded: Set<T> = emptySet(),
                   random: Random = Random.Default, zoneId: ZoneId = ZoneId.systemDefault(),
                   nowMillis: Long = System.currentTimeMillis()): List<T> {
        require(count in 1..30)
        require(candidates.map { it.bucket }.toSet().size == 1)
        val remaining = candidates.distinctBy { it.uri }.filter { it.uri !in excluded }.map {
            it.uri to MediaDate.day(it.added, it.takenMillis, zoneId, nowMillis)?.value
        }.toMutableList()
        require(remaining.size >= count)
        val preferDays = remaining.mapNotNull { it.second }.toSet().size > 1
        val usedDays = mutableSetOf<LocalDate>()
        val result = ArrayList<T>(count)
        repeat(count) {
            // Unknown dates are never counted as an additional day. Once known days have been
            // represented (or only one exists), every remaining asset is eligible for the draw.
            val unseen = if (preferDays) remaining.indices.filter {
                remaining[it].second?.let { day -> day !in usedDays } == true
            } else emptyList()
            val index = if (unseen.isEmpty()) random.nextInt(remaining.size) else unseen[random.nextInt(unseen.size)]
            val selected = remaining.removeAt(index)
            result.add(selected.first)
            selected.second?.let(usedDays::add)
        }
        return result
    }
}
