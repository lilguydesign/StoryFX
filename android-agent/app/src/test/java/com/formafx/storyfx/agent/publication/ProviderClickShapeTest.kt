package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProviderClickShapeTest {
    @Test fun navigationAcceptsOnlyAnIndividualTabAcrossBothPhoneSizes() {
        assertTrue(ProviderClickShape.accepts(270, 150, 1080, 2340, true))
        assertTrue(ProviderClickShape.accepts(180, 120, 720, 1544, true))
        assertFalse(ProviderClickShape.accepts(1080, 150, 1080, 2340, true))
        assertFalse(ProviderClickShape.accepts(720, 1544, 720, 1544, true))
    }
    @Test fun selectionRefusesTheWholeContactListAndInvalidBounds() {
        assertTrue(ProviderClickShape.accepts(720, 130, 720, 1544, false))
        assertFalse(ProviderClickShape.accepts(720, 1300, 720, 1544, false))
        assertFalse(ProviderClickShape.accepts(0, 130, 720, 1544, false))
        assertFalse(ProviderClickShape.accepts(720, 130, 0, 1544, false))
    }
}
