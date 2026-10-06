package com.formafx.storyfx.agent.publication

import org.junit.Assert.assertEquals
import org.junit.Test

class KeyguardFailureTest {
    @Test fun reportsTheFailedUiGuardWithoutItsMessage() {
        assertEquals("STATE_GUARD", KeyguardFailure.kind(java.util.concurrent.ExecutionException(IllegalStateException("private"))))
        assertEquals("UI_TIMEOUT", KeyguardFailure.kind(java.util.concurrent.TimeoutException("private")))
    }
    @Test fun unknownErrorsExportOnlyAnOpaqueCategory() {
        assertEquals("PLATFORM_ERROR", KeyguardFailure.kind(Exception("private")))
    }
}
