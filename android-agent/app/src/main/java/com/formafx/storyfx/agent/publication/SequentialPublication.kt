package com.formafx.storyfx.agent.publication

import org.json.JSONArray
import org.json.JSONObject

/** One immutable draw, bounded slices, separated single-view proofs; never resumes a send. */
class SequentialPublication<T>(
    private val now: () -> Long,
    private val deadlineMillis: Long,
    private val authorize: () -> Unit,
    private val pause: (Long) -> Unit = Thread::sleep
) {
    private var entered = false
    data class Baseline(val agedRows: Int)

    companion object {
        const val METHOD = "sequential_recent_visible_v1"
        fun sizes(parts: List<Int>): List<Int> {
            require(parts.isNotEmpty() && parts.all { it in 1..30 } && parts.sum() in 10..30)
            return parts.flatMap { size -> List(size / 9) { 9 } + if (size % 9 == 0) emptyList() else listOf(size % 9) }
        }
    }

    fun execute(media: List<T>, counts: List<Int>,
                baseline: (Int) -> Baseline?, send: (List<T>) -> Unit,
                verify: (Int) -> PublicationVerification.Evidence,
                persist: (JSONObject, Boolean) -> Unit): JSONObject {
        check(!entered); entered = true
        require(media.size in 10..30 && media.distinct().size == media.size)
        require(counts.size in 2..5 && counts.all { it in 1..9 } && counts.sum() == media.size)
        val origin = now()
        val baselines = mutableListOf<Long>()
        val aged = mutableListOf<Int>()
        val verified = mutableListOf<Int>()
        val finished = mutableListOf<Long>()
        fun guard() { check(now() < deadlineMillis); authorize(); check(now() < deadlineMillis) }
        fun proof() = JSONObject().put("contract_version", 1).put("planned_counts", JSONArray(counts))
            .put("verified_counts", JSONArray(verified)).put("baseline_elapsed_ms", JSONArray(baselines))
            .put("baseline_aged_rows", JSONArray(aged)).put("verified_elapsed_ms", JSONArray(finished))
        // Persist the entire plan before the first provider gesture. A persistence failure sends nothing.
        persist(proof(), false)
        var offset = 0
        counts.forEachIndexed { index, count ->
            var ready: Baseline? = null
            while (ready == null) {
                guard()
                ready = baseline(if (index == 0) 0 else counts[index - 1])
                check(now() < deadlineMillis)
                if (ready == null || index > 0 && now() - origin <= finished.last()) {
                    ready = null
                    pause(minOf(1000L, deadlineMillis - now()).also { check(it > 0) })
                }
            }
            check(index == 0 || ready.agedRows >= counts[index - 1])
            baselines.add(now() - origin); aged.add(ready.agedRows)
            // Durable intent before this slice; no code path reconstructs or retries a slice.
            persist(proof(), false)
            guard()
            send(media.subList(offset, offset + count).toList())
            guard()
            val evidence = verify(count)
            check(now() < deadlineMillis && evidence.count == count && evidence.method == "recent_visible")
            check(now() - origin > baselines.last())
            verified.add(count); finished.add(now() - origin); offset += count
            persist(proof(), index == counts.lastIndex)
        }
        check(offset == media.size && verified == counts)
        return proof()
    }
}
