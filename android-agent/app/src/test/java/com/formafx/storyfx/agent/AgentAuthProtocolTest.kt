package com.formafx.storyfx.agent

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.time.Instant
import java.util.UUID

class AgentAuthProtocolTest {
    private val instant = 1_700_000_000_000L
    private val server = AgentAuthRoutes.publicServer
    private val installationId = UUID.randomUUID().toString()
    private val ticket = "synthetic_ticket_validation"

    @Test fun startPersistsProofBeforeNetworkAndSendsChallengeOnly() {
        val store = FakeAuthStore()
        val gateway = Gateway { path, body ->
            assertEquals("/v1/auth/agent/start", path)
            val pending = store.pending!!
            assertEquals(pending.challenge(), body.getString("code_challenge"))
            assertEquals("S256", body.getString("code_challenge_method"))
            assertFalse(body.has("code_verifier")); assertFalse(body.has("verifier"))
            assertEquals(AgentAuthRoutes.callback, body.getString("redirect_uri"))
            startReply()
        }
        val url = protocol(gateway, store).start(server, installationId, "Validation technique", "15", "0.2.0")
        assertTrue(url.startsWith("$server/agent/connect?request_id="))
        assertEquals(instant + 600_000, store.pending!!.expiresAt)
    }

    @Test fun completeValidatesStateAndExchangesPrivateProofInBody() {
        val store = prepared()
        val pending = store.pending!!
        val gateway = Gateway { path, body ->
            assertEquals("/v1/auth/agent/exchange", path)
            assertEquals(pending.verifier, body.getString("code_verifier"))
            assertEquals(pending.deviceNonce, body.getString("device_nonce"))
            assertEquals(installationId, body.getString("installation_id"))
            sessionReply()
        }
        protocol(gateway, store).complete(callback(pending.state))
        assertTrue(store.associated); assertNull(store.pending)
        assertEquals("validation@example.invalid", store.session!!.email)
    }

    @Test fun mismatchedStateCannotReachServer() {
        val store = prepared(); val gateway = Gateway { _, _ -> error("Unexpected network call") }
        rejects { protocol(gateway, store).complete(callback("X".repeat(43))) }
        assertEquals(0, gateway.calls); assertNotNull(store.pending)
    }

    @Test fun expiredProofCannotReachServer() {
        val store = prepared()
        store.pending = store.pending!!.withExpiration(instant - 1)
        val gateway = Gateway { _, _ -> error("Unexpected network call") }
        rejects { protocol(gateway, store).complete(callback(store.pending!!.state)) }
        assertEquals(0, gateway.calls)
    }

    @Test fun unresolvedDiagnosticsPreventNewAssociation() {
        val store = FakeAuthStore().apply { pendingEvents = true }
        val gateway = Gateway { _, _ -> error("Unexpected network call") }
        rejects { protocol(gateway, store).start(server, installationId, "Validation technique", "15", "0.2.0") }
        assertEquals(0, gateway.calls); assertNull(store.pending)
    }

    @Test fun responseLossPreservesPendingEncryptedStoreContract() {
        val store = prepared(); val pending = store.pending!!
        val gateway = Gateway { _, _ -> throw java.io.IOException("Synthetic offline fixture") }
        try { protocol(gateway, store).complete(callback(pending.state)); fail() }
        catch (_: java.io.IOException) { }
        assertSame(pending, store.pending); assertNull(store.session)
    }

    @Test fun invalidSessionNeverCommitsOrClearsProof() {
        val store = prepared(); val pending = store.pending!!
        val gateway = Gateway { _, _ -> sessionReply().put("token", "contains whitespace token") }
        rejects { protocol(gateway, store).complete(callback(pending.state)) }
        assertSame(pending, store.pending); assertNull(store.session)
    }

    @Test fun releaseCannotUseUnrelatedHttpsServer() {
        val store = FakeAuthStore(); val gateway = Gateway { _, _ -> error("Unexpected network call") }
        rejects { protocol(gateway, store).start("https://unrelated.invalid", installationId,
            "Validation technique", "15", "0.2.0") }
        assertEquals(0, gateway.calls)
    }

    private fun protocol(gateway: AgentGateway, store: FakeAuthStore) =
        AgentAuthProtocol(gateway, store, false) { instant }
    private fun prepared() = FakeAuthStore().apply {
        pending = AgentAuthProof.create(server, installationId, instant)
    }
    private fun callback(state: String) = "${AgentAuthRoutes.callback}?ticket=$ticket&state=$state"
    private fun startReply() = JSONObject().put("connect_url", "$server/agent/connect?request_id=${UUID.randomUUID()}")
        .put("expires_at", Instant.ofEpochMilli(instant + 600_000).toString())
    private fun sessionReply() = JSONObject().put("device_id", UUID.randomUUID().toString())
        .put("token", "synthetic_device_credential_validation_only")
        .put("user", JSONObject().put("id", UUID.randomUUID().toString())
            .put("email", "validation@example.invalid"))
    private fun rejects(action: () -> Any) {
        try { action(); fail("Invalid auth transition accepted") } catch (_: AgentAuthException) { }
    }

    private class Gateway(val handler: (String, JSONObject) -> JSONObject) : AgentGateway {
        var calls = 0
        override fun post(path: String, body: JSONObject): JSONObject { calls++; return handler(path, body) }
    }
    private class FakeAuthStore : AgentAuthStateStore {
        var pending: PendingAgentAuth? = null
        var associated = false
        var pendingEvents = false
        var session: AuthenticatedAgentSession? = null
        override fun pendingAuth() = pending
        override fun savePendingAuth(value: PendingAgentAuth) { pending = value }
        override fun associationPresent() = associated
        override fun pendingEventsPresent() = pendingEvents
        override fun saveAuthenticatedSession(value: AuthenticatedAgentSession) {
            session = value; associated = true; pending = null
        }
    }
}
