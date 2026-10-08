package com.formafx.storyfx.agent.publication

/** Observe until the existing attempt deadline; never receives any send operation. */
class PublicationVerification(
    private val deadlineMillis: Long,
    private val now: () -> Long,
    private val authorize: () -> Unit,
    private val pause: (Long) -> Unit = Thread::sleep
) {
    data class Evidence(val count: Int, val method: String)

    private fun timeRemaining() = deadlineMillis - now()
    private fun guard() {
        check(timeRemaining() > 0)
        authorize()
        check(timeRemaining() > 0)
    }
    private fun waitForUpload() {
        check(timeRemaining() > 0)
        pause(minOf(1000L, timeRemaining()))
    }

    fun verify(expected: Int, restart: () -> Unit, observe: () -> List<Int?>,
               scroll: () -> Boolean, record: (Evidence) -> Unit): Evidence {
        require(expected in 1..30)
        while (true) {
            guard()
            restart()
            check(timeRemaining() > 0)
            // Positions may shift even between adjacent pages. Never accumulate them.
            for (page in 0 until 8) {
                guard()
                val completed = observe()
                check(timeRemaining() > 0)
                val method = PublicationProof.verified(expected, completed)
                val visibleCompleted = completed.count { it == null } +
                    completed.filterNotNull().filter { it >= 0 }.distinct().size
                val evidence = Evidence(visibleCompleted.coerceAtMost(30), method)
                record(evidence)
                if (method != "none") return evidence
                val canInspectNext = completed.isNotEmpty() && completed.all { it != null } && completed.size < expected
                if (!canInspectNext) break
                guard()
                val moved = scroll()
                check(timeRemaining() > 0)
                if (!moved) break
                waitForUpload()
            }
            // No completed row or no further page can mean an upload is still in progress.
            waitForUpload()
        }
    }
}
