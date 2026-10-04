package com.formafx.storyfx.agent

import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test

class ServerAddressTest {
    @Test fun httpsRootIsAcceptedAndNormalized() {
        assertEquals("https://story.example", ServerAddress.validate(" https://story.example/ ", false))
    }

    @Test fun httpIsRestrictedToDebugEmulator() {
        assertEquals("http://10.0.2.2:8788", ServerAddress.validate("http://10.0.2.2:8788", true))
        rejected("http://10.0.2.2:8788", false)
        rejected("http://192.168.1.2:8788", true)
        rejected("http://story.example", true)
        rejected("http://localhost:8788", true)
    }

    @Test fun credentialsQueriesPathsAndLocalhostAreRejected() {
        for (value in listOf("https://user:password@story.example", "https://story.example/?token=x",
            "https://story.example/path", "https://story.example/#token", "https://localhost",
            "https://story.example:0", "file:///server", "garbage")) rejected(value, true)
    }

    private fun rejected(value: String, debug: Boolean) {
        try { ServerAddress.validate(value, debug); fail("Address must be refused") }
        catch (_: IllegalArgumentException) { }
    }
}
