package com.formafx.storyfx.agent.publication

import com.formafx.storyfx.agent.AgentGateway
import com.formafx.storyfx.agent.AgentRequestException
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PublicationHeartbeatTest {
    private fun body(globalEnabled: Boolean = false) = JSONObject().put("service_ready", true).put("media_ready", true)
        .put("screen_locked", false).put("own_status_empty", false).put("media_modes_ready", true)
        .put("native_runtime", NativeRuntimeState(globalEnabled, true, true, true, true).toJson())

    private class Fake(private val failures: List<Exception>) : AgentGateway {
        val bodies = mutableListOf<JSONObject>()
        override fun post(path: String, body: JSONObject): JSONObject {
            assertEquals("/v1/control/android/heartbeat", path)
            bodies.add(JSONObject(body.toString()))
            if (bodies.size <= failures.size) throw failures[bodies.size - 1]
            return JSONObject().put("ready", false)
        }
    }

    @Test fun supportedServerReceivesGlobalStopAndPhysicalStateWithoutHealthRequest() {
        val api = Fake(emptyList())
        PublicationHeartbeat(api) { error("No negotiation needed") }.send(body())
        assertEquals(1, api.bodies.size)
        assertFalse(api.bodies[0].getJSONObject("native_runtime").getBoolean("global_enabled"))
        assertTrue(api.bodies[0].getBoolean("service_ready"))
        assertTrue(api.bodies[0].getBoolean("media_modes_ready"))
    }

    @Test fun recognisedRollbackProjectsGlobalStopWithoutMutatingPhysicalInput() {
        val api = Fake(listOf(AgentRequestException(422)))
        val original = body()
        PublicationHeartbeat(api) { false }.send(original)
        assertEquals(2, api.bodies.size)
        assertFalse(api.bodies.last().has("native_runtime"))
        assertTrue(api.bodies.last().has("own_status_empty"))
        assertTrue(api.bodies.last().has("media_modes_ready"))
        assertFalse(api.bodies.last().getBoolean("service_ready"))
        assertFalse(api.bodies.last().getBoolean("media_modes_ready"))
        assertTrue(api.bodies.last().getBoolean("media_ready"))
        assertTrue(original.has("native_runtime"))
        assertTrue(original.getBoolean("service_ready"))
        assertTrue(original.getBoolean("media_modes_ready"))
    }

    @Test fun recognisedRollbackKeepsReadinessWhenGlobalPilotIsEnabled() {
        val api = Fake(listOf(AgentRequestException(422)))
        PublicationHeartbeat(api) { false }.send(body(true))
        assertTrue(api.bodies.last().getBoolean("service_ready"))
        assertTrue(api.bodies.last().getBoolean("media_modes_ready"))
        assertFalse(api.bodies.last().has("native_runtime"))
    }

    @Test fun newOrUnknownServerCannotSilentlyStripPhysicalGuardAfterAValidationRefusal() {
        for (supported in listOf(true, null)) {
            val api = Fake(listOf(AgentRequestException(422)))
            assertThrows(AgentRequestException::class.java) { PublicationHeartbeat(api) { supported }.send(body()) }
            assertEquals(1, api.bodies.size)
        }
    }

    @Test fun networkTimeoutOrAuthFailureNeverRetriesHeartbeatInTheSameCall() {
        for (failure in listOf(java.io.IOException("synthetic"), AgentRequestException(403), AgentRequestException(500))) {
            val api = Fake(listOf(failure))
            assertThrows(Exception::class.java) { PublicationHeartbeat(api) { error("No health request") }.send(body()) }
            assertEquals(1, api.bodies.size)
        }
    }

    @Test fun oldestKnownBackendKeepsThePriorOptionalFieldFallbackBounded() {
        val api = Fake(listOf(AgentRequestException(422), AgentRequestException(422)))
        PublicationHeartbeat(api) { false }.send(body())
        assertEquals(3, api.bodies.size)
        assertFalse(api.bodies.last().has("own_status_empty"))
        assertFalse(api.bodies.last().has("media_modes_ready"))
        assertEquals(false, api.bodies.last().get("service_ready"))
    }
}
