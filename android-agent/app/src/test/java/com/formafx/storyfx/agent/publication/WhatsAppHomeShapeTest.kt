package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WhatsAppHomeShapeTest {
    @Test fun separatesHeaderAndBottomNavigationForBothSamsungSizes() {
        for ((width, height) in listOf(720 to 1544, 1080 to 2340)) {
            assertTrue(WhatsAppHomeShape.portrait(width, height))
            assertTrue(WhatsAppHomeShape.header(height / 12, height))
            assertFalse(WhatsAppHomeShape.navigation(height / 12, height))
            assertTrue(WhatsAppHomeShape.navigation(height * 9 / 10, height))
            assertFalse(WhatsAppHomeShape.header(height * 9 / 10, height))
            assertTrue(WhatsAppHomeShape.section(height / 8, height))
            assertTrue(WhatsAppHomeShape.ownTile(width / 8, height / 3, width, height))
            assertFalse(WhatsAppHomeShape.ownTile(width / 2, height / 3, width, height))
            assertFalse(WhatsAppHomeShape.ownTile(width / 8, height * 3 / 4, width, height))
        }
    }
    @Test fun requiresEveryHomeAnchorAndNeverAcceptsOwnStatusesOrSendScreens() {
        assertTrue(WhatsAppHomeShape.empty(true, true, true, true, false, false))
        for (missing in 0..3) {
            val anchors = MutableList(4) { true }; anchors[missing] = false
            assertFalse(WhatsAppHomeShape.empty(anchors[0], anchors[1], anchors[2], anchors[3], false, false))
        }
        assertFalse(WhatsAppHomeShape.empty(true, true, true, true, true, false))
        assertFalse(WhatsAppHomeShape.empty(true, true, true, true, false, true))
        assertFalse(WhatsAppHomeShape.portrait(2340, 1080))
        assertFalse(WhatsAppHomeShape.portrait(0, 1544))
    }
}
