package com.formafx.storyfx.agent.publication

/** Pure selection: one exact bucket, distinct assets, stable newest-first order. */
object MediaSelection {
    data class Candidate<T>(val uri: T, val bucket: Long, val added: Long, val id: Long, val kind: String)

    fun <T> select(candidates: List<Candidate<T>>, count: Int, excluded: Set<T> = emptySet()): List<T> {
        require(count in 1..30)
        require(candidates.map { it.bucket }.toSet().size == 1)
        val result = candidates.sortedWith(compareByDescending<Candidate<T>> { it.added }.thenByDescending { it.id })
            .map { it.uri }.distinct().filter { it !in excluded }.take(count)
        require(result.size == count)
        return result
    }
}
