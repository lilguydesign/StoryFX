package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class KeyguardResultTest {
    @Test fun oldEncryptedPreferencesAndStableNewStatesBothRemainReadable() {
        assertEquals(KeyguardResult.AUTHORIZATION_REFUSED, KeyguardResult.read("AUTORISATION_REFUSÉE"))
        assertEquals(KeyguardResult.PIN_CONFIRMED, KeyguardResult.read("PIN_CONFIRMED"))
        assertEquals(KeyguardResult.PIN_CONFIRMED, KeyguardResult.read("PIN_CONFIRMÉ"))
    }
    @Test fun unknownOrLegacyGenericConfirmationNeverProvesANativePin() {
        assertEquals(KeyguardResult.UNTESTED, KeyguardResult.read("unknown"))
        assertNotEquals(KeyguardResult.PIN_CONFIRMED, KeyguardResult.read("CONFIRMÉ"))
        assertNotEquals(KeyguardResult.PIN_CONFIRMED, KeyguardResult.WAKE_CONFIRMED)
    }
}
