package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class PublicationListPositionTest {
    @Test fun existingScrolledListIsReadBackToStartWithoutExtraGesture() {
        var observations = 0
        var guards = 0
        PublicationListPosition.reset({ ++observations < 3 }, { guards++ }, {})
        assertEquals(3, observations)
        assertEquals(3, guards)
    }

    @Test fun listThatNeverReachesItsStartStopsBeforePublication() {
        var observations = 0
        assertThrows(IllegalStateException::class.java) {
            PublicationListPosition.reset({ observations++; true }, {}, {})
        }
        assertEquals(16, observations)
    }
}
