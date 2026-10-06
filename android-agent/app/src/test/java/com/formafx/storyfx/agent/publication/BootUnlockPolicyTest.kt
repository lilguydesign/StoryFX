package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class BootUnlockPolicyTest {
    @Test fun requiresConsentCredentialAndLockedUser() {
        assertTrue(BootUnlockPolicy.eligible(true, true, false, 8, 7))
        assertFalse(BootUnlockPolicy.eligible(false, true, false, 8, 7))
        assertFalse(BootUnlockPolicy.eligible(true, false, false, 8, 7))
        assertFalse(BootUnlockPolicy.eligible(true, true, true, 8, 7))
    }
    @Test fun doesNotRearmOnServiceRestartOrUnknownBoot() {
        assertFalse(BootUnlockPolicy.eligible(true, true, false, 8, 8))
        assertFalse(BootUnlockPolicy.eligible(true, true, false, -1, 7))
        assertTrue(BootUnlockPolicy.eligible(true, true, false, 9, 8))
    }
}
