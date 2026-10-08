package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class BootUnlockPolicyTest {
    @Test fun requiresConsentCredentialAndLockedUser() {
        assertTrue(BootUnlockPolicy.eligible(true, true, false, 8, 7, globalEnabled = true))
        assertFalse(BootUnlockPolicy.eligible(false, true, false, 8, 7, globalEnabled = true))
        assertFalse(BootUnlockPolicy.eligible(true, false, false, 8, 7, globalEnabled = true))
        assertFalse(BootUnlockPolicy.eligible(true, true, true, 8, 7, globalEnabled = true))
    }
    @Test fun doesNotRearmOnServiceRestartOrUnknownBoot() {
        assertFalse(BootUnlockPolicy.eligible(true, true, false, 8, 8, globalEnabled = true))
        assertFalse(BootUnlockPolicy.eligible(true, true, false, -1, 7, globalEnabled = true))
        assertTrue(BootUnlockPolicy.eligible(true, true, false, 9, 8, globalEnabled = true))
    }
    @Test fun oldBootConsentWithoutAnExplicitGlobalFlagDoesNotAuthorizeUnlock() {
        assertFalse(BootUnlockPolicy.eligible(true, true, false, 9, 8))
    }
    @Test fun globalStopBlocksBootWithoutRewritingConsentOrConsumedAttempts() {
        assertFalse(BootUnlockPolicy.eligible(true, true, false, 9, 8, globalEnabled = false))
        assertTrue(BootUnlockPolicy.eligible(true, true, false, 9, 8, globalEnabled = true))
        assertFalse(BootUnlockPolicy.eligible(true, true, false, 9, 9, globalEnabled = true))
        assertFalse(BootUnlockPolicy.eligible(false, true, false, 9, 8, globalEnabled = true))
    }
}
