package com.formafx.storyfx.agent.publication

import org.junit.Assert.*
import org.junit.Test

class BootChallengePolicyTest {
    @Test fun preparationMayWakeTheChallengeBeforeLockFlagsAppearButNeverAfterAPinAttempt() {
        assertTrue(BootChallengePolicy.canPrepare(false, true, false))
        assertFalse(BootChallengePolicy.canPrepare(true, true, false))
        assertFalse(BootChallengePolicy.canPrepare(false, false, false))
        assertFalse(BootChallengePolicy.canPrepare(false, true, true))
    }
    @Test fun bootAnimationIsNotAnUnlockOrAReadyChallenge() {
        assertFalse(BootChallengePolicy.ready(false, false, false, true))
        assertFalse(KeyguardOutcome.awake(false, false, true, false))
        assertFalse(KeyguardOutcome.confirmed(true, false, false, true, false))
    }
    @Test fun doesNotConsumeTheAttemptBeforeRecognizingTheKeypad() {
        assertFalse(BootChallengePolicy.ready(false, true, true, false))
        assertTrue(BootChallengePolicy.ready(false, true, true, true))
        assertTrue(BootChallengePolicy.ready(false, true, false, true))
        assertFalse(BootChallengePolicy.ready(true, true, true, true))
    }
    @Test fun successRequiresCredentialStorageAndBothLocksUnlocked() {
        assertTrue(KeyguardOutcome.confirmed(true, false, false, true, true))
        assertFalse(KeyguardOutcome.confirmed(true, true, false, true, true))
        assertFalse(KeyguardOutcome.confirmed(true, false, true, true, true))
        assertFalse(KeyguardOutcome.confirmed(false, false, false, true, true))
    }
}
