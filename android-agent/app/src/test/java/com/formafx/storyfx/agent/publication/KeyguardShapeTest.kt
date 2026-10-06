package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class KeyguardShapeTest {
    private val keys = (0..9).map { "com.android.systemui:id/key$it" }.toSet()
    @Test fun acceptsOnlyCompleteEmptyNumericSystemChallenge() {
        assertTrue(KeyguardShape.accepts("com.android.systemui", true, keys))
        assertFalse(KeyguardShape.accepts("com.whatsapp.w4b", true, keys))
        assertFalse(KeyguardShape.accepts("com.android.systemui", false, keys))
        assertFalse(KeyguardShape.accepts("com.android.systemui", true, keys.minus("com.android.systemui:id/key0")))
        assertFalse(KeyguardShape.accepts("com.android.systemui", true, emptySet()))
    }
}
