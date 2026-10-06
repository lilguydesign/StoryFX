package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class KeyguardOutcomeTest {
    @Test fun autoValidationAfterReservedPinAcceptsOnlyFullyUnlockedInteractiveAndroid() {
        assertTrue(KeyguardOutcome.confirmed(true, false, false, true))
        assertFalse(KeyguardOutcome.confirmed(true, true, false, true))
        assertFalse(KeyguardOutcome.confirmed(true, false, true, true))
        assertFalse(KeyguardOutcome.confirmed(true, false, false, false))
    }
    @Test fun AnUnreservedWakeCannotBecomePinConfirmation() {
        assertFalse(KeyguardOutcome.confirmed(false, false, false, true))
    }
}
