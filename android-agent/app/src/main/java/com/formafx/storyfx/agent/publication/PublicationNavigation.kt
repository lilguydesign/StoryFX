package com.formafx.storyfx.agent.publication

enum class OwnScreen { UNKNOWN, UPDATES_TAB, OWN_HOME, EMPTY_HOME, OWN_LIST }

/** Only known navigation controls are used. Delayed rendering never repeats a click. */
class PublicationNavigation(
    private val observe: () -> OwnScreen,
    private val updates: () -> Unit,
    private val own: () -> Unit,
    private val authorize: () -> Unit,
    private val pause: (Long) -> Unit = Thread::sleep
) {
    private fun await(accepted: Set<OwnScreen>): OwnScreen {
        repeat(20) {
            authorize()
            val state = observe()
            if (state in accepted) return state
            pause(500)
        }
        error("OWN_STATUS_NAVIGATION_UNAVAILABLE")
    }

    fun openOwn(beforeOwn: () -> Unit = {}): OwnScreen {
        val homes = setOf(OwnScreen.OWN_HOME, OwnScreen.EMPTY_HOME, OwnScreen.OWN_LIST)
        var state = await(homes + OwnScreen.UPDATES_TAB)
        if (state == OwnScreen.UPDATES_TAB) {
            authorize(); updates()
            state = await(homes)
        }
        beforeOwn()
        if (state == OwnScreen.OWN_HOME) {
            authorize(); own()
            state = await(setOf(OwnScreen.OWN_LIST, OwnScreen.EMPTY_HOME))
        }
        return state
    }
}
