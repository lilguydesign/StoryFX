package com.formafx.storyfx.agent

import org.junit.Assert.*
import org.junit.Test

class LoginBrowserTargetsTest {
    @Test fun chromeOnlyHasNoImplicitFallback() {
        assertNull(LoginBrowserTargets.select(listOf("com.android.chrome")))
        assertNull(LoginBrowserTargets.select(emptyList()))
    }
    @Test fun samsungIsExplicitlyPreferred() {
        assertEquals("com.sec.android.app.sbrowser", LoginBrowserTargets.select(listOf(
            "com.android.chrome", "com.microsoft.emmx", "com.sec.android.app.sbrowser")))
    }
    @Test fun supportedFallbacksRemainExplicit() {
        assertEquals("com.microsoft.emmx", LoginBrowserTargets.select(listOf("org.mozilla.firefox", "com.microsoft.emmx")))
        assertEquals("org.mozilla.firefox", LoginBrowserTargets.select(listOf("org.mozilla.firefox")))
    }
}
