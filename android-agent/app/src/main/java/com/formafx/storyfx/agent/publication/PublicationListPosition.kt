package com.formafx.storyfx.agent.publication

/** Read-only list navigation is bounded and requires a fresh authorization at each step. */
object PublicationListPosition {
    fun reset(scrollBack: () -> Boolean, authorize: () -> Unit, pause: (Long) -> Unit = Thread::sleep) {
        repeat(16) {
            authorize()
            if (!scrollBack()) return
            pause(300)
        }
        error("OWN_STATUS_LIST_START_UNAVAILABLE")
    }
}
