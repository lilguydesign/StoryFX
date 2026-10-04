package com.formafx.storyfx.agent

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.time.Instant
import java.util.UUID

class DiagnosticRunnerTest {
    private val deviceId = UUID.randomUUID().toString()

    @Test fun eventsPersistBeforeNetworkAndRetrySameIdsWithoutAnotherClaim() {
        val store = MemoryQueue()
        val api = FakeGateway(job(), store).apply { loseFirstResponse = true }
        val runner = DiagnosticRunner(api, store)
        try { runner.synchronize(deviceId, heartbeat()); fail("Network loss expected") }
        catch (_: IOException) { }
        assertEquals(2, JSONArray(store.read()).length())
        val eventId = JSONArray(store.read()).getJSONObject(0).getString("event_id")
        runner.synchronize(deviceId, heartbeat())
        assertEquals(1, api.claims)
        assertEquals(3, api.events.size)
        assertEquals(eventId, api.events[0].getString("event_id"))
        assertEquals(eventId, api.events[1].getString("event_id"))
        assertEquals("STARTED", api.events[1].getString("stage"))
        assertEquals("DIAGNOSTIC_CONFIRMED", api.events[2].getString("stage"))
        assertEquals("diagnostic_only", api.events[2].getString("detail"))
        assertEquals(0, JSONArray(store.read()).length())
        assertTrue(api.persistedBeforeSend)
    }

    @Test fun unresolvedOutboxBlocksHeartbeatAndNewClaims() {
        val store = MemoryQueue()
        val api = FakeGateway(job(), store).apply { loseEveryResponse = true }
        val runner = DiagnosticRunner(api, store)
        repeat(2) {
            try { runner.synchronize(deviceId, heartbeat()); fail("Network loss expected") }
            catch (_: IOException) { }
        }
        assertEquals(1, api.claims)
        assertEquals(1, api.heartbeats)
        assertEquals(2, JSONArray(store.read()).length())
    }

    @Test fun livePublicationAndOtherDeviceJobsAreRejected() {
        for (invalid in listOf(job().put("kind", "publish"),
            job().put("device_id", UUID.randomUUID().toString()))) {
            val store = MemoryQueue()
            val api = FakeGateway(invalid, store)
            try { DiagnosticRunner(api, store).synchronize(deviceId, heartbeat()); fail("Must refuse") }
            catch (_: IllegalStateException) { }
            assertTrue(api.events.isEmpty())
            assertEquals("[]", store.read())
        }
    }

    @Test fun expiredInitialLeaseIsNotExecuted() {
        val store = MemoryQueue()
        val api = FakeGateway(job().put("lease_expires_at", Instant.now().minusSeconds(60).toString()), store)
        try { DiagnosticRunner(api, store).synchronize(deviceId, heartbeat()); fail("Must refuse") }
        catch (_: IllegalStateException) { }
        assertTrue(api.events.isEmpty())
    }

    @Test fun noJobSendsOnlyHeartbeatAndClaim() {
        val store = MemoryQueue()
        val api = FakeGateway(null, store)
        DiagnosticRunner(api, store).synchronize(deviceId, heartbeat())
        assertEquals(1, api.heartbeats)
        assertEquals(1, api.claims)
        assertTrue(api.events.isEmpty())
    }

    private fun heartbeat() = JSONObject().put("battery_percent", 50).put("screen_locked", true)
        .put("app_version", "0.1.0").put("executor", "diagnostic")

    private fun job() = JSONObject().put("id", UUID.randomUUID().toString())
        .put("device_id", deviceId).put("kind", "diagnostic")
        .put("expires_at", Instant.now().plusSeconds(3600).toString())
        .put("lease_expires_at", Instant.now().plusSeconds(120).toString())
        .put("lease_token", "synthetic-lease")

    private class MemoryQueue : QueueStore {
        private var value = "[]"
        override fun read() = value
        override fun write(value: String) { this.value = value }
    }

    private class FakeGateway(private val job: JSONObject?, private val store: QueueStore) : AgentGateway {
        var claims = 0
        var heartbeats = 0
        var loseFirstResponse = false
        var loseEveryResponse = false
        var persistedBeforeSend = true
        val events = mutableListOf<JSONObject>()

        override fun post(path: String, body: JSONObject): JSONObject {
            return when (path) {
                "/v1/devices/heartbeat" -> { heartbeats++; JSONObject() }
                "/v1/agent/claim" -> { claims++; JSONObject().put("job", job ?: JSONObject.NULL) }
                else -> {
                    persistedBeforeSend = persistedBeforeSend && JSONArray(store.read()).length() > 0
                    events.add(JSONObject(body.toString()))
                    if (loseEveryResponse || (loseFirstResponse && events.size == 1)) throw IOException()
                    JSONObject().put("accepted", true)
                }
            }
        }
    }
}
