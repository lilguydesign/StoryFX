package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class PublicationNavigationTest {
    @Test fun delayedHomeAndOwnListPerformOnlyOneGesturePerTransition() {
        val states = ArrayDeque(listOf(OwnScreen.UNKNOWN, OwnScreen.UPDATES_TAB, OwnScreen.UNKNOWN,
            OwnScreen.OWN_HOME, OwnScreen.UNKNOWN, OwnScreen.OWN_LIST))
        var updates = 0
        var own = 0
        var guards = 0
        val nav = PublicationNavigation({ states.removeFirst() }, { updates++ }, { own++ }, { guards++ }, {})
        assertEquals(OwnScreen.OWN_LIST, nav.openOwn())
        assertEquals(1, updates)
        assertEquals(1, own)
        assertTrue(guards >= 6)
    }

    @Test fun resumedOwnListIsNotTakenBackOrClickedAgain() {
        val nav = PublicationNavigation({ OwnScreen.OWN_LIST }, { error("unexpected updates") },
            { error("unexpected own click") }, {}, {})
        assertEquals(OwnScreen.OWN_LIST, nav.openOwn())
    }

    @Test fun emptyHomeDoesNotOpenTheAddStatusComposer() {
        val nav = PublicationNavigation({ OwnScreen.EMPTY_HOME }, { error("unexpected updates") },
            { error("unexpected composer") }, {}, {})
        assertEquals(OwnScreen.EMPTY_HOME, nav.openOwn())
    }

    @Test fun unknownScreenIsObservedWithoutBackOrClick() {
        var observations = 0
        val nav = PublicationNavigation({ observations++; OwnScreen.UNKNOWN }, { error("unexpected click") },
            { error("unexpected click") }, {}, {})
        assertThrows(IllegalStateException::class.java) { nav.openOwn() }
        assertEquals(20, observations)
    }

    @Test fun aClickThatDoesNotNavigateIsNeverRepeated() {
        var updates = 0
        val nav = PublicationNavigation({ OwnScreen.UPDATES_TAB }, { updates++ }, { error("unexpected own") }, {}, {})
        assertThrows(IllegalStateException::class.java) { nav.openOwn() }
        assertEquals(1, updates)
    }
}
