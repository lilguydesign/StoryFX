package com.formafx.storyfx.agent.publication

/** Compare complete provider collection counts, never assume missing metadata means zero. */
object PublicationCountDelta {
    fun matches(before: Int?, after: Int?, requested: Int): Boolean =
        before != null && after != null && before in 0..600 && after in 0..600 &&
            requested in 1..30 && after - before == requested
}
